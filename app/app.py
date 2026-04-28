from flask import Flask, request, jsonify, send_file
import os
import uuid
from dataclasses import asdict, is_dataclass
from werkzeug.utils import secure_filename
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config
from modules.doc_processor import DocProcessor
from modules.llm_client import LLMClient
from modules.pdf_processor import PDFProcessor
from modules.ocr_processor import OCRProcessor
from modules.data_structurer import DataStructurer
from modules.historical_citation_verifier import HistoricalCitationVerifier
from modules.historical_citation_workspace import HistoricalCitationWorkspaceInterface
from modules.ndl_download_workflow import NDLDownloadModule, NDLDownloadRequest
from modules.pdf_to_ner_workflow import PDFToNERConfig, PDFToNERPipeline
from modules.task_manager import TaskManager
from modules.unified_ocr_processor import UnifiedOCRProcessor, UnifiedOCRConfig, OCRModelType


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = config['default'].MAX_CONTENT_LENGTH

class LazyService:
    def __init__(self, factory, name="", description=""):
        self._factory = factory
        self._instance = None
        self.name = name
        self.description = description

    def _get_instance(self):
        if self._instance is None:
            self._instance = self._factory()
        return self._instance

    def __getattr__(self, item):
        return getattr(self._get_instance(), item)

    @property
    def initialized(self):
        return self._instance is not None

    def status(self):
        return {
            'name': self.name,
            'description': self.description,
            'initialized': self.initialized,
            'class_name': type(self._instance).__name__ if self._instance is not None else None,
        }

unified_ocr_config = UnifiedOCRConfig(
    ndlocr_path=config['default'].NDLOCR_LITE_PATH or None,
    ndlkoten_path=config['default'].NDLKOTENOCR_LITE_PATH or None,
    tesseract_path=config['default'].TESSERACT_PATH,
    use_gpu=config['default'].NDLOCR_LITE_GPU,
    enable_visualization=config['default'].NDLOCR_LITE_VIZ,
    timeout=config['default'].NDLOCR_LITE_TIMEOUT,
    default_model=config['default'].DEFAULT_OCR_MODEL
)
doc_processor = LazyService(lambda: DocProcessor(), name='doc_processor', description='Document parsing service')
llm_client = LazyService(lambda: LLMClient(config['default'].LLM_CONFIG), name='llm_client', description='LLM service')
pdf_processor = LazyService(lambda: PDFProcessor(config['default'].OUTPUT_DIR), name='pdf_processor', description='PDF service')
ocr_processor = LazyService(lambda: OCRProcessor(config['default'].TESSERACT_PATH), name='ocr_processor', description='Tesseract OCR service')
data_structurer = LazyService(lambda: DataStructurer(), name='data_structurer', description='Structured data service')
unified_ocr_processor = LazyService(lambda: UnifiedOCRProcessor(unified_ocr_config), name='unified_ocr_processor', description='Unified OCR service')
ndl_download_module = LazyService(lambda: NDLDownloadModule(), name='ndl_download_module', description='NDL download service')
historical_citation_verifier = LazyService(
    lambda: HistoricalCitationVerifier(
        ndl_download_module=ndl_download_module,
        pdf_processor=pdf_processor,
        ocr_processor=unified_ocr_processor,
        llm_client=llm_client,
    ),
    name='historical_citation_verifier',
    description='Historical citation verification service',
)
historical_citation_workspace = LazyService(
    lambda: HistoricalCitationWorkspaceInterface(verifier=historical_citation_verifier),
    name='historical_citation_workspace',
    description='Workspace-safe historical citation package interface',
)
_task_manager = None

LAZY_SERVICES = {
    'doc_processor': doc_processor,
    'llm_client': llm_client,
    'pdf_processor': pdf_processor,
    'ocr_processor': ocr_processor,
    'data_structurer': data_structurer,
    'unified_ocr_processor': unified_ocr_processor,
    'ndl_download_module': ndl_download_module,
    'historical_citation_verifier': historical_citation_verifier,
    'historical_citation_workspace': historical_citation_workspace,
}


def create_app(test_config=None):
    """Return the Flask app without initializing lazy services."""

    if test_config:
        app.config.update(test_config)
    return app


def get_service_status():
    return {
        name: service.status()
        for name, service in LAZY_SERVICES.items()
    }


def _get_task_manager():
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager(
            mode=os.getenv('TASK_EXECUTION_MODE', 'script'),
            provider=config['default'].LLM_CONFIG.get('provider', 'qwen'),
        )
    return _task_manager


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config['default'].ALLOWED_EXTENSIONS


def _parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _parse_int(value, default=None):
    if value in (None, ''):
        return default
    return int(value)


def _request_payload():
    return request.get_json(silent=True) or request.form or {}


def _save_uploaded_pdf(file_storage, prefix):
    unique_id = uuid.uuid4().hex[:8]
    temp_dir = os.path.join(config['default'].TEMP_DIR, f'{prefix}_{unique_id}')
    os.makedirs(temp_dir, exist_ok=True)
    filename = secure_filename(file_storage.filename) or 'input.pdf'
    temp_pdf_path = os.path.join(temp_dir, filename)
    file_storage.save(temp_pdf_path)
    return temp_dir, temp_pdf_path


def _dataclass_payload(obj):
    if is_dataclass(obj):
        return asdict(obj)
    return obj


def _run_reusable_pdf_to_ner_pipeline(temp_pdf_path, options):
    output_dir = options.get('output_dir') or os.path.join(
        config['default'].OUTPUT_DIR,
        'pdf_to_ner_runs',
        uuid.uuid4().hex[:8],
    )
    pipeline = PDFToNERPipeline(
        PDFToNERConfig(
            pdf_path=temp_pdf_path,
            output_dir=output_dir,
            start_page=_parse_int(options.get('start_page'), 1),
            end_page=_parse_int(options.get('end_page')),
            dpi=_parse_int(options.get('dpi'), config['default'].PDF_DPI),
            ndlocr_device=options.get('ndlocr_device', 'cpu'),
            run_ocr=_parse_bool(options.get('run_ocr'), True),
            run_ner=_parse_bool(options.get('run_ner'), True),
            min_entry_chars=_parse_int(options.get('min_entry_chars'), 40),
            ner_model=options.get('ner_model', 'qwen3.6-plus'),
            ner_chunk_size=_parse_int(options.get('ner_chunk_size'), 3),
            max_retries=_parse_int(options.get('max_retries'), 3),
            sleep_between_calls=float(options.get('sleep_between_calls', 1.5)),
            entry_limit_per_page=_parse_int(options.get('entry_limit_per_page')),
            confirm_ner_cost=_parse_bool(options.get('confirm_ner_cost'), False),
            continue_on_error=_parse_bool(options.get('continue_on_error'), False),
        )
    )
    return pipeline.run()


@app.route('/')
def index():
    """系统信息接口"""
    return jsonify({
        'name': 'History Research AI Tools',
        'version': '1.1.0',
        'description': '日本史研究辅助工具后端系统',
        'ocr_methods': {
            'tesseract': '本地Tesseract OCR',
            'ndlocr-lite': '日本国立国会图书馆NDL OCR-Lite ⭐推荐(近代现代文献)',
            'ndlkotenocr-lite': '日本国立国会图书馆NDL古典籍OCR-Lite ⭐(古典籍文献)',
            'unified': '统一OCR处理器 - 支持模型切换',
            'llm': '大语言模型辅助OCR'
        },
        'endpoints': {
            'doc': {
                'parse': 'POST /api/doc/parse - 解析Word文档',
                'polish': 'POST /api/doc/polish - 学术润色',
                'generate': 'POST /api/doc/generate - 生成Word文档',
                'verify_historical_citations': 'POST /api/doc/verify-historical-citations - 核对中文引文与 NDL 日文史料原文',
                'historical_citation_package': 'POST /api/doc/historical-citation-package - 输出工作区统一历史引文 package'
            },
            'pdf': {
                'info': 'GET /api/pdf/info?path=xxx - 获取PDF信息',
                'convert': 'POST /api/pdf/convert - PDF转图片',
                'analyze_layout': 'POST /api/pdf/analyze-layout - 版面分析'
            },
            'ocr': {
                'extract': 'POST /api/ocr/extract - Tesseract OCR',
                'llm_ocr': 'POST /api/ocr/llm - LLM辅助OCR',
                'ndlocr_lite': 'POST /api/ocr/ndlocr-lite - NDL OCR-Lite ⭐',
                'ndlocr_status': 'GET /api/ocr/ndlocr-lite/status - NDL状态',
                'list_models': 'GET /api/ocr/models - 列出所有OCR模型',
                'model_process': 'POST /api/ocr/model/process - 使用指定模型OCR',
                'model_compare': 'POST /api/ocr/model/compare - 对比两种模型'
            },
            'data': {
                'structure': 'POST /api/data/structure - 数据结构化',
                'export': 'POST /api/data/export - 导出结构化数据'
            },
            'tasks': {
                'capabilities': 'GET /api/tasks/capabilities - 查看可用任务、后端、Provider 与多选项',
                'task_capability': 'GET /api/tasks/capabilities/<task_type> - 查看单个任务的后端选项',
                'execute': 'POST /api/tasks/execute - 统一任务执行入口'
            }
        }
    })


@app.route('/api/system/status', methods=['GET'])
def system_status():
    """Lightweight API status endpoint that does not initialize lazy services."""

    return jsonify({
        'success': True,
        'data': {
            'app': {
                'name': 'History Research AI Tools',
                'version': '1.1.0',
            },
            'services': get_service_status(),
            'task_manager': {
                'initialized': _task_manager is not None,
            },
            'privacy': {
                'redacted_status_only': True,
                'does_not_initialize_lazy_services': True,
                'does_not_expose_secret_values': True,
            },
        },
    })


@app.route('/api/tasks/capabilities', methods=['GET'])
def list_task_capabilities():
    """统一任务能力发现接口"""
    try:
        manager = _get_task_manager()
        return jsonify({
            'success': True,
            'data': {
                'tasks': manager.get_available_tasks(detailed=True),
                'providers': manager.get_available_providers(detailed=True),
                'default_mode': manager.mode,
                'default_provider': manager.provider,
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/capabilities/<task_type>', methods=['GET'])
def get_task_capability(task_type):
    """查询单个任务的能力和后端选项"""
    try:
        manager = _get_task_manager()
        return jsonify({
            'success': True,
            'data': manager.get_task_options(task_type)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/execute', methods=['POST'])
def execute_task():
    """统一任务执行接口"""
    try:
        data = request.get_json() or {}
        task_type = data.get('task_type')
        if not task_type:
            return jsonify({'error': '未提供 task_type'}), 400

        manager = _get_task_manager()
        requested_mode = data.get('mode')
        requested_provider = data.get('provider')
        if requested_mode:
            manager.set_mode(requested_mode)
        if requested_provider:
            manager.set_provider(requested_provider)

        task_input = data.get('input')
        if task_input is None:
            task_input = {
                key: value
                for key, value in data.items()
                if key not in {
                    'task_type',
                    'input',
                    'preset',
                    'mode',
                    'provider',
                }
            }

        runtime_kwargs = {}
        for key in [
            'provider',
            'model',
            'backend',
            'temperature',
            'max_tokens',
            'timeout',
            'max_retries',
            'cache_enabled',
            'fallback_backends',
            'preferred_providers',
            'extra_params',
        ]:
            if key in data:
                runtime_kwargs[key] = data[key]

        result = manager.execute_task_package(
            task_type,
            preset=data.get('preset'),
            **task_input,
            **runtime_kwargs,
        )
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doc/parse', methods=['POST'])
def parse_docx():
    """Word文档解析接口"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件类型'}), 400

        file_bytes = file.read()
        result = doc_processor.extract_text_from_bytes(file_bytes)

        return jsonify({
            'success': True,
            'data': result,
            'message': '文档解析成功'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doc/polish', methods=['POST'])
def polish_document():
    """学术论文润色接口"""
    try:
        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({'error': '未提供文本内容'}), 400

        text = data['text']
        language = data.get('language', 'zh')

        polished_text = llm_client.academic_polish(text, language)

        return jsonify({
            'success': True,
            'original': text,
            'polished': polished_text.get('content', text),
            'usage': polished_text.get('usage', {})
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doc/verify-historical-citations', methods=['POST'])
def verify_historical_citations():
    """史料引文核对接口"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文档文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400
        if not file.filename.lower().endswith('.docx'):
            return jsonify({'error': '仅支持 docx 文件'}), 400

        unique_id = uuid.uuid4().hex[:8]
        temp_dir = os.path.join(config['default'].TEMP_DIR, f'historical_citation_{unique_id}')
        os.makedirs(temp_dir, exist_ok=True)

        filename = secure_filename(file.filename) or f'citation_{unique_id}.docx'
        temp_docx_path = os.path.join(temp_dir, filename)
        file.save(temp_docx_path)

        result = historical_citation_verifier.verify_docx(
            temp_docx_path,
            search_ndl=_parse_bool(request.form.get('search_ndl'), True),
            download_source=_parse_bool(request.form.get('download_source'), False),
            restricted_download=_parse_bool(request.form.get('restricted_download'), False),
            max_search_results=_parse_int(request.form.get('max_search_results'), 5) or 5,
            page_window=_parse_int(request.form.get('page_window'), 4) or 4,
            ocr_model=request.form.get('ocr_model', OCRModelType.NDLOCR_LITE.value),
            output_dir=os.path.join(config['default'].OUTPUT_DIR, 'historical_citation_verification', unique_id),
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doc/historical-citation-package', methods=['POST'])
def historical_citation_package():
    """工作区统一历史引文 package 接口，默认离线解析。"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文档文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        unique_id = uuid.uuid4().hex[:8]
        temp_dir = os.path.join(config['default'].TEMP_DIR, f'historical_citation_package_{unique_id}')
        os.makedirs(temp_dir, exist_ok=True)

        filename = secure_filename(file.filename) or f'citation_{unique_id}.docx'
        temp_docx_path = os.path.join(temp_dir, filename)
        file.save(temp_docx_path)

        action = request.form.get('action', 'parse')
        output_dir = os.path.join(config['default'].OUTPUT_DIR, 'historical_citation_packages', unique_id)
        result = historical_citation_workspace.build_package(
            file_path=temp_docx_path,
            action=action,
            include_unquoted=_parse_bool(request.form.get('include_unquoted'), False),
            search_ndl=_parse_bool(request.form.get('search_ndl'), False),
            download_source=_parse_bool(request.form.get('download_source'), False),
            restricted_download=_parse_bool(request.form.get('restricted_download'), False),
            max_search_results=_parse_int(request.form.get('max_search_results'), 5) or 5,
            page_window=_parse_int(request.form.get('page_window'), 4) or 4,
            ocr_model=request.form.get('ocr_model', OCRModelType.NDLOCR_LITE.value),
            output_dir=output_dir,
        )

        return jsonify(result), 200 if result.get('success') else 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doc/generate', methods=['POST'])
def generate_docx():
    """生成Word文档接口"""
    try:
        data = request.get_json()

        if not data or 'content' not in data:
            return jsonify({'error': '未提供文档内容'}), 400

        content = data['content']
        output_filename = data.get('filename', f'output_{uuid.uuid4().hex[:8]}.docx')
        output_path = os.path.join(config['default'].OUTPUT_DIR, output_filename)

        doc_processor.create_document(content, output_path)

        return send_file(
            output_path,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=output_filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/info', methods=['GET'])
def get_pdf_info():
    """获取PDF文档信息"""
    try:
        pdf_path = request.args.get('path')

        if not pdf_path:
            return jsonify({'error': '未提供PDF文件路径'}), 400

        if not os.path.exists(pdf_path):
            return jsonify({'error': '文件不存在'}), 404

        info = pdf_processor.get_page_info(pdf_path)

        return jsonify({
            'success': True,
            'data': info
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/convert', methods=['POST'])
def convert_pdf_to_images():
    """PDF转图片接口"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        dpi = request.form.get('dpi', config['default'].PDF_DPI, type=int)
        format_type = request.form.get('format', config['default'].PDF_FORMAT)

        unique_id = uuid.uuid4().hex[:8]
        temp_dir = os.path.join(config['default'].TEMP_DIR, f'pdf_{unique_id}')
        os.makedirs(temp_dir, exist_ok=True)

        temp_pdf_path = os.path.join(temp_dir, 'input.pdf')
        file.save(temp_pdf_path)

        image_paths = pdf_processor.pdf_to_images(
            temp_pdf_path,
            output_dir=temp_dir,
            dpi=dpi,
            format=format_type
        )

        return jsonify({
            'success': True,
            'data': {
                'image_count': len(image_paths),
                'images': [os.path.basename(p) for p in image_paths],
                'temp_dir': temp_dir
            },
            'message': f'成功转换{len(image_paths)}页'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/analyze-layout', methods=['POST'])
def analyze_pdf_layout():
    """PDF版面分析接口"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        unique_id = uuid.uuid4().hex[:8]
        temp_dir = os.path.join(config['default'].TEMP_DIR, f'layout_{unique_id}')
        os.makedirs(temp_dir, exist_ok=True)

        temp_pdf_path = os.path.join(temp_dir, 'input.pdf')
        file.save(temp_pdf_path)

        image_paths = pdf_processor.pdf_to_images(temp_pdf_path, temp_dir)

        layout_results = []
        for image_path in image_paths:
            layout = pdf_processor.analyze_layout(image_path)
            layout_results.append({
                'page': len(layout_results) + 1,
                'image': os.path.basename(image_path),
                'layout': layout
            })

        return jsonify({
            'success': True,
            'data': {
                'pages': layout_results,
                'total_pages': len(layout_results)
            },
            'message': '版面分析完成'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr/extract', methods=['POST'])
def ocr_extract():
    """OCR文字识别接口 - 支持多种OCR引擎路由"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        engine = request.form.get('engine', 'tesseract')
        language = request.form.get('language', config['default'].OCR_LANGUAGE)

        unique_id = uuid.uuid4().hex[:8]
        temp_path = os.path.join(config['default'].TEMP_DIR, f'ocr_{unique_id}_{file.filename}')
        file.save(temp_path)

        try:
            if engine == 'tesseract':
                # Tesseract OCR
                file_bytes = open(temp_path, 'rb').read()
                result = ocr_processor.extract_text_from_bytes(file_bytes, language)
                if result['success']:
                    cleaned_text = data_structurer.clean_text(result['text'])
                    return jsonify({
                        'success': True,
                        'text': cleaned_text,
                        'raw_text': result['text'],
                        'language': language,
                        'method': 'tesseract',
                        'message': 'Tesseract OCR识别成功'
                    })
                else:
                    return jsonify({'success': False, 'error': result.get('error', 'OCR识别失败')}), 500

            elif engine in ('ndlocr-lite', 'ndlkotenocr-lite'):
                # NDL OCR-Lite / NDL 古典籍 OCR-Lite
                model_type = 'ndlocr_lite' if engine == 'ndlocr-lite' else 'ndlkotenocr_lite'
                temp_output_dir = os.path.join(config['default'].TEMP_DIR, f'ndlocr_out_{unique_id}')
                os.makedirs(temp_output_dir, exist_ok=True)

                ocr_result = unified_ocr_processor.process_image(temp_path, model_type, temp_output_dir)

                if ocr_result.success:
                    return jsonify({
                        'success': True,
                        'text': ocr_result.text,
                        'pages': ocr_result.pages,
                        'structures': ocr_result.structures,
                        'processing_time': ocr_result.processing_time,
                        'method': engine,
                        'model_type': model_type,
                        'message': f'{ocr_result.model_description}识别成功'
                    })
                else:
                    return jsonify({'success': False, 'error': ocr_result.error or f'{engine}识别失败'}), 500

            elif engine == 'qwen-vl-ocr':
                # 通义千问VL OCR
                result = ocr_processor.llm_ocr(temp_path, llm_client, language)
                if result['success']:
                    return jsonify({
                        'success': True,
                        'text': result['text'],
                        'method': 'qwen-vl-ocr',
                        'language': language,
                        'message': '通义千问VL OCR识别成功'
                    })
                else:
                    return jsonify({'success': False, 'error': result.get('error', 'VL OCR识别失败')}), 500

            else:
                return jsonify({'error': f'不支持的OCR引擎: {engine}'}), 400

        finally:
            # 清理临时文件
            try:
                os.remove(temp_path)
            except:
                pass
            import shutil
            try:
                shutil.rmtree(os.path.dirname(temp_path.replace(file.filename, '').replace(f'ocr_{unique_id}_', 'ndlocr_out_')), ignore_errors=True)
            except:
                pass

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr/llm', methods=['POST'])
def llm_assisted_ocr():
    """大语言模型辅助OCR接口"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        language = request.form.get('language', 'zh')

        unique_id = uuid.uuid4().hex[:8]
        temp_path = os.path.join(config['default'].TEMP_DIR, f'ocr_{unique_id}_{file.filename}')
        file.save(temp_path)

        result = ocr_processor.llm_ocr(temp_path, llm_client, language)

        os.remove(temp_path)

        if result['success']:
            return jsonify({
                'success': True,
                'text': result['text'],
                'method': 'llm',
                'language': language,
                'message': 'LLM OCR识别成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'LLM OCR识别失败')
            }), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/structure', methods=['POST'])
def structure_data():
    """数据结构化接口"""
    try:
        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({'error': '未提供文本内容'}), 400

        text = data['text']
        structure_type = data.get('type', 'general')

        result = data_structurer.structure_text(text, structure_type)

        return jsonify({
            'success': True,
            'data': result,
            'message': '数据处理完成'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/export', methods=['POST'])
def export_structured_data():
    """导出结构化数据接口"""
    try:
        data = request.get_json()

        if not data or 'content' not in data:
            return jsonify({'error': '未提供数据内容'}), 400

        content = data['content']
        output_format = data.get('format', 'json')
        filename = data.get('filename', f'output_{uuid.uuid4().hex[:8]}')

        result = data_structurer.export_structured_data(content, output_format)

        if output_format == 'json':
            return jsonify({
                'success': True,
                'data': result,
                'format': 'json'
            })
        elif output_format == 'csv':
            return jsonify({
                'success': True,
                'data': 'CSV文件已生成',
                'format': 'csv'
            })
        else:
            return jsonify({
                'success': True,
                'data': result,
                'format': output_format
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr/batch', methods=['POST'])
def batch_ocr():
    """批量OCR处理接口"""
    try:
        if 'files' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        files = request.files.getlist('files')

        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': '未提供文件'}), 400

        language = request.form.get('language', config['default'].OCR_LANGUAGE)
        method = request.form.get('method', 'tesseract')

        unique_id = uuid.uuid4().hex[:8]
        temp_dir = os.path.join(config['default'].TEMP_DIR, f'batch_{unique_id}')
        os.makedirs(temp_dir, exist_ok=True)

        results = []

        for file in files:
            if file.filename == '':
                continue

            temp_path = os.path.join(temp_dir, file.filename)
            file.save(temp_path)

            if method == 'llm':
                result = ocr_processor.llm_ocr(temp_path, llm_client, language)
            else:
                result = ocr_processor.extract_text_from_image(temp_path, language)

            results.append({
                'filename': file.filename,
                'success': result['success'],
                'text': result.get('text', ''),
                'error': result.get('error', '')
            })

            os.remove(temp_path)

        merged_text = data_structurer.merge_ocr_results(results)

        return jsonify({
            'success': True,
            'results': results,
            'merged_text': merged_text,
            'total': len(results),
            'message': f'处理完成{len(results)}个文件'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr/ndlocr-lite', methods=['POST'])
def ndlocr_lite_ocr():
    """NDL OCR-Lite文字识别接口"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        use_gpu = request.form.get('use_gpu', str(config['default'].NDLOCR_LITE_GPU)).lower() == 'true'
        enable_viz = request.form.get('enable_viz', str(config['default'].NDLOCR_LITE_VIZ)).lower() == 'true'

        unique_id = uuid.uuid4().hex[:8]
        temp_dir = os.path.join(config['default'].TEMP_DIR, f'ndlocr_{unique_id}')
        os.makedirs(temp_dir, exist_ok=True)

        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)

        result = ocr_processor.ndlocr_lite_ocr(temp_path, use_gpu=use_gpu, enable_viz=enable_viz)

        if result['success']:
            return jsonify({
                'success': True,
                'text': result.get('text', ''),
                'structured_data': result.get('structured_data', {}),
                'pages': result.get('pages', []),
                'statistics': result.get('statistics', {}),
                'method': 'ndlocr-lite',
                'output_dir': result.get('output_dir', ''),
                'visualization_available': len(result.get('visualization_paths', [])) > 0,
                'message': 'NDL OCR-Lite识别成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '识别失败')
            }), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr/ndlocr-lite/status', methods=['GET'])
def ndlocr_lite_status():
    """获取NDL OCR-Lite状态信息"""
    try:
        status = {
            'available': ocr_processor.is_ndlocr_lite_available(),
            'supported_methods': ocr_processor.get_supported_methods(),
            'current_method': 'ndlocr-lite'
        }

        if status['available']:
            from modules.ndlocr_lite import NDLOCRLiteProcessor
            processor = NDLOCRLiteProcessor()
            status.update(processor.get_status())

        return jsonify({
            'success': True,
            'data': status
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr/models', methods=['GET'])
def get_ocr_models():
    """获取所有可用的OCR模型"""
    try:
        available_models = unified_ocr_processor.get_available_models()

        return jsonify({
            'success': True,
            'data': {
                'models': available_models,
                'default_model': config['default'].DEFAULT_OCR_MODEL
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr/model/process', methods=['POST'])
def ocr_model_process():
    """使用指定模型进行OCR处理"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        model_type = request.form.get('model_type', config['default'].DEFAULT_OCR_MODEL)
        unique_id = uuid.uuid4().hex[:8]

        temp_path = os.path.join(config['default'].TEMP_DIR, f'ocr_{unique_id}_{file.filename}')
        file.save(temp_path)

        temp_output_dir = os.path.join(config['default'].TEMP_DIR, f'ocr_output_{unique_id}')

        result = unified_ocr_processor.process_image(temp_path, model_type, temp_output_dir)

        if result.success:
            try:
                os.remove(temp_path)
            except:
                pass

            return jsonify({
                'success': True,
                'data': {
                    'text': result.text,
                    'pages': result.pages,
                    'structures': result.structures,
                    'processing_time': result.processing_time,
                    'model_type': result.model_type,
                    'model_description': result.model_description,
                    'visualization_paths': result.visualization_paths
                },
                'method': model_type,
                'message': f'{result.model_description}识别成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error or 'OCR识别失败'
            }), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr/model/compare', methods=['POST'])
def ocr_model_compare():
    """对比两种模型的OCR结果"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        unique_id = uuid.uuid4().hex[:8]
        temp_path = os.path.join(config['default'].TEMP_DIR, f'ocr_compare_{unique_id}_{file.filename}')
        file.save(temp_path)

        results = unified_ocr_processor.compare_models(temp_path)

        try:
            os.remove(temp_path)
        except:
            pass

        comparison_data = {}
        for model_type, result in results.items():
            comparison_data[model_type] = {
                'success': result.success,
                'text': result.text,
                'processing_time': result.processing_time,
                'model_description': result.model_description,
                'error': result.error
            }

        return jsonify({
            'success': True,
            'data': {
                'comparison': comparison_data,
                'file_analyzed': file.filename
            },
            'message': '模型对比完成'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doc/pipeline', methods=['POST'])
def document_processing_pipeline():
    """文档处理完整流程"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        language = request.form.get('language', 'zh')

        file_bytes = file.read()
        parsed_doc = doc_processor.extract_text_from_bytes(file_bytes)

        full_text = '\n\n'.join([p['text'] for p in parsed_doc.get('paragraphs', [])])

        polished_result = llm_client.academic_polish(full_text, language)

        polished_paragraphs = []
        for para in parsed_doc.get('paragraphs', []):
            para_text = para['text']
            if para_text in full_text:
                start_idx = full_text.find(para_text)
                if start_idx >= 0:
                    end_idx = start_idx + len(para_text)
                    para_polished = polished_result.get('content', full_text)[start_idx:end_idx]
                    polished_paragraphs.append({
                        'text': para_polished if para_polished else para_text,
                        'style': para.get('style', 'Normal'),
                        'alignment': para.get('alignment', 'LEFT')
                    })
                else:
                    polished_paragraphs.append(para)
            else:
                polished_paragraphs.append(para)

        polished_content = {
            'title': parsed_doc.get('title', ''),
            'paragraphs': polished_paragraphs,
            'tables': parsed_doc.get('tables', [])
        }

        unique_id = uuid.uuid4().hex[:8]
        output_filename = f'polished_{unique_id}.docx'
        output_path = os.path.join(config['default'].OUTPUT_DIR, output_filename)

        doc_processor.create_document(polished_content, output_path)

        return send_file(
            output_path,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=output_filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/ocr/pipeline', methods=['POST'])
def pdf_ocr_pipeline():
    """PDF OCR完整处理流程"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        if request.form.get('pipeline_type') in {'pdf_to_ner', 'ner'}:
            _, temp_pdf_path = _save_uploaded_pdf(file, 'pdf_to_ner')
            result = _run_reusable_pdf_to_ner_pipeline(temp_pdf_path, request.form)
            return jsonify({
                'success': result.success,
                'pipeline_type': 'pdf_to_ner',
                'data': _dataclass_payload(result),
                'message': 'PDF 到 NER 工作流完成' if result.success else 'PDF 到 NER 工作流失败'
            }), 200 if result.success else 500

        language = request.form.get('language', 'zh')
        ocr_method = request.form.get('method', 'tesseract')
        output_format = request.form.get('output', 'json')

        unique_id = uuid.uuid4().hex[:8]
        temp_dir = os.path.join(config['default'].TEMP_DIR, f'pipeline_{unique_id}')
        os.makedirs(temp_dir, exist_ok=True)

        temp_pdf_path = os.path.join(temp_dir, 'input.pdf')
        file.save(temp_pdf_path)

        image_paths = pdf_processor.pdf_to_images(temp_pdf_path, temp_dir)

        ocr_results = []
        for image_path in image_paths:
            layout = pdf_processor.analyze_layout(image_path)

            if ocr_method == 'llm':
                ocr_result = ocr_processor.llm_ocr(image_path, llm_client, language)
            else:
                ocr_result = ocr_processor.extract_text_from_image(image_path, language)

            ocr_results.append({
                'page': len(ocr_results) + 1,
                'image': os.path.basename(image_path),
                'layout': layout,
                'ocr': ocr_result
            })

        all_text = '\n\n'.join([r['ocr'].get('text', '') for r in ocr_results if r['ocr'].get('success')])

        structured = data_structurer.structure_text(all_text, 'general')

        if output_format == 'json':
            export_data = {
                'pages': ocr_results,
                'full_text': all_text,
                'structured': structured
            }
            return jsonify({
                'success': True,
                'data': export_data,
                'format': 'json',
                'message': '处理完成'
            })
        else:
            csv_content = data_structurer.to_csv(structured.get('data', []))
            return jsonify({
                'success': True,
                'csv_data': csv_content,
                'format': 'csv',
                'message': '处理完成'
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/ner/pipeline', methods=['POST'])
def pdf_to_ner_pipeline():
    """PDF 到 NER 全流程接口"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        _, temp_pdf_path = _save_uploaded_pdf(file, 'pdf_to_ner')
        result = _run_reusable_pdf_to_ner_pipeline(temp_pdf_path, request.form)

        return jsonify({
            'success': result.success,
            'pipeline_type': 'pdf_to_ner',
            'data': _dataclass_payload(result),
            'message': 'PDF 到 NER 工作流完成' if result.success else 'PDF 到 NER 工作流失败'
        }), 200 if result.success else 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ndl/search', methods=['POST'])
def ndl_search():
    """NDL 搜索接口"""
    try:
        data = _request_payload()
        keyword = data.get('keyword')
        if not keyword:
            return jsonify({'error': '未提供 keyword'}), 400

        max_results = _parse_int(data.get('max_results'), 10)
        use_api = _parse_bool(data.get('use_api'), True)
        headless = _parse_bool(data.get('headless'), True)
        output_dir = data.get('output_dir')

        results = ndl_download_module.search(
            keyword,
            max_results=max_results,
            use_api=use_api,
            headless=headless,
            output_dir=output_dir,
        )

        return jsonify({
            'success': True,
            'keyword': keyword,
            'count': len(results),
            'results': [_dataclass_payload(item) for item in results],
            'message': 'NDL 搜索完成'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ndl/download', methods=['POST'])
def ndl_download():
    """NDL 下载接口"""
    try:
        data = _request_payload()
        keyword = data.get('keyword')
        if not keyword:
            return jsonify({'error': '未提供 keyword'}), 400

        request_model = NDLDownloadRequest(
            keyword=keyword,
            output_dir=data.get('output_dir') or os.path.join(config['default'].OUTPUT_DIR, 'ndl_downloads'),
            filename=data.get('filename'),
            max_results=_parse_int(data.get('max_results'), 5),
            max_attempts=_parse_int(data.get('max_attempts'), 5),
            use_api=_parse_bool(data.get('use_api'), True),
            headless=_parse_bool(data.get('headless'), True),
            restricted=_parse_bool(data.get('restricted'), False),
            result_index=_parse_int(data.get('result_index'), 0),
        )

        outcome = ndl_download_module.download(request_model)

        return jsonify({
            'success': outcome.success,
            'data': _dataclass_payload(outcome),
            'message': 'NDL 下载完成' if outcome.success else 'NDL 下载失败'
        }), 200 if outcome.success else 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────
#  工作流 API（Phase 4）
# ─────────────────────────────────────────────────────────

import json
import uuid
from datetime import datetime

# WorkflowOrchestrator lazy import（避免循环导入）
_workflow_cache = {}  # project_id → WorkflowOrchestrator instance


def _get_workflow_orchestrator(topic: str = None, language: str = "en",
                                bilingual: bool = True,
                                citation_format: str = "chicago",
                                output_dir: str = "./workflow_output"):
    """获取或创建 WorkflowOrchestrator 实例"""
    from tools.workflow import WorkflowOrchestrator
    return WorkflowOrchestrator(
        topic=topic,
        language=language,
        bilingual=bilingual,
        citation_format=citation_format,
        output_dir=output_dir,
    )


@app.route('/api/workflow/run', methods=['POST'])
def workflow_run():
    """
    执行历史研究论文工作流

    POST body (JSON):
        topic: str           - 研究主题
        language: str         - 主要语言 (en/ja/zh)
        bilingual: bool       - 是否生成双语版本
        citation_format: str   - 引用格式 (chicago/apa/gb7714/mla)
        run_stages: list[int] - 要执行的阶段列表，默认 [1,2,3,4,5,6,7]
        stage_options: dict    - 各阶段可选参数
    """
    try:
        data = request.get_json() or {}
        topic = data.get('topic', 'Untitled Research')
        language = data.get('language', 'en')
        bilingual = data.get('bilingual', True)
        citation_format = data.get('citation_format', 'chicago')
        run_stages = data.get('run_stages', [1, 2, 3, 4, 5, 6, 7])
        stage_options = data.get('stage_options', {})

        print(f"[Workflow API] 启动工作流 | 主题: {topic} | 语言: {language} | 阶段: {run_stages}")

        # 创建工作流
        wf = _get_workflow_orchestrator(
            topic=topic,
            language=language,
            bilingual=bilingual,
            citation_format=citation_format,
        )
        project_id = wf.project.id
        _workflow_cache[project_id] = wf

        # 按顺序执行各阶段
        results = {}
        for stage_num in run_stages:
            opts = stage_options.get(str(stage_num), {})
            try:
                result = wf.run_stage(stage_num, **opts)
                results[stage_num] = {'status': 'done', 'result': str(result)[:200]}
            except Exception as e:
                results[stage_num] = {'status': 'failed', 'error': str(e)}
                print(f"[Workflow API] Stage {stage_num} 失败: {e}")

        # 构建响应
        response_data = {
            'success': True,
            'project_id': project_id,
            'topic': topic,
            'stages_completed': run_stages,
            'results': results,
            'summary': wf.project.summary(),
            'files': {
                'draft': './workflow_output/paper_draft.md',
                'final': './workflow_output/final_paper.md',
            },
        }

        # 如果有最终论文，附带摘要
        if wf.project.final_paper:
            response_data['final_paper_preview'] = wf.project.final_paper[:500]
        elif wf.project.paper_draft:
            response_data['paper_draft_preview'] = wf.project.paper_draft[:500]

        return jsonify(response_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/stage/<int:stage_num>', methods=['POST'])
def workflow_run_single_stage(stage_num: int):
    """
    执行单个工作流阶段

    POST body (JSON):
        project_id: str (可选) - 已有项目ID，用于断点续做
        topic: str              - 研究主题（project_id 不存在时必填）
        language: str           - 主要语言
        ... 其他 WorkflowOrchestrator 参数

        **kwargs: 各阶段额外参数
    """
    try:
        data = request.get_json() or {}
        project_id = data.pop('project_id', None)
        stage_options = data.pop('stage_options', {})

        # 断点续做或新建
        if project_id and project_id in _workflow_cache:
            wf = _workflow_cache[project_id]
            print(f"[Workflow API] 恢复项目 {project_id}，继续 Stage {stage_num}")
        else:
            topic = data.get('topic', 'Untitled Research')
            language = data.get('language', 'en')
            bilingual = data.get('bilingual', True)
            citation_format = data.get('citation_format', 'chicago')
            wf = _get_workflow_orchestrator(
                topic=topic, language=language,
                bilingual=bilingual, citation_format=citation_format,
            )
            project_id = wf.project.id
            _workflow_cache[project_id] = wf
            print(f"[Workflow API] 新建项目 {project_id}，执行 Stage {stage_num}")

        # 执行单阶段
        opts = stage_options.get(str(stage_num), {})
        result = wf.run_stage(stage_num, **opts)

        return jsonify({
            'success': True,
            'project_id': project_id,
            'stage': stage_num,
            'status': 'done',
            'result_preview': str(result)[:300] if result else None,
            'project_summary': wf.project.summary(),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'stage': stage_num}), 500


@app.route('/api/workflow/project/<project_id>', methods=['GET'])
def workflow_get_project(project_id: str):
    """获取项目状态和产出"""
    try:
        if project_id not in _workflow_cache:
            return jsonify({'error': '项目不存在或已过期'}), 404

        wf = _workflow_cache[project_id]
        p = wf.project

        return jsonify({
            'success': True,
            'project_id': project_id,
            'topic': p.topic,
            'language': p.language,
            'bilingual': p.bilingual,
            'stage_status': {
                'stage1': p.stage1_status.value,
                'stage2': p.stage2_status.value,
                'stage3': p.stage3_status.value,
                'stage4': p.stage4_status.value,
                'stage5': p.stage5_status.value,
                'stage6': p.stage6_status.value,
                'stage7': p.stage7_status.value,
            },
            'outputs': {
                'literature_count': len(p.literature),
                'entities_count': len(p.entities),
                'paper_draft_chars': len(p.paper_draft),
                'polished_draft_chars': len(p.polished_draft),
                'final_paper_chars': len(p.final_paper),
            },
            'paper_draft_preview': p.paper_draft[:300] if p.paper_draft else None,
            'final_paper_preview': p.final_paper[:300] if p.final_paper else None,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/save', methods=['POST'])
def workflow_save_project():
    """
    保存项目到文件（断点续做）

    POST body (JSON):
        project_id: str - 项目ID
        path: str        - 保存路径（可选）
    """
    try:
        data = request.get_json() or {}
        project_id = data.get('project_id')
        save_path = data.get('path', '')

        if not project_id or project_id not in _workflow_cache:
            return jsonify({'error': '项目不存在'}), 404

        wf = _workflow_cache[project_id]
        if not save_path:
            save_path = wf._get_save_path()

        wf.project.save(save_path)
        return jsonify({
            'success': True,
            'project_id': project_id,
            'saved_path': save_path,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/load', methods=['POST'])
def workflow_load_project():
    """
    从文件加载项目

    POST body (JSON):
        path: str - 项目 JSON 文件路径
    """
    try:
        data = request.get_json() or {}
        path = data.get('path')
        if not path:
            return jsonify({'error': '未提供 path'}), 400

        from tools.workflow import WorkflowOrchestrator
        wf = WorkflowOrchestrator.load(path)
        _workflow_cache[wf.project.id] = wf

        return jsonify({
            'success': True,
            'project_id': wf.project.id,
            'topic': wf.project.topic,
            'summary': wf.project.summary(),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/stages', methods=['GET'])
def workflow_stages_info():
    """获取所有阶段信息"""
    from tools.workflow import WorkflowOrchestrator
    return jsonify({
        'stages': [
            {'num': 1, 'name': '搜集材料', 'description': '使用 HistoryFieldExplorer 搜集学术文献'},
            {'num': 2, 'name': '整理史料', 'description': '生成 Obsidian 笔记 + 格式化引用'},
            {'num': 3, 'name': '提取信息', 'description': 'NER 实体提取 + 关系识别'},
            {'num': 4, 'name': '史料考察', 'description': '引文网络分析 + 论文逻辑审视'},
            {'num': 5, 'name': '撰写论文', 'description': '生成研究论文（含双语翻译）'},
            {'num': 6, 'name': '论文修改润色', 'description': '精简冗余 + 文风迁移'},
            {'num': 7, 'name': '注释格式修改', 'description': '引用格式转换（Chicago/APA/GB7714等）'},
        ],
        'formats': ['chicago', 'apa', 'gb7714', 'mla', 'ieee', 'harvard'],
        'languages': [{'code': 'en', 'name': 'English'}, {'code': 'ja', 'name': '日本語'}, {'code': 'zh', 'name': '中文'}],
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

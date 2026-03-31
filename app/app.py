from flask import Flask, request, jsonify, send_file
import os
import uuid
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
from modules.unified_ocr_processor import UnifiedOCRProcessor, UnifiedOCRConfig, OCRModelType


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = config['default'].MAX_CONTENT_LENGTH

doc_processor = DocProcessor()
llm_client = LLMClient(config['default'].LLM_CONFIG)
pdf_processor = PDFProcessor(config['default'].OUTPUT_DIR)
ocr_processor = OCRProcessor(config['default'].TESSERACT_PATH)
data_structurer = DataStructurer()

unified_ocr_config = UnifiedOCRConfig(
    ndlocr_path=config['default'].NDLOCR_LITE_PATH or None,
    ndlkoten_path=config['default'].NDLKOTENOCR_LITE_PATH or None,
    use_gpu=config['default'].NDLOCR_LITE_GPU,
    enable_visualization=config['default'].NDLOCR_LITE_VIZ,
    timeout=config['default'].NDLOCR_LITE_TIMEOUT,
    default_model=config['default'].DEFAULT_OCR_MODEL
)
unified_ocr_processor = UnifiedOCRProcessor(unified_ocr_config)


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config['default'].ALLOWED_EXTENSIONS


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
                'generate': 'POST /api/doc/generate - 生成Word文档'
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
            }
        }
    })


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
    """OCR文字识别接口"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未提供文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        language = request.form.get('language', config['default'].OCR_LANGUAGE)

        file_bytes = file.read()
        result = ocr_processor.extract_text_from_bytes(file_bytes, language)

        if result['success']:
            cleaned_text = data_structurer.clean_text(result['text'])
            return jsonify({
                'success': True,
                'text': cleaned_text,
                'raw_text': result['text'],
                'language': language,
                'message': 'OCR识别成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'OCR识别失败')
            }), 500

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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

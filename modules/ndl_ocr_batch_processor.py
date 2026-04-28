"""
NDL OCR批量处理器模块

专门用于调用NDL OCR系列模型进行批量图片识别
与pdf_processor.py保持独立，仅在对NDL OCR系列模型时使用
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import time


class NDLOCRBatchProcessor:
    """NDL OCR批量处理器"""

    def __init__(self, ndlocr_path: Optional[str] = None, strict: bool = False):
        """
        初始化批量处理器

        Args:
            ndlocr_path: NDL OCR可执行文件路径
            strict: 是否在 NDL OCR 不可用时直接抛出异常
        """
        self.base_dir = Path(__file__).parent.parent

        if ndlocr_path:
            self.ndlocr_path = Path(ndlocr_path)
        else:
            self.ndlocr_path = self.base_dir / "ndlocr-lite" / "src" / "ocr.py"

        self.results = []
        self.available = self._validate_ndlocr(strict=strict)
        self.availability_message = (
            "NDL OCR可用"
            if self.available
            else self._build_installation_message()
        )

    def _build_installation_message(self) -> str:
        return (
            f"NDL OCR未找到: {self.ndlocr_path}\n"
            f"请先安装NDL OCR:\n"
            f"  git clone https://github.com/ndl-lab/ndlocr-lite\n"
            f"  cd ndlocr-lite\n"
            f"  pip install -r requirements.txt"
        )

    def _validate_ndlocr(self, strict: bool = False) -> bool:
        """
        验证NDL OCR是否可用

        Returns:
            bool: 是否可用
        """
        if not self.ndlocr_path.exists():
            if strict:
                raise FileNotFoundError(self._build_installation_message())
            return False
        return True

    def get_capabilities(self) -> Dict[str, Any]:
        """返回批量 OCR 能力快照，供任务层/agent 选择后端。"""
        return {
            "module": "NDLOCRBatchProcessor",
            "task": "ocr_batch",
            "available": self.available,
            "backend_options": [
                {
                    "backend": "local_engine",
                    "provider": "ndlocr_batch",
                    "model": "ndlocr-lite",
                    "available": self.available,
                    "requires": [str(self.ndlocr_path)],
                    "input_formats": ["png"],
                    "output_type": "ocr_batch",
                }
            ],
            "fallback_order": [
                "unified_ocr_processor",
                "ndlocr_lite",
                "llm_ocr_processor",
                "ocr_processor",
                "skill",
                "mcp",
            ],
            "quality_signals": [
                "engine_unavailable",
                "no_images",
                "page_failures",
                "no_successful_pages",
                "empty_text",
            ],
            "message": self.availability_message,
        }

    def process_image(self, image_path: str, output_dir: str,
                    timeout: int = 60) -> Tuple[bool, str]:
        """
        处理单张图片

        Args:
            image_path: 图片路径
            output_dir: 输出目录
            timeout: 超时时间（秒）

        Returns:
            Tuple[bool, str]: (是否成功, 错误信息或识别文本)
        """
        image_path = Path(image_path)
        output_dir = Path(output_dir)

        if not self.available:
            return False, self.availability_message

        if not image_path.exists():
            return False, f"图片文件不存在: {image_path}"

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            python_exe = sys.executable
            cmd = [
                python_exe,
                str(self.ndlocr_path),
                "--sourceimg", str(image_path),
                "--output", str(output_dir)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                txt_file = output_dir / f"{image_path.stem}.txt"
                if txt_file.exists():
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        text = f.read()
                    return True, text
                else:
                    return False, "输出文件未生成"
            else:
                error_msg = result.stderr if result.stderr else "未知错误"
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "处理超时"
        except Exception as e:
            return False, str(e)

    def process_batch(self, image_dir: str, output_dir: str,
                    max_pages: Optional[int] = None,
                    timeout: int = 60,
                    progress_callback=None) -> List[Dict[str, Any]]:
        """
        批量处理图片

        Args:
            image_dir: 图片目录
            output_dir: 输出目录
            max_pages: 最大处理页数（None表示全部）
            timeout: 单张处理超时（秒）
            progress_callback: 进度回调函数 callback(current, total, result)

        Returns:
            List[Dict]: 处理结果列表
        """
        image_dir = Path(image_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        image_files = sorted(image_dir.glob("*.png"))

        if max_pages:
            image_files = image_files[:max_pages]

        print(f"\n开始批量OCR处理")
        print(f"图片数量: {len(image_files)}")
        print(f"输出目录: {output_dir}")

        results = []
        start_time = time.time()

        for i, img_path in enumerate(image_files, 1):
            page_num = i
            output_subdir = output_dir / f"page_{page_num:04d}"

            result = {
                'page': page_num,
                'filename': img_path.name,
                'success': False,
                'text': '',
                'char_count': 0,
                'output_path': str(output_subdir),
                'error': None
            }

            print(f"[{i:2d}/{len(image_files)}] {img_path.name}...", end=" ", flush=True)

            success, text_or_error = self.process_image(
                str(img_path),
                str(output_subdir),
                timeout
            )

            if success:
                result['success'] = True
                result['text'] = text_or_error
                result['char_count'] = len(text_or_error)
                print(f"✓ ({len(text_or_error)} 字符)")
            else:
                result['error'] = text_or_error
                print(f"✗")

            results.append(result)

            if progress_callback:
                progress_callback(i, len(image_files), result)

        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r['success'])

        print(f"\n处理完成:")
        print(f"  成功: {success_count}/{len(results)}")
        print(f"  耗时: {elapsed:.1f}秒")
        print(f"  平均: {elapsed/len(results):.1f}秒/页" if results else "  平均: 0.0秒/页")

        self.results = results
        return results

    def process_batch_package(self, image_dir: str, output_dir: str,
                              max_pages: Optional[int] = None,
                              timeout: int = 60,
                              progress_callback=None) -> Dict[str, Any]:
        """批量处理图片并返回统一 `ocr_batch` envelope。"""
        image_path = Path(image_dir)
        output_path = Path(output_dir)

        if not self.available:
            return self._build_batch_package(
                [],
                image_path,
                output_path,
                error=self.availability_message,
            )

        if not image_path.exists():
            return self._build_batch_package(
                [],
                image_path,
                output_path,
                error=f"图片目录不存在: {image_path}",
            )

        results = self.process_batch(
            str(image_path),
            str(output_path),
            max_pages=max_pages,
            timeout=timeout,
            progress_callback=progress_callback,
        )
        return self._build_batch_package(results, image_path, output_path)

    def _build_batch_package(self, results: List[Dict[str, Any]],
                             image_dir: Path,
                             output_dir: Path,
                             error: Optional[str] = None) -> Dict[str, Any]:
        statistics = self._statistics_from_results(results)
        flags = self._package_quality_flags(results, error)
        return {
            "type": "ocr_batch",
            "schema_version": "2026-04-25",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_path": str(image_dir),
            "output_dir": str(output_dir),
            "backend": "local_engine",
            "provider": "ndlocr_batch",
            "model": "ndlocr-lite",
            "confidence": self._package_confidence(statistics, flags),
            "needs_review": bool(flags),
            "quality_flags": flags,
            "capabilities": self.get_capabilities(),
            "statistics": statistics,
            "pages": [
                self._result_to_page_package(result, image_dir)
                for result in results
            ],
            "artifacts": [
                {
                    "page_number": result.get("page"),
                    "kind": "ocr_output_dir",
                    "path": result.get("output_path"),
                }
                for result in results
                if result.get("output_path")
            ],
            "error": error,
        }

    def _result_to_page_package(self, result: Dict[str, Any],
                                image_dir: Path) -> Dict[str, Any]:
        filename = result.get("filename")
        source_path = str(image_dir / filename) if filename else None
        flags = []
        if not result.get("success"):
            flags.append("page_failed")
        if result.get("success") and not result.get("text"):
            flags.append("empty_text")

        return {
            "page_number": result.get("page"),
            "source_path": source_path,
            "filename": filename,
            "text": result.get("text", ""),
            "char_count": result.get("char_count", 0),
            "success": bool(result.get("success")),
            "confidence": 0.85 if result.get("success") else 0.0,
            "needs_review": bool(flags),
            "quality_flags": flags,
            "error": result.get("error"),
            "artifacts": [
                {
                    "kind": "ocr_output_dir",
                    "path": result.get("output_path"),
                }
            ] if result.get("output_path") else [],
        }

    def _statistics_from_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not results:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "total_chars": 0,
                "avg_chars": 0,
                "success_rate": 0,
            }

        success_results = [r for r in results if r.get("success")]
        total_chars = sum(r.get("char_count", 0) for r in success_results)
        return {
            "total": len(results),
            "success": len(success_results),
            "failed": len(results) - len(success_results),
            "total_chars": total_chars,
            "avg_chars": total_chars / len(success_results) if success_results else 0,
            "success_rate": len(success_results) / len(results) * 100,
        }

    def _package_quality_flags(self, results: List[Dict[str, Any]],
                               error: Optional[str] = None) -> List[str]:
        flags = []
        if error:
            flags.append("batch_error")
        if not self.available:
            flags.append("engine_unavailable")
        if not results and not error:
            flags.append("no_images")
        failed_count = sum(1 for result in results if not result.get("success"))
        if failed_count:
            flags.append("page_failures")
        if results and failed_count == len(results):
            flags.append("no_successful_pages")
        if any(result.get("success") and not result.get("text") for result in results):
            flags.append("empty_text")
        return flags

    def _package_confidence(self, statistics: Dict[str, Any],
                            flags: List[str]) -> float:
        if "engine_unavailable" in flags or "batch_error" in flags:
            return 0.0
        if not statistics.get("total"):
            return 0.0
        return round(float(statistics.get("success_rate", 0)) / 100, 3)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取处理统计

        Returns:
            Dict: 统计信息
        """
        if not self.results:
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'total_chars': 0,
                'avg_chars': 0
            }

        success_results = [r for r in self.results if r['success']]

        return {
            'total': len(self.results),
            'success': len(success_results),
            'failed': len(self.results) - len(success_results),
            'total_chars': sum(r['char_count'] for r in success_results),
            'avg_chars': (
                sum(r['char_count'] for r in success_results) / len(success_results)
                if success_results else 0
            ),
            'success_rate': (
                len(success_results) / len(self.results) * 100
                if self.results else 0
            )
        }


class NDLOCRWorkflow:
    """NDL OCR工作流（PDF转Word）"""

    def __init__(self):
        """初始化工作流"""
        self.base_dir = Path(__file__).parent.parent
        self.batch_processor = NDLOCRBatchProcessor()

    def run_workflow(self, pdf_path: str, output_dir: Optional[str] = None,
                   max_pages: int = 20,
                   dpi: int = 300,
                   generate_word: bool = True) -> Dict[str, Any]:
        """
        运行完整工作流

        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            max_pages: 最大处理页数
            dpi: PDF转图片分辨率
            generate_word: 是否生成Word文档

        Returns:
            Dict: 工作流结果
        """
        from modules.pdf_processor import PDFProcessor
        from modules.doc_processor import DocProcessor
        from modules.ndlocr_result_processor import create_result_processor

        pdf_path = Path(pdf_path)

        if output_dir:
            output_dir = Path(output_dir)
        else:
            output_dir = self.base_dir / "output"

        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        temp_images_dir = self.base_dir / "temp_images"
        ocr_output_dir = output_dir / f"ocr_results_{timestamp}"

        print("="*60)
        print("PDF到Word工作流")
        print("="*60)

        print("\n步骤1: PDF转图片...")
        pdf_processor = PDFProcessor(str(temp_images_dir))

        try:
            image_paths = pdf_processor.pdf_to_images(
                str(pdf_path),
                dpi=dpi
            )
            limited_images = image_paths[:max_pages]
            print(f"✓ 转换完成: {len(limited_images)} 页")
        except Exception as e:
            return {
                'success': False,
                'error': f'PDF转换失败: {e}',
                'step': 'pdf_to_images'
            }

        print("\n步骤2: NDL OCR识别...")
        ocr_results = self.batch_processor.process_batch(
            str(temp_images_dir),
            str(ocr_output_dir),
            max_pages=max_pages
        )

        print("\n步骤3: 数据清洗...")
        cleaner = create_result_processor()

        cleaned_texts = []
        for result in ocr_results:
            if result['success']:
                cleaned = cleaner.clean_text(result['text'])
                cleaned_texts.append(cleaned)

        print(f"✓ 清洗完成: {len(cleaned_texts)} 页")

        workflow_result = {
            'success': True,
            'pdf_path': str(pdf_path),
            'output_dir': str(output_dir),
            'pages_processed': len(limited_images),
            'pages_success': sum(1 for r in ocr_results if r['success']),
            'ocr_results': ocr_results,
            'cleaned_texts': cleaned_texts,
            'ocr_output_dir': str(ocr_output_dir)
        }

        if generate_word:
            print("\n步骤4: 生成Word文档...")

            doc_processor = DocProcessor()

            doc_title = f"{pdf_path.stem}（OCR识别结果）"

            paragraphs = []
            for i, text in enumerate(cleaned_texts, 1):
                paragraphs.append({
                    'text': f"【第 {i} 页】\n\n{text}",
                    'style': 'Normal',
                    'alignment': 'LEFT'
                })

            content = {
                'title': doc_title,
                'paragraphs': paragraphs,
                'tables': []
            }

            word_output = output_dir / f"{pdf_path.stem}_OCR识别结果.docx"

            try:
                doc_processor.create_document(content, str(word_output))
                print(f"✓ Word文档生成成功: {word_output}")
                workflow_result['word_output'] = str(word_output)
            except Exception as e:
                workflow_result['word_doc_error'] = str(e)
                print(f"✗ Word文档生成失败: {e}")

        print("\n" + "="*60)
        print("工作流完成")
        print("="*60)

        stats = self.batch_processor.get_statistics()
        print(f"\n统计:")
        print(f"  处理页数: {stats['total']}")
        print(f"  成功: {stats['success']}")
        print(f"  成功率: {stats['success_rate']:.1f}%")
        print(f"  总字符数: {stats['total_chars']:,}")

        if generate_word and 'word_output' in workflow_result:
            print(f"\n输出文件:")
            print(f"  Word: {workflow_result['word_output']}")

        return workflow_result


def create_batch_processor(ndlocr_path: Optional[str] = None,
                           strict: bool = False) -> NDLOCRBatchProcessor:
    """
    工厂函数 - 创建批量处理器

    Args:
        ndlocr_path: NDL OCR路径
        strict: 是否在 NDL OCR 不可用时直接抛出异常

    Returns:
        NDLOCRBatchProcessor: 批量处理器实例
    """
    return NDLOCRBatchProcessor(ndlocr_path, strict=strict)


def create_workflow() -> NDLOCRWorkflow:
    """
    工厂函数 - 创建工作流

    Returns:
        NDLOCRWorkflow: 工作流实例
    """
    return NDLOCRWorkflow()


if __name__ == "__main__":
    processor = create_batch_processor()

    print("测试批量处理...")
    results = processor.process_batch(
        "test Images",
        "ocr_output",
        max_pages=3
    )

    print("\n统计信息:")
    stats = processor.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

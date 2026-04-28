"""
人物传记处理管道
整合PDF转换、OCR、NER、排序、CSV导出
"""
import os
import sys
import json
import time
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import asdict, dataclass
from datetime import datetime

# 导入子模块
from .biographical_ner import BiographicalNER, PersonEntity


@dataclass
class PipelineConfig:
    """管道配置"""
    pdf_path: str
    output_dir: str
    dpi: int = 300
    use_llm_ocr: bool = False
    llm_api_key: Optional[str] = None
    llm_model: str = "qwen-vl-ocr"
    start_page: Optional[int] = None
    end_page: Optional[int] = None


class BiographyPipeline:
    """传记处理管道"""

    def __init__(self, config: PipelineConfig):
        """
        初始化管道

        Args:
            config: 管道配置
        """
        self.config = config
        self.ner = BiographicalNER()
        self.persons: List[PersonEntity] = []

    def get_capabilities(self) -> Dict[str, Any]:
        """Return an agent/workflow-facing capability snapshot."""
        return {
            "module": "biography_pipeline",
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "layer": "specialized_workflow",
            "input_formats": ["pdf", "ocr_result", "text_blocks"],
            "output_types": ["biography_pipeline_summary", "biography_batch"],
            "capabilities": [
                "pdf_to_image_orchestration",
                "ocr_result_collection",
                "biographical_ner_delegation",
                "csv_json_export",
                "package_output",
            ],
            "fallback_order": ["biography_extractor", "biographical_ner", "local_ocr", "llm_api", "skill", "mcp"],
            "privacy": {
                "offline_by_default": True,
                "llm_ocr_enabled": self.config.use_llm_ocr,
                "api_key_provided": bool(self.config.llm_api_key),
                "secret_file_loading": False,
            },
        }

    def run_ocr(self, image_paths: List[str], progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        运行OCR识别

        Args:
            image_paths: 图片路径列表
            progress_callback: 进度回调

        Returns:
            OCR结果列表
        """
        # TODO: 实现OCR调用
        # 目前先用占位符
        results = []

        for i, img_path in enumerate(image_paths):
            # 占位：实际应该调用ndlocr或LLM OCR
            results.append({
                'image_path': img_path,
                'text': '',
                'blocks': [],
                'success': False,
            })

            if progress_callback:
                progress_callback(i + 1, len(image_paths), f"OCR: {os.path.basename(img_path)}")

        return results

    def parse_vertical_layout(self, text: str) -> List[str]:
        """
        解析竖排版文本
        注意：竖排日文是从右到左、从上到下阅读

        Args:
            text: OCR识别的原始文本

        Returns:
            分割后的文本块列表
        """
        # 竖排文本的特性：
        # 1. 每行是竖的
        # 2. 阅读顺序是从右到左
        # 3. 人物条目之间可能有空行分隔

        blocks = []

        # 按空行分割为块
        raw_blocks = text.split('\n\n')

        for block in raw_blocks:
            block = block.strip()
            if block:
                blocks.append(block)

        return blocks

    def process_page(self, page_num: int, ocr_result: Dict[str, Any]) -> List[PersonEntity]:
        """
        处理单页OCR结果，提取人物信息

        Args:
            page_num: 页码
            ocr_result: OCR结果

        Returns:
            识别的人物列表
        """
        page_persons = []
        text = ocr_result.get('text', '')

        # 解析为文本块
        blocks = self.parse_vertical_layout(text)

        for block_idx, block_text in enumerate(blocks):
            person = self.ner.extract_person_from_block(block_text, page_num, block_idx)
            if person and (person.name or person.work_experiences):
                page_persons.append(person)

        return page_persons

    def process_ocr_results_package(self, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process OCR results through the local biography NER package."""
        blocks: List[Dict[str, Any]] = []
        for index, result in enumerate(ocr_results or [], 1):
            page_num = result.get("page_number") or result.get("page") or index
            text = result.get("text", "")
            for block_idx, block_text in enumerate(self.parse_vertical_layout(text)):
                blocks.append({
                    "text": block_text,
                    "page_num": page_num,
                    "block_idx": block_idx,
                    "source_image": result.get("image_path"),
                })

        entity_package = self.ner.process_text_blocks_package(blocks)
        self.persons = self.ner.get_persons()
        quality_flags = self._pipeline_quality_flags(ocr_results, entity_package)
        return {
            "type": "biography_batch",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": self._estimate_confidence(
                entity_package["summary"].get("person_count", 0),
                quality_flags,
            ),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "persons": entity_package.get("persons", []),
            "summary": {
                "ocr_result_count": len(ocr_results or []),
                "text_block_count": len(blocks),
                "person_count": entity_package["summary"].get("person_count", 0),
                "successful_ocr_results": sum(1 for item in (ocr_results or []) if item.get("success", True)),
            },
            "source_package": entity_package,
            "capabilities": self.get_capabilities(),
        }

    def build_summary_package(
        self,
        *,
        success: bool,
        output_dir: Optional[str] = None,
        artifacts: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build a compact workflow summary package."""
        quality_flags = []
        if not success:
            quality_flags.append("pipeline_failed")
        if errors:
            quality_flags.extend(f"error:{error}" for error in errors[:3])
        if not self.persons:
            quality_flags.append("no_biography_entities")
        quality_flags = sorted(set(quality_flags))
        return {
            "type": "biography_pipeline_summary",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": self._estimate_confidence(len(self.persons), quality_flags),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "success": success,
            "persons": [asdict(person) for person in self.persons],
            "summary": {
                "person_count": len(self.persons),
                "output_dir": output_dir or self.config.output_dir,
                "artifacts": artifacts or {},
            },
            "capabilities": self.get_capabilities(),
        }

    def run(
        self,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        运行完整管道

        Args:
            progress_callback: 进度回调 (当前, 总数, 描述)

        Returns:
            是否成功
        """
        try:
            total_steps = 5
            current_step = 0

            # Step 1: PDF转图片
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, "PDF转图片...")

            images_dir = os.path.join(self.config.output_dir, 'images')
            os.makedirs(images_dir, exist_ok=True)

            from .pdf_image_converter import convert_pdf_to_images

            image_paths = convert_pdf_to_images(
                self.config.pdf_path,
                images_dir,
                dpi=self.config.dpi,
                start_page=self.config.start_page,
                end_page=self.config.end_page,
            )

            if not image_paths:
                print("PDF转图片失败")
                return False

            if progress_callback:
                progress_callback(current_step, total_steps, f"图片转换完成: {len(image_paths)}张")

            # Step 2: OCR识别
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, "OCR识别...")

            ocr_results = self.run_ocr(image_paths, progress_callback)

            # Step 3: NER提取
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, "NER提取...")

            all_persons = []
            for page_num, ocr_result in enumerate(ocr_results, 1):
                page_persons = self.process_page(page_num, ocr_result)
                all_persons.extend(page_persons)

            self.persons = all_persons

            # Step 4: 时间排序
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, "排序工作经历...")

            self.ner.sort_work_experiences_by_date()

            # Step 5: 导出CSV
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, "导出CSV...")

            csv_path = os.path.join(self.config.output_dir, 'biography_data.csv')
            self.export_to_csv(csv_path)

            if progress_callback:
                progress_callback(total_steps, total_steps, f"完成! 共{len(self.persons)}人")

            return True

        except Exception as e:
            print(f"管道执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _pipeline_quality_flags(
        self,
        ocr_results: List[Dict[str, Any]],
        entity_package: Dict[str, Any],
    ) -> List[str]:
        flags: List[str] = []
        if not ocr_results:
            flags.append("no_ocr_results")
        if any(not item.get("success", True) for item in (ocr_results or [])):
            flags.append("ocr_failures_present")
        if any(not item.get("text") for item in (ocr_results or [])):
            flags.append("empty_ocr_text")
        flags.extend(entity_package.get("quality_flags", []))
        return sorted(set(flags))

    def _estimate_confidence(self, person_count: int, quality_flags: List[str]) -> float:
        confidence = 0.45
        if person_count:
            confidence += 0.35
        confidence -= min(0.35, len(set(quality_flags)) * 0.07)
        return round(max(0.1, min(confidence, 0.95)), 2)

    def export_to_csv(self, csv_path: str) -> None:
        """
        导出为CSV文件

        Args:
            csv_path: CSV文件路径
        """
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # 写入表头
            writer.writerow([
                '姓名', '本籍', '学历',
                '工作经历1_单位', '工作经历1_时间', '工作经历1_描述',
                '工作经历2_单位', '工作经历2_时间', '工作经历2_描述',
                '工作经历3_单位', '工作经历3_时间', '工作经历3_描述',
                '页码', '块索引', '原始文本'
            ])

            # 写入数据
            for person in self.persons:
                experiences = person.work_experiences[:3]  # 最多3条

                row = [
                    person.name or '',
                    person.hometown or '',
                    person.education or '',
                ]

                # 添加工作经历
                for i in range(3):
                    if i < len(experiences):
                        exp = experiences[i]
                        row.extend([
                            exp.get('unit', ''),
                            exp.get('date_range', ''),
                            exp.get('description', ''),
                        ])
                    else:
                        row.extend(['', '', ''])

                row.extend([
                    person.page_number or '',
                    person.block_index or '',
                    person.original_text[:100] if person.original_text else '',  # 截断原始文本
                ])

                writer.writerow(row)

        print(f"CSV已导出: {csv_path}")

    def export_to_json(self, json_path: str) -> None:
        """
        导出为JSON文件

        Args:
            json_path: JSON文件路径
        """
        data = {
            'total_persons': len(self.persons),
            'persons': [p.to_dict() if hasattr(p, 'to_dict') else {
                'name': p.name,
                'hometown': p.hometown,
                'education': p.education,
                'work_experiences': p.work_experiences,
                'page_number': p.page_number,
                'block_index': p.block_index,
            } for p in self.persons]
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"JSON已导出: {json_path}")


def run_biography_pipeline(
    pdf_path: str,
    output_dir: str,
    dpi: int = 300,
    use_llm_ocr: bool = False,
    llm_api_key: Optional[str] = None,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    progress_callback: Optional[Callable] = None,
) -> bool:
    """
    运行传记管道的便捷函数

    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        dpi: 图片分辨率
        use_llm_ocr: 是否使用LLM OCR
        llm_api_key: LLM API密钥
        start_page: 起始页
        end_page: 结束页
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    config = PipelineConfig(
        pdf_path=pdf_path,
        output_dir=output_dir,
        dpi=dpi,
        use_llm_ocr=use_llm_ocr,
        llm_api_key=llm_api_key,
        start_page=start_page,
        end_page=end_page,
    )

    pipeline = BiographyPipeline(config)
    return pipeline.run(progress_callback)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="人物传记处理管道")
    parser.add_argument('pdf_path', help="PDF文件路径")
    parser.add_argument('output_dir', help="输出目录")
    parser.add_argument('--dpi', type=int, default=300, help="图片DPI")
    parser.add_argument('--start-page', type=int, help="起始页")
    parser.add_argument('--end-page', type=int, help="结束页")

    args = parser.parse_args()

    def progress(current, total, desc):
        print(f"[{current}/{total}] {desc}")

    run_biography_pipeline(
        args.pdf_path,
        args.output_dir,
        dpi=args.dpi,
        start_page=args.start_page,
        end_page=args.end_page,
        progress_callback=progress,
    )

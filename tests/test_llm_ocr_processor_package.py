import unittest

from modules.llm_ocr_processor import ProcessedPage, QwenVLOCRProcessor


def make_processor_without_io() -> QwenVLOCRProcessor:
    processor = QwenVLOCRProcessor.__new__(QwenVLOCRProcessor)
    processor.pdf_path = "sample.pdf"
    processor.output_dir = "out"
    processor.images_dir = "out/images"
    processor.ocr_output_dir = "out/llm_ocr_output"
    processor.final_output_dir = "out/final"
    processor.api_key = ""
    processor.model = "qwen-vl-ocr-latest"
    processor.previous_header = ""
    processor.previous_footer = ""
    processor.header_footer_history = []
    return processor


class TestLLMOCRProcessorPackage(unittest.TestCase):
    def test_build_pages_package_records_statistics(self):
        processor = make_processor_without_io()
        pages = [
            ProcessedPage(
                pdf_page_number=1,
                ocr_page_number=1,
                ocr_page_number_text="1",
                text="Tokugawa page text",
                text_length=18,
                raw_text="Tokugawa page text",
            )
        ]

        package = processor.build_pages_package(pages)

        self.assertEqual(package["type"], "ocr_result")
        self.assertEqual(package["backend"], "llm_api")
        self.assertEqual(package["provider"], "dashscope")
        self.assertEqual(package["statistics"]["total_pages"], 1)
        self.assertFalse(package["needs_review"])
        self.assertIn("vision_ocr", package["metadata"]["capabilities"])

    def test_empty_pages_require_review(self):
        processor = make_processor_without_io()

        package = processor.build_pages_package([])

        self.assertTrue(package["needs_review"])
        self.assertIn("no_pages", package["quality_flags"])
        self.assertIn("no_text", package["quality_flags"])


if __name__ == "__main__":
    unittest.main()

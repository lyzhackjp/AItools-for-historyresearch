import unittest

from modules.universal_layout_analyzer import (
    DocumentType,
    DocumentTypeDetector,
    UniversalLayoutAnalyzer,
    create_layout_config,
)


class FakeImage:
    shape = (1200, 800, 3)


class TestUniversalLayoutAnalyzerPackage(unittest.TestCase):
    def test_get_capabilities_describes_lightweight_protocol(self):
        analyzer = UniversalLayoutAnalyzer(create_layout_config())

        capabilities = analyzer.get_capabilities()

        self.assertEqual(capabilities["module"], "universal_layout_analyzer")
        self.assertIn("layout_page", capabilities["output_types"])
        self.assertIn(DocumentType.BOOK.value, capabilities["supported_document_types"])
        self.assertTrue(capabilities["privacy"]["offline_by_default"])
        self.assertIn("skill", capabilities["fallback_order"])
        self.assertIn("mcp", capabilities["fallback_order"])

    def test_analyze_page_package_can_skip_model_loading(self):
        analyzer = UniversalLayoutAnalyzer(create_layout_config())

        package = analyzer.analyze_page_package(FakeImage(), page_num=3, use_models=False)

        self.assertEqual(package["type"], "layout_page")
        self.assertEqual(package["page"]["page_number"], 3)
        self.assertEqual(package["summary"]["width"], 800)
        self.assertEqual(package["summary"]["height"], 1200)
        self.assertIn("models_not_requested", package["quality_flags"])
        self.assertTrue(package["needs_review"])

    def test_analyze_document_package_can_return_lightweight_envelope(self):
        analyzer = UniversalLayoutAnalyzer(create_layout_config())

        package = analyzer.analyze_document_package(
            "synthetic.pdf",
            start_page=2,
            end_page=4,
            use_models=False,
        )

        self.assertEqual(package["type"], "layout_document")
        self.assertEqual(package["document_type"], DocumentType.UNKNOWN.value)
        self.assertEqual(package["metadata"]["source_path"], "synthetic.pdf")
        self.assertIn("models_not_requested", package["quality_flags"])
        self.assertTrue(package["needs_review"])

    def test_document_type_detector_keeps_core_supported_types(self):
        self.assertEqual(
            DocumentTypeDetector.detect(["明治三年の日記 記録"]),
            DocumentType.CLASSICAL_DIARY.value,
        )
        self.assertEqual(
            DocumentTypeDetector.detect(["東京朝日新聞 第三号"]),
            DocumentType.NEWSPAPER.value,
        )


if __name__ == "__main__":
    unittest.main()

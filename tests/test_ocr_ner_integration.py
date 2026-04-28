import unittest

from modules.ner_disambiguation import NERDisambiguation
from modules.ner_processor import NERProcessor
from modules.unified_ocr_processor import OCRModelType, UnifiedOCRProcessor


class TestUnifiedOCRProcessor(unittest.TestCase):
    def test_capabilities_expose_multiple_engines(self):
        processor = UnifiedOCRProcessor()
        capabilities = processor.get_capabilities()
        model_names = {item["type"] for item in capabilities["models"]}
        self.assertIn(OCRModelType.TESSERACT.value, model_names)
        self.assertIn(OCRModelType.NDLOCR_LITE.value, model_names)
        self.assertIn(OCRModelType.NDLKOTENOCR_LITE.value, model_names)
        self.assertIn(OCRModelType.LLM_OCR.value, model_names)


class TestNERProcessor(unittest.TestCase):
    def test_script_backend_returns_normalized_entities(self):
        processor = NERProcessor(test_mode=True)
        entities = processor.recognize_historical_entities("伊藤博文出生于1841年，是明治维新的重要人物。")
        self.assertTrue(entities)
        first = entities[0]
        self.assertIn("entity", first)
        self.assertIn("category", first)
        self.assertIn("confidence", first)
        self.assertIn("backend", first)

    def test_capabilities_expose_multi_backend_choices(self):
        processor = NERProcessor(test_mode=True)
        capabilities = processor.get_capabilities()
        backend_names = {item["name"] for item in capabilities["backends"]}
        self.assertIn("script", backend_names)
        self.assertIn("llm_api", backend_names)
        self.assertIn("local_llm", backend_names)


class TestNERDisambiguationCompatibility(unittest.TestCase):
    def test_stage3_compatibility_shape(self):
        disambiguation = NERDisambiguation()
        results = disambiguation.disambiguate(
            [("明治", "date", 0, 2), ("江户", "location", 3, 5)],
            "明治维新发生在江户幕府统治结束之际。",
        )
        self.assertEqual(len(results), 2)
        self.assertIn("original_entity", results[0])
        self.assertIn("disambiguated_type", results[0])
        self.assertIn("confidence", results[0])


if __name__ == "__main__":
    unittest.main()

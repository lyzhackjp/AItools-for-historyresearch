import unittest

from modules.ner_processor import NERProcessor


class TestNERProcessorPackage(unittest.TestCase):
    def test_recognize_package_exposes_envelope(self):
        processor = NERProcessor(test_mode=True)
        text = "Tokugawa Ieyasu consolidated political authority in Edo."

        result = processor.recognize_historical_entities_package(
            text,
            categories=["person", "location"],
            backend="script",
            source={"id": "doc-1", "title": "Edo politics"},
        )

        self.assertEqual(result["type"], "ner_extraction")
        self.assertEqual(result["backend"], "script")
        self.assertEqual(result["source"]["id"], "doc-1")
        self.assertIn("capabilities", result)
        self.assertIn("fallback_order", result["capabilities"])
        self.assertIsInstance(result["entities"], list)
        self.assertIsInstance(result["relationships"], list)

    def test_batch_package_flags_empty_batch(self):
        processor = NERProcessor(test_mode=True)

        result = processor.batch_process_documents_package([])

        self.assertEqual(result["type"], "ner_batch")
        self.assertTrue(result["needs_review"])
        self.assertIn("no_documents", result["quality_flags"])


if __name__ == "__main__":
    unittest.main()

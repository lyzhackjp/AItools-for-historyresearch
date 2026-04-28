import unittest

from modules.historical_speech_extractor import (
    DateInfo,
    HistoricalSpeechExtractor,
    SpeechSegment,
)


class StubSpeechExtractor(HistoricalSpeechExtractor):
    def __init__(self):
        super().__init__(api_provider="qwen", test_mode=True)

    def extract_speeches(self, text):
        if not text.strip():
            return []
        return [
            SpeechSegment(
                text="We shall proceed",
                speaker="Minister",
                speech_type="direct_speech",
                position=(0, 16),
                confidence=0.9,
            )
        ]

    def extract_dates(self, text):
        if not text.strip():
            return []
        return [
            DateInfo(
                year=1889,
                month=2,
                day=11,
                date_type="text_internal",
                original_text="1889-02-11",
                confidence=0.95,
            )
        ]

    def extract_entities(self, text, categories=None):
        if not text.strip():
            return []
        return [
            {
                "entity": "Minister",
                "category": "person",
                "start_pos": 0,
                "end_pos": 8,
                "confidence": 0.9,
                "source": "stub",
            }
        ]


class HistoricalSpeechExtractorPackageTest(unittest.TestCase):
    def test_process_ocr_result_package_returns_structured_summary(self):
        extractor = StubSpeechExtractor()
        ocr_data = {
            "metadata": {"source": "unit_test"},
            "pages": [
                {
                    "pdf_page_number": 1,
                    "ocr_page_number": 11,
                    "header": "",
                    "footer": "",
                    "text": 'Minister said "We shall proceed" on 1889-02-11.',
                }
            ],
        }

        package = extractor.process_ocr_result_package(ocr_data)

        self.assertEqual(package["type"], "historical_speech_analysis")
        self.assertEqual(package["backend"], "script")
        self.assertFalse(package["needs_review"])
        self.assertEqual(package["statistics"]["total_speeches"], 1)
        self.assertEqual(package["statistics"]["total_dates"], 1)
        self.assertEqual(package["statistics"]["total_entities"], 1)
        self.assertEqual(package["records"][0]["speeches"][0]["speaker"], "Minister")
        self.assertEqual(package["source_summary"]["metadata_keys"], ["source"])

    def test_analyze_text_package_wraps_single_page_input(self):
        extractor = StubSpeechExtractor()

        package = extractor.analyze_text_package(
            "Minister said the line.",
            page_number=7,
            metadata={"ocr_page_number": 70},
        )

        self.assertEqual(package["source_summary"]["page_count"], 1)
        self.assertEqual(package["records"][0]["page_number"], 7)
        self.assertEqual(package["records"][0]["original_page_number"], 70)
        self.assertGreater(package["confidence"], 0.8)

    def test_empty_ocr_package_needs_review(self):
        extractor = StubSpeechExtractor()

        package = extractor.process_ocr_result_package({"metadata": {}, "pages": []})

        self.assertTrue(package["needs_review"])
        self.assertIn("no_pages", package["quality_flags"])
        self.assertEqual(package["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()

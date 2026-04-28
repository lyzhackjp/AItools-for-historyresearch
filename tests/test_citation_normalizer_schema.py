import unittest

from modules.citation_normalizer import CitationNormalizer


class TestCitationNormalizerSchema(unittest.TestCase):
    def setUp(self):
        self.normalizer = CitationNormalizer(style="gb7714")

    def test_normalize_single_record_schema(self):
        citation = (
            'Smith, John. "Tokugawa Reforms." Journal of Japanese History, '
            "2012, vol. 12, no. 3, pp. 45-67. https://doi.org/10.1234/abcd"
        )
        record = self.normalizer.normalize(citation)

        self.assertIsInstance(record, dict)
        for key in (
            "raw_text",
            "normalized_citation",
            "type",
            "title",
            "authors",
            "year",
            "confidence",
            "needs_review",
            "backend",
            "provider",
            "model",
        ):
            self.assertIn(key, record)

        self.assertEqual(record["target_style"], "gb7714")
        self.assertIsInstance(record["authors"], list)
        self.assertTrue(record["normalized_citation"])
        self.assertGreater(record["confidence"], 0.0)

    def test_normalize_batch_keeps_shared_schema(self):
        citations = [
            'Tanaka, Hiroshi. "Meiji State Formation." Modern Japan Review, 2008, vol. 4, no. 2, pp. 12-20.',
            "Yamada, Ken. History of Early Modern Japan [M]. Tokyo Press, 1998.",
        ]
        records = self.normalizer.normalize(citations, target_style="chicago")

        self.assertEqual(len(records), 2)
        self.assertTrue(all("normalized_citation" in record for record in records))
        self.assertTrue(all(record["target_style"] == "chicago" for record in records))


if __name__ == "__main__":
    unittest.main()

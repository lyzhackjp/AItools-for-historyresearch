import unittest

from modules.citation_formats import CitationFormatter


class CitationFormatsPackageTest(unittest.TestCase):
    def test_format_record_package_wraps_rendered_citation(self):
        formatter = CitationFormatter()
        record = {
            "type": "article",
            "author": "Smith",
            "title": "Tokugawa governance",
            "journal": "Journal of Early Modern Japan",
            "year": "2024",
            "volume": "12",
            "issue": "2",
            "pages": "10-30",
        }

        package = formatter.format_record_package(record, style="gb7714", index=3)

        self.assertEqual(package["type"], "citation_formatting")
        self.assertEqual(package["style"], "gb7714")
        self.assertFalse(package["needs_review"])
        self.assertTrue(package["rendered"].startswith("[3]"))
        self.assertEqual(package["summary"]["record_count"], 1)

    def test_format_batch_package_records_missing_fields(self):
        formatter = CitationFormatter()
        records = [
            {"type": "book", "title": "A Book", "author": "Tanaka", "year": "1988", "publisher": "Tokyo"},
            {"type": "article", "title": "Untitled fragment"},
        ]

        package = formatter.format_batch_package(records, style="chicago")

        self.assertEqual(package["summary"]["record_count"], 2)
        self.assertEqual(package["summary"]["rendered_count"], 2)
        self.assertTrue(package["needs_review"])
        self.assertIn("missing_author", package["quality_flags"])
        self.assertIn("missing_year", package["quality_flags"])


if __name__ == "__main__":
    unittest.main()

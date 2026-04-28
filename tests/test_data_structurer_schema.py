import csv
import io
import unittest

from modules.data_structurer import DataStructurer


class TestDataStructurerSchema(unittest.TestCase):
    def test_normalize_record_reports_missing_required_fields(self):
        structurer = DataStructurer()
        result = structurer.normalize_record(
            {"title": "  近代日本政治史  ", "year": ""},
            schema={"required": ["title", "year"], "optional": ["author"]},
            source_type="citation",
        )

        self.assertEqual(result["type"], "citation")
        self.assertEqual(result["data"]["title"], "近代日本政治史")
        self.assertTrue(result["needs_review"])
        self.assertEqual(result["validation"]["missing_fields"], ["year"])

    def test_build_export_payload_summarizes_review_counts(self):
        structurer = DataStructurer()
        payload = structurer.build_export_payload(
            [{"name": "Edo", "category": "place"}, {"name": "", "category": "person"}],
            schema={"required": ["name", "category"]},
            source_type="entity",
        )

        self.assertEqual(payload["record_count"], 2)
        self.assertEqual(payload["records_needing_review"], 1)
        self.assertTrue(payload["needs_review"])

    def test_to_csv_uses_union_of_dict_fields(self):
        structurer = DataStructurer()
        csv_text = structurer.to_csv([{"a": 1}, {"b": 2}])
        rows = list(csv.DictReader(io.StringIO(csv_text)))

        self.assertEqual(rows[0]["a"], "1")
        self.assertIn("b", rows[0])
        self.assertEqual(rows[1]["b"], "2")


if __name__ == "__main__":
    unittest.main()

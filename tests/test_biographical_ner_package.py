import unittest

from modules.biographical_ner import (
    BiographicalNER,
    extract_biographical_entities_package,
)


class TestBiographicalNERPackage(unittest.TestCase):
    def test_get_capabilities_is_local_rule_backend(self):
        ner = BiographicalNER()

        capabilities = ner.get_capabilities()

        self.assertEqual(capabilities["module"], "biographical_ner")
        self.assertIn("biography_entities", capabilities["output_types"])
        self.assertTrue(capabilities["privacy"]["offline_by_default"])
        self.assertFalse(capabilities["privacy"]["external_api_required"])
        self.assertIn("skill", capabilities["fallback_order"])
        self.assertIn("mcp", capabilities["fallback_order"])

    def test_process_text_blocks_package_extracts_person(self):
        ner = BiographicalNER()
        blocks = [
            {
                "text": "\n".join(
                    [
                        "鈴木梅四郎",
                        "本籍：東京府",
                        "学歴：東京帝国大学経済学部卒業",
                        "昭和5年 満鉄調査部",
                    ]
                ),
                "page_num": 1,
                "block_idx": 0,
            }
        ]

        package = ner.process_text_blocks_package(blocks)

        self.assertEqual(package["type"], "biography_entities")
        self.assertEqual(package["summary"]["person_count"], 1)
        self.assertEqual(package["persons"][0]["name"], "鈴木梅四郎")
        self.assertEqual(package["persons"][0]["page_number"], 1)
        self.assertFalse(package["needs_review"])

    def test_convenience_package_flags_empty_blocks(self):
        package = extract_biographical_entities_package([{"text": "", "page_num": 1, "block_idx": 0}])

        self.assertEqual(package["type"], "biography_entities")
        self.assertEqual(package["summary"]["person_count"], 0)
        self.assertTrue(package["needs_review"])
        self.assertIn("empty_text_blocks", package["quality_flags"])
        self.assertIn("no_biography_entities", package["quality_flags"])


if __name__ == "__main__":
    unittest.main()

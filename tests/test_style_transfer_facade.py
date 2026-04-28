import unittest

from modules.style_transfer import StyleTransfer, create_style_transfer


class TestStyleTransferFacade(unittest.TestCase):
    def test_factory_and_capabilities(self):
        transfer = create_style_transfer(test_mode=True)
        self.assertIsInstance(transfer, StyleTransfer)
        capabilities = transfer.get_capabilities()
        self.assertIn("task_type", capabilities)
        self.assertEqual(capabilities["task_type"], "style_transfer")

    def test_analyze_style_matrix_returns_expected_shape(self):
        transfer = StyleTransfer(test_mode=True)
        analysis = transfer.analyze_style_matrix(
            "This is a formal historical paragraph. Therefore, the argument proceeds carefully."
        )
        self.assertIn("sentence_structure", analysis)
        self.assertIn("vocabulary_choices", analysis)
        self.assertIn("tone_narrative", analysis)
        self.assertIn("rhetorical_patterns", analysis)
        self.assertIn("overall_style_summary", analysis)

    def test_transfer_style_result_returns_unified_metadata(self):
        transfer = StyleTransfer(test_mode=True)
        result = transfer.transfer_style_result(
            "This is a short paragraph for style transfer.",
            target_style="academic history prose",
        )
        self.assertIn("rewritten_text", result)
        self.assertIn("backend", result)
        self.assertIn("provider", result)
        self.assertIn("confidence", result)
        self.assertIn("needs_review", result)


if __name__ == "__main__":
    unittest.main()

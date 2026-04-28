import unittest

from modules.citation_network_analyzer import CitationNetworkAnalyzer


class TestCitationNetworkPackage(unittest.TestCase):
    def test_analyze_documents_package_exposes_graph_envelope(self):
        analyzer = CitationNetworkAnalyzer()
        documents = [
            {
                "title": "Meiji Political Thought",
                "authors": ["A. Tanaka"],
                "year": "2010",
                "text": "This article cites Tokugawa Governance Reform as a key background.",
            },
            {
                "title": "Tokugawa Governance Reform",
                "authors": ["B. Sato"],
                "year": "2001",
                "text": "A study of early modern institutions.",
            },
        ]

        result = analyzer.analyze_documents_package(documents, language="english")

        self.assertEqual(result["type"], "citation_network")
        self.assertEqual(result["backend"], "script")
        self.assertEqual(result["provider"], "rule_based_graph")
        self.assertEqual(result["summary"]["total_nodes"], 2)
        self.assertGreaterEqual(result["summary"]["total_edges"], 1)
        self.assertFalse(result["needs_review"])
        self.assertIn("execution", result["graph"]["metadata"])

    def test_empty_documents_are_flagged_for_review(self):
        analyzer = CitationNetworkAnalyzer()

        result = analyzer.analyze_documents_package([])

        self.assertTrue(result["needs_review"])
        self.assertIn("no_documents", result["quality_flags"])
        self.assertLess(result["confidence"], 0.5)


if __name__ == "__main__":
    unittest.main()

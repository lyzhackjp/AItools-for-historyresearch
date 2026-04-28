import unittest

from modules.citation_formats import CitationFormatter
from modules.citation_network_analyzer import CitationNetworkAnalyzer
from tools.workflow.research_project import PaperRecord, ResearchProject, StageStatus
from tools.workflow.stages.stage4_examine import Stage4Examine


class CitationChainTest(unittest.TestCase):
    def test_citation_network_analyzer_returns_normalized_summary(self):
        analyzer = CitationNetworkAnalyzer()
        documents = [
            {
                "id": "doc-a",
                "title": "Tokugawa governance",
                "authors": ["Smith"],
                "year": "2001",
                "text": "Tokugawa governance shaped Edo institutions.",
            },
            {
                "id": "doc-b",
                "title": "Edo institutions and governance",
                "authors": ["Tanaka"],
                "year": "2010",
                "text": "Edo institutions and governance builds on Tokugawa governance and governance debates.",
            },
        ]

        result = analyzer.analyze_documents(documents, language="english")

        self.assertEqual(result["summary"]["total_nodes"], 2)
        self.assertGreaterEqual(result["summary"]["total_edges"], 1)
        self.assertIn("average_edge_confidence", result["summary"])

    def test_stage4_uses_analyzer_summary(self):
        project = ResearchProject(topic="Tokugawa citations", language="en")
        project.literature = [
            PaperRecord(
                id="paper-1",
                title="Tokugawa governance",
                abstract="Tokugawa governance shaped Edo institutions.",
                authors=["Smith"],
                year="2001",
            ),
            PaperRecord(
                id="paper-2",
                title="Edo institutions and governance",
                abstract="Edo institutions and governance builds on Tokugawa governance and governance debates.",
                authors=["Tanaka"],
                year="2010",
            ),
        ]

        stage = Stage4Examine(project)

        def fake_outline_analyzer():
            class Analyzer:
                def analyze(self, text, language="english"):
                    del text, language
                    return {
                        "section_word_counts": {},
                        "section_ratios": {},
                        "logical_gaps": [],
                        "deviation_flags": [],
                        "suggestions": [],
                    }

            return Analyzer()

        project.paper_draft = "Introduction\n" + ("Tokugawa governance. " * 20)
        stage._get_outline_analyzer = fake_outline_analyzer
        result = stage.run()

        self.assertEqual(project.stage4_status, StageStatus.DONE)
        summary = project.get_stage_metadata(4)["execution_summary"]["citation_analysis"]
        self.assertEqual(summary["nodes"], 2)
        self.assertIn("average_edge_confidence", summary)
        self.assertIsNotNone(result["citation_network"])

    def test_citation_formatter_formats_normalized_record(self):
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

        chicago = formatter.format_record(record, style="chicago")
        gb = formatter.format_record(record, style="gb7714", index=3)

        self.assertIn("Tokugawa governance", chicago)
        self.assertTrue(gb.startswith("[3]"))


if __name__ == "__main__":
    unittest.main()

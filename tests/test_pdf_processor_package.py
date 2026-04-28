import tempfile
import unittest
from pathlib import Path

try:
    import fitz
except ModuleNotFoundError as exc:
    raise unittest.SkipTest("PyMuPDF/fitz is not installed") from exc

from modules.pdf_processor import PDFProcessor


class TestPDFProcessorPackage(unittest.TestCase):
    def _create_pdf(self, path: Path) -> None:
        doc = fitz.open()
        page = doc.new_page(width=300, height=400)
        page.insert_text((72, 72), "Tokugawa governance shaped Edo institutions.")
        doc.save(path)
        doc.close()

    def test_info_and_text_packages_have_workflow_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "sample.pdf"
            self._create_pdf(pdf_path)
            processor = PDFProcessor(output_dir=temp_dir)

            info = processor.get_pdf_info_package(str(pdf_path))
            text = processor.extract_text_package(str(pdf_path))

            self.assertEqual(info["backend"], "script")
            self.assertEqual(info["provider"], "pymupdf")
            self.assertEqual(info["page_count"], 1)
            self.assertFalse(info["needs_review"])
            self.assertIn("Tokugawa governance", text["full_text"])
            self.assertFalse(text["needs_review"])

    def test_convert_to_images_package_records_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "sample.pdf"
            out_dir = Path(temp_dir) / "images"
            self._create_pdf(pdf_path)
            processor = PDFProcessor(output_dir=temp_dir)

            result = processor.convert_to_images_package(str(pdf_path), output_dir=str(out_dir), dpi=72)

            self.assertEqual(result["image_count"], 1)
            self.assertEqual(result["artifacts"][0]["page_number"], 1)
            self.assertTrue(Path(result["artifacts"][0]["path"]).exists())


if __name__ == "__main__":
    unittest.main()

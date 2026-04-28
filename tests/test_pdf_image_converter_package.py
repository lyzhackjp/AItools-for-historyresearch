import tempfile
import unittest
from pathlib import Path

try:
    import fitz
except ModuleNotFoundError as exc:
    raise unittest.SkipTest("PyMuPDF/fitz is not installed") from exc

from modules.pdf_image_converter import PDFImageConverter, convert_pdf_to_images_package


class TestPDFImageConverterPackage(unittest.TestCase):
    def _create_pdf(self, path: Path) -> None:
        doc = fitz.open()
        page = doc.new_page(width=240, height=320)
        page.insert_text((40, 60), "Meiji archives require page mapping.")
        doc.save(path)
        doc.close()

    def test_range_package_records_artifacts_and_capabilities(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "sample.pdf"
            out_dir = Path(temp_dir) / "images"
            self._create_pdf(pdf_path)

            converter = PDFImageConverter(dpi=72)
            result = converter.convert_range_package(str(pdf_path), 1, 1, str(out_dir))

            self.assertEqual(result["backend"], "script")
            self.assertEqual(result["provider"], "pymupdf")
            self.assertEqual(result["image_count"], 1)
            self.assertEqual(result["artifacts"][0]["page_number"], 1)
            self.assertEqual(result["artifacts"][0]["dpi"], 72)
            self.assertTrue(Path(result["artifacts"][0]["path"]).exists())
            self.assertIn("page_artifact_mapping", converter.get_capabilities()["capabilities"])

    def test_function_wrapper_preserves_package_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "sample.pdf"
            self._create_pdf(pdf_path)

            result = convert_pdf_to_images_package(str(pdf_path), str(Path(temp_dir) / "out"), dpi=72)

            self.assertEqual(result["type"], "pdf_image_conversion")
            self.assertFalse(result["needs_review"])


if __name__ == "__main__":
    unittest.main()

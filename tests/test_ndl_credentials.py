import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.workflows import ndl_credentials
from modules.workflows.ndl_credentials import NDLCredentialError, load_ndl_credentials


class TestNDLCredentials(unittest.TestCase):
    def test_loads_from_environment(self):
        with patch.dict(
            os.environ,
            {"NDL_USERNAME": "NDL_USERNAME_TEST", "NDL_PASSWORD": "NDL_PASSWORD_TEST"},
            clear=True,
        ):
            credentials = load_ndl_credentials()

        self.assertEqual(credentials.username, "NDL_USERNAME_TEST")
        self.assertEqual(credentials.password, "NDL_PASSWORD_TEST")
        self.assertEqual(credentials.source, "environment")

    def test_loads_from_key_value_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_file = Path(temp_dir) / "ndl_credentials.txt"
            credentials_file.write_text(
                "username=NDL_FILE_USERNAME_TEST\npassword=NDL_FILE_PASSWORD_TEST\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                credentials = load_ndl_credentials(credentials_file)

        self.assertEqual(credentials.username, "NDL_FILE_USERNAME_TEST")
        self.assertEqual(credentials.password, "NDL_FILE_PASSWORD_TEST")
        self.assertIn("ndl_credentials.txt", credentials.source)

    def test_loads_from_environment_file_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_file = Path(temp_dir) / "custom_ndl_credentials.txt"
            credentials_file.write_text(
                "card_id=NDL_FILE_CARD_TEST\nndl_password=NDL_FILE_PASSWORD_TEST\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"NDL_CREDENTIALS_FILE": str(credentials_file)}, clear=True):
                credentials = load_ndl_credentials()

        self.assertEqual(credentials.username, "NDL_FILE_CARD_TEST")
        self.assertEqual(credentials.password, "NDL_FILE_PASSWORD_TEST")

    def test_falls_back_to_singular_secret_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_default = Path(temp_dir) / "secrets" / "ndl_credentials.txt"
            alternate = Path(temp_dir) / "secret" / "ndl_credentials.txt"
            alternate.parent.mkdir()
            alternate.write_text(
                "username=NDL_ALT_USERNAME_TEST\npassword=NDL_ALT_PASSWORD_TEST\n",
                encoding="utf-8",
            )

            with patch.object(ndl_credentials, "DEFAULT_NDL_CREDENTIALS_FILE", missing_default):
                with patch.object(ndl_credentials, "ALTERNATE_NDL_CREDENTIALS_FILES", (alternate,)):
                    with patch.dict(os.environ, {}, clear=True):
                        credentials = load_ndl_credentials()

        self.assertEqual(credentials.username, "NDL_ALT_USERNAME_TEST")
        self.assertEqual(credentials.password, "NDL_ALT_PASSWORD_TEST")

    def test_missing_credentials_raise_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_file = Path(temp_dir) / "missing.txt"

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(NDLCredentialError) as context:
                    load_ndl_credentials(missing_file)

        self.assertIn("NDL credentials are not configured", str(context.exception))


if __name__ == "__main__":
    unittest.main()

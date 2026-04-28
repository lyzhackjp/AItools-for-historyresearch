import unittest

try:
    from app.app import create_app, get_service_status
except ModuleNotFoundError as exc:
    if exc.name != "flask":
        raise
    create_app = None
    get_service_status = None


@unittest.skipIf(create_app is None, "Flask is not installed in this environment")
class TestAPIAppFactory(unittest.TestCase):
    def test_create_app_status_does_not_initialize_lazy_services(self):
        app = create_app({"TESTING": True})
        client = app.test_client()

        before = get_service_status()
        response = client.get("/api/system/status")
        after = get_service_status()

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["data"]["privacy"]["does_not_initialize_lazy_services"])
        self.assertFalse(payload["data"]["services"]["doc_processor"]["initialized"])
        self.assertEqual(before["doc_processor"]["initialized"], after["doc_processor"]["initialized"])

    def test_task_execute_returns_package_envelope(self):
        app = create_app({"TESTING": True})
        client = app.test_client()

        response = client.post(
            "/api/tasks/execute",
            json={
                "task_type": "text_summary",
                "mode": "script",
                "input": {
                    "text": "This is a short historical research note about Meiji institutions and source criticism.",
                    "max_length": 40,
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["type"], "task_execution")
        self.assertEqual(payload["task_type"], "text_summary")
        self.assertTrue(payload["success"])
        self.assertIn("task_options", payload)
        self.assertIn("result", payload)


if __name__ == "__main__":
    unittest.main()

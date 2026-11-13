from io import BytesIO

from django.test import TestCase
from openpyxl import load_workbook
from rest_framework.test import APIClient, APIRequestFactory

from tests.testapp.models import ExampleModel
from tests.testapp.views import ExampleViewSet


class XLSXStreamingTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def get_xlsx(self):
        response = self.client.get("/examples/?format=xlsx")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)

        content = b"".join(response.streaming_content)
        workbook = load_workbook(BytesIO(content), read_only=True)

        return response, workbook

    def test_xlsx_is_streamed_by_default(self):
        ExampleModel.objects.create(
            title="First",
            description="First description",
        )

        response, workbook = self.get_xlsx()

        self.assertTrue(response.streaming)
        self.assertTrue(
            response["Content-Type"].startswith(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        )

        rows = list(workbook.active.values)

        self.assertEqual(
            rows,
            [
                ("title", "description"),
                ("First", "First description"),
            ],
        )

    def test_xlsx_exports_all_queryset_records(self):
        ExampleModel.objects.bulk_create(
            [
                ExampleModel(title="First", description="Description 1"),
                ExampleModel(title="Second", description="Description 2"),
                ExampleModel(title="Third", description="Description 3"),
            ]
        )

        _, workbook = self.get_xlsx()
        rows = list(workbook.active.values)

        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0], ("title", "description"))
        self.assertEqual(
            set(rows[1:]),
            {
                ("First", "Description 1"),
                ("Second", "Description 2"),
                ("Third", "Description 3"),
            },
        )

    def test_xlsx_handles_empty_queryset(self):
        _, workbook = self.get_xlsx()

        rows = list(workbook.active.values)

        self.assertEqual(rows, [("title", "description")])

    def test_xlsx_uses_configured_filename(self):
        response, _ = self.get_xlsx()

        self.assertIn(
            "my_export.xlsx",
            response["Content-Disposition"],
        )

    def test_json_response_is_not_streamed(self):
        ExampleModel.objects.create(
            title="First",
            description="First description",
        )

        request = APIRequestFactory().get(
            "/examples/",
            HTTP_ACCEPT="application/json",
        )
        response = ExampleViewSet.as_view({"get": "list"})(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.streaming)

        self.assertEqual(
            response.json(),
            [
                {
                    "title": "First",
                    "description": "First description",
                }
            ],
        )

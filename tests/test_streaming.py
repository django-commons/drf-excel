from io import BytesIO

import pytest
from django.test import TestCase
from openpyxl import load_workbook
from rest_framework import serializers
from rest_framework.test import APIClient, APIRequestFactory

from drf_excel import mixins
from tests.testapp.models import ExampleModel
from tests.testapp.views import ExampleViewSet


class StreamingOptionsSerializer(serializers.ModelSerializer):
    extra = serializers.SerializerMethodField()
    row_color = serializers.SerializerMethodField()

    class Meta:
        model = ExampleModel
        fields = ("title", "description", "extra", "row_color")

    def get_extra(self, obj):
        return "calculated"

    def get_row_color(self, obj):
        return "FF0000"


class StreamingOptionsViewSet(ExampleViewSet):
    serializer_class = StreamingOptionsSerializer
    header = {
        "header_title": "Report",
        "tab_title": "Data",
        "height": 30,
        "style": {"font": {"bold": True}},
    }
    column_header = {
        "titles": ["Custom title"],
        "column_width": [32],
        "height": 24,
        "style": {"font": {"italic": True}},
    }
    body = {
        "height": 18,
        "style": {"font": {"bold": True}},
    }
    sheet_view_options = {"showGridLines": False}
    xlsx_auto_filter = True
    xlsx_custom_cols = {
        "extra": {
            "label": "Calculated",
            "formatter": lambda value: f"{value}!",
        },
        "missing": {"label": "Empty"},
    }


def get_xlsx_response(viewset):
    request = APIRequestFactory().get("/examples/?format=xlsx")
    return viewset.as_view({"get": "list"})(request)


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
            response.data,
            [
                {
                    "title": "First",
                    "description": "First description",
                }
            ],
        )


@pytest.mark.django_db
def test_streaming_export_applies_view_options(workbook_reader):
    ExampleModel.objects.create(title="First", description="Description")

    response = get_xlsx_response(StreamingOptionsViewSet)
    workbook = workbook_reader(response, read_only=False)
    worksheet = workbook.active

    assert worksheet.title == "Data"
    assert worksheet["A1"].value == "Report"
    assert worksheet["A1"].font.bold is True
    assert worksheet["A2"].value == "Custom title"
    assert worksheet["A2"].font.italic is True
    assert worksheet["B2"].value == "description"
    assert worksheet["C2"].value == "Calculated"
    assert worksheet["D2"].value == "Empty"
    assert worksheet["A3"].value == "First"
    assert worksheet["C3"].value == "calculated!"
    assert worksheet["D3"].value is None
    assert worksheet["A3"].fill.start_color.rgb == "00FF0000"
    assert worksheet.row_dimensions[1].height == 30
    assert worksheet.row_dimensions[2].height == 24
    assert worksheet.row_dimensions[3].height == 18
    assert worksheet.column_dimensions["A"].width == 32
    assert worksheet.sheet_view.showGridLines is False
    assert worksheet.auto_filter.ref == "A2:D3"


@pytest.mark.django_db
def test_non_queryset_export_is_rejected():
    class NonQuerysetViewSet(ExampleViewSet):
        def get_queryset(self):
            return []

    with pytest.raises(TypeError, match="requires a queryset"):
        get_xlsx_response(NonQuerysetViewSet)


@pytest.mark.parametrize(
    ("chunk_size", "error"),
    [
        (True, TypeError),
        (1.5, TypeError),
        ("10", TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
@pytest.mark.django_db
def test_invalid_iterator_chunk_size_is_rejected(chunk_size, error):
    class InvalidChunkSizeViewSet(ExampleViewSet):
        xlsx_iterator_chunk_size = chunk_size

    with pytest.raises(error, match="xlsx_iterator_chunk_size"):
        get_xlsx_response(InvalidChunkSizeViewSet)


@pytest.mark.django_db
def test_header_image_is_rejected():
    class ImageHeaderViewSet(ExampleViewSet):
        header = {"img": "header.png"}

    with pytest.raises(NotImplementedError, match="Images in the XLSX header"):
        get_xlsx_response(ImageHeaderViewSet)


@pytest.mark.django_db
def test_filename_attribute_is_used_when_get_filename_is_unavailable():
    class FilenameFallbackViewSet(ExampleViewSet):
        filename = "fallback.xlsx"
        get_filename = None

    response = get_xlsx_response(FilenameFallbackViewSet)

    assert 'filename="fallback.xlsx"' in response["Content-Disposition"]


@pytest.mark.django_db
def test_workbook_save_failure_closes_temporary_file(monkeypatch):
    temporary_files = []
    original_temporary_file = mixins.TemporaryFile

    def create_temporary_file(*args, **kwargs):
        temporary_file = original_temporary_file(*args, **kwargs)
        temporary_files.append(temporary_file)
        return temporary_file

    def fail_save(workbook, file):
        raise RuntimeError("save failed")

    monkeypatch.setattr(mixins, "TemporaryFile", create_temporary_file)
    monkeypatch.setattr(mixins.Workbook, "save", fail_save)

    with pytest.raises(RuntimeError, match="save failed"):
        get_xlsx_response(ExampleViewSet)

    assert len(temporary_files) == 1
    assert temporary_files[0].closed

import gc
import os

import psutil
import pytest
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from rest_framework import serializers
from rest_framework.fields import CharField, DateTimeField, IntegerField
from rest_framework.test import APIClient

from drf_excel.fields import XLSXDateField, XLSXField, XLSXNumberField
from drf_excel import streaming as streaming_module
from drf_excel.utilities import XLSXStyle
from tests.testapp.models import ExampleModel
from tests.testapp.views import ExampleViewSet

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def read_streaming_response(response):
    """Consume the response so the XLSX workbook can be inspected."""
    return b"".join(response.streaming_content)


def measure_peak_rss(api_client):
    """
    Measure the process RSS increase while consuming
    the streaming XLSX response.
    """
    process = psutil.Process(os.getpid())

    gc.collect()
    baseline = process.memory_info().rss
    peak = baseline

    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200
    assert response.streaming is True

    try:
        for _chunk in response.streaming_content:
            current = process.memory_info().rss
            peak = max(peak, current)
    finally:
        response.close()

    return max(0, peak - baseline)


def test_streaming_export_returns_all_queryset_records(
    api_client,
    workbook_reader,
):
    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title="First",
                description="First description",
            ),
            ExampleModel(
                title="Second",
                description="Second description",
            ),
            ExampleModel(
                title="Third",
                description="Third description",
            ),
        ]
    )

    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200
    assert response.streaming is True

    assert response["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    assert "my_export.xlsx" in response["Content-Disposition"]

    workbook = workbook_reader(
        read_streaming_response(response),
        read_only=True,
    )

    rows = list(workbook.worksheets[0].values)

    assert rows == [
        ("title", "description"),
        ("First", "First description"),
        ("Second", "Second description"),
        ("Third", "Third description"),
    ]


def test_streaming_export_handles_empty_queryset(
    api_client,
    workbook_reader,
):
    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200
    assert response.streaming is True

    workbook = workbook_reader(
        read_streaming_response(response),
        read_only=True,
    )

    rows = list(workbook.worksheets[0].values)

    assert rows == [
        ("title", "description"),
    ]


def test_streaming_export_uses_queryset_iterator(
    api_client,
    monkeypatch,
):
    from django.db.models.query import QuerySet

    original_iterator = QuerySet.iterator
    iterator_calls = []

    def tracked_iterator(queryset, *args, **kwargs):
        if queryset.model is ExampleModel:
            iterator_calls.append(kwargs.get("chunk_size"))

        return original_iterator(queryset, *args, **kwargs)

    monkeypatch.setattr(
        QuerySet,
        "iterator",
        tracked_iterator,
    )

    ExampleModel.objects.create(
        title="Iterator test",
        description="Checking iterator usage",
    )

    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200

    for _chunk in response.streaming_content:
        pass

    assert iterator_calls == [2000]


def test_streaming_export_handles_many_records(
    api_client,
    workbook_reader,
):
    record_count = 1500

    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index}",
            )
            for index in range(record_count)
        ]
    )

    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200

    workbook = workbook_reader(
        read_streaming_response(response),
        read_only=True,
    )

    rows = workbook.worksheets[0].iter_rows(values_only=True)

    assert next(rows) == ("title", "description")

    exported_rows = list(rows)

    assert len(exported_rows) == record_count
    assert exported_rows[0] == (
        "Record 0",
        "Description 0",
    )
    assert exported_rows[-1] == (
        f"Record {record_count - 1}",
        f"Description {record_count - 1}",
    )


def test_streaming_export_memory_growth(api_client):
    import tracemalloc

    def measure_peak_memory():
        gc.collect()
        tracemalloc.start()

        try:
            response = api_client.get("/examples/export-xlsx/")
            assert response.status_code == 200

            for _chunk in response.streaming_content:
                pass

            _, peak = tracemalloc.get_traced_memory()
            response.close()

            return peak
        finally:
            tracemalloc.stop()

    # Warm-up
    ExampleModel.objects.create(
        title="Warmup",
        description="Warmup",
    )
    measure_peak_memory()
    ExampleModel.objects.all().delete()

    # Small dataset
    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index}",
            )
            for index in range(500)
        ]
    )

    small_peak = measure_peak_memory()
    ExampleModel.objects.all().delete()

    # Large dataset
    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index}",
            )
            for index in range(20000)
        ]
    )

    large_peak = measure_peak_memory()

    growth_mb = (large_peak - small_peak) / (1024 * 1024)

    print(f"\n500 records peak: {small_peak / 1024 / 1024:.2f} MB")
    print(f"20000 records peak: {large_peak / 1024 / 1024:.2f} MB")
    print(f"Memory growth: {growth_mb:.2f} MB")

    assert growth_mb < 14, (
        f"Memory grew by {growth_mb:.2f} MB "
        "when increasing records from 500 to 20000."
    )


def test_streaming_export_rss_memory_growth(api_client):
    # Warm-up
    ExampleModel.objects.create(
        title="Warmup",
        description="Warmup",
    )

    measure_peak_rss(api_client)
    ExampleModel.objects.all().delete()

    # Small dataset
    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index}",
            )
            for index in range(500)
        ]
    )

    small_peak = measure_peak_rss(api_client)
    ExampleModel.objects.all().delete()
    gc.collect()

    # Large dataset
    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index}",
            )
            for index in range(20000)
        ]
    )

    large_peak = measure_peak_rss(api_client)

    small_mb = small_peak / (1024 * 1024)
    large_mb = large_peak / (1024 * 1024)
    growth_mb = (large_peak - small_peak) / (1024 * 1024)

    print("\n========== RSS MEMORY RESULTS ==========")
    print(f"500 records:    {small_mb:.2f} MB")
    print(f"20,000 records: {large_mb:.2f} MB")
    print(f"Difference:     {growth_mb:.2f} MB")
    print("========================================")



@pytest.mark.parametrize(
    ("chunk_size", "error"),
    [
        (True, TypeError),
        ("200", TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_streaming_export_rejects_invalid_chunk_size(
    api_client,
    monkeypatch,
    chunk_size,
    error,
):
    monkeypatch.setattr(ExampleViewSet, "xlsx_iterator_chunk_size", chunk_size)

    with pytest.raises(error, match="xlsx_iterator_chunk_size"):
        api_client.get("/examples/export-xlsx/")


def test_streaming_export_requires_queryset_iterator(api_client, monkeypatch):
    monkeypatch.setattr(ExampleViewSet, "get_queryset", lambda self: [])

    with pytest.raises(TypeError, match="supports iterator"):
        api_client.get("/examples/export-xlsx/")


def test_streaming_export_rejects_header_images(api_client, monkeypatch):
    monkeypatch.setattr(ExampleViewSet, "header", {"img": "unused.png"})

    with pytest.raises(NotImplementedError, match="Images in the XLSX header"):
        api_client.get("/examples/export-xlsx/")


def test_streaming_export_applies_workbook_options(
    api_client,
    workbook_reader,
    monkeypatch,
):
    ExampleModel.objects.create(title="Styled", description="Styled row")
    monkeypatch.setattr(
        ExampleViewSet,
        "header",
        {
            "tab_title": "Streaming report",
            "header_title": "Report title",
            "height": 30,
            "style": {"font": {"bold": True}},
        },
    )
    monkeypatch.setattr(
        ExampleViewSet,
        "column_header",
        {
            "titles": ["Name", "Details"],
            "height": 25,
            "column_width": [12],
            "style": {"font": {"italic": True}},
        },
    )
    monkeypatch.setattr(
        ExampleViewSet,
        "body",
        {"height": 18, "style": {"font": {"bold": True}}},
    )
    monkeypatch.setattr(ExampleViewSet, "xlsx_auto_filter", True)
    monkeypatch.setattr(
        ExampleViewSet,
        "sheet_view_options",
        {"showGridLines": False},
    )

    response = api_client.get("/examples/export-xlsx/")
    workbook = workbook_reader(
        read_streaming_response(response),
        read_only=False,
    )
    worksheet = workbook["Streaming report"]

    assert worksheet["A1"].value == "Report title"
    assert worksheet["A1"].font.bold is True
    assert worksheet["A2"].value == "Name"
    assert worksheet["A2"].font.italic is True
    assert worksheet["A3"].font.bold is True
    assert worksheet.row_dimensions[1].height == 30
    assert worksheet.row_dimensions[2].height == 25
    assert worksheet.row_dimensions[3].height == 18
    assert worksheet.column_dimensions["A"].width == 12
    assert worksheet.column_dimensions["B"].width == 13
    assert worksheet.auto_filter.ref == "A2:B3"
    assert worksheet.sheet_view.showGridLines is False


def test_streaming_export_can_omit_report_title(
    api_client,
    workbook_reader,
    monkeypatch,
):
    ExampleModel.objects.create(title="First", description="Second")
    monkeypatch.setattr(
        ExampleViewSet,
        "header",
        {"use_header": False, "tab_title": "No title"},
    )
    monkeypatch.setattr(
        ExampleViewSet,
        "column_header",
        {"column_width": 24},
    )

    response = api_client.get("/examples/export-xlsx/")
    workbook = workbook_reader(read_streaming_response(response), read_only=False)
    worksheet = workbook["No title"]

    assert worksheet["A1"].value == "title"
    assert worksheet["A2"].value == "First"
    assert worksheet.column_dimensions["A"].width == 24


def test_streaming_export_handles_custom_columns_and_mappings(
    api_client,
    workbook_reader,
    monkeypatch,
):
    ExampleModel.objects.create(title="original", description="description")
    monkeypatch.setattr(
        ExampleViewSet,
        "xlsx_custom_cols",
        {"extra": {"label": "Extra column"}},
    )
    monkeypatch.setattr(
        ExampleViewSet,
        "xlsx_custom_mappings",
        {"title": lambda value: value.upper()},
    )
    monkeypatch.setattr(ExampleViewSet, "xlsx_specify_headers", ["title", "extra"])
    monkeypatch.setattr(ExampleViewSet, "xlsx_ignore_headers", [])

    response = api_client.get("/examples/export-xlsx/")
    workbook = workbook_reader(read_streaming_response(response))
    rows = list(workbook.active.values)

    assert rows == [
        ("title", "Extra column"),
        ("ORIGINAL", None),
    ]


def test_streaming_export_applies_row_color(api_client, workbook_reader, monkeypatch):
    class ColoredSerializer(serializers.ModelSerializer):
        row_color = serializers.SerializerMethodField()

        def get_row_color(self, instance):
            return "FFFF00"

        class Meta:
            model = ExampleModel
            fields = ("title", "description", "row_color")

    ExampleModel.objects.create(title="Colored", description="row")
    monkeypatch.setattr(ExampleViewSet, "serializer_class", ColoredSerializer)

    response = api_client.get("/examples/export-xlsx/")
    workbook = workbook_reader(read_streaming_response(response), read_only=False)
    worksheet = workbook.active

    assert worksheet.max_column == 2
    assert worksheet["A2"].value == "Colored"
    assert worksheet["A2"].fill.fgColor.rgb.endswith("FFFF00")
    assert worksheet["B2"].fill.fgColor.rgb.endswith("FFFF00")


def test_streaming_export_uses_filename_fallback(
    api_client,
    monkeypatch,
):
    monkeypatch.setattr(ExampleViewSet, "get_filename", None)
    monkeypatch.setattr(ExampleViewSet, "filename", "fallback.xlsx")

    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200
    assert "fallback.xlsx" in response["Content-Disposition"]


def test_streaming_export_closes_temporary_file_when_save_fails(
    api_client,
    monkeypatch,
):
    class TemporaryFileStub:
        closed = False

        def close(self):
            self.closed = True

    temporary_file = TemporaryFileStub()

    def fail_save(self, file_object):
        raise OSError("disk write failed")

    monkeypatch.setattr(streaming_module, "TemporaryFile", lambda **kwargs: temporary_file)
    monkeypatch.setattr(Workbook, "save", fail_save)

    with pytest.raises(OSError, match="disk write failed"):
        api_client.get("/examples/export-xlsx/")

    assert temporary_file.closed is True


@pytest.mark.parametrize(
    ("mapping", "value", "expected"),
    [
        ("label", {"label": "mapped"}, "mapped"),
        (lambda value: value.upper(), "mapped", "MAPPED"),
    ],
)
def test_write_only_cell_supports_custom_mappings(mapping, value, expected):
    worksheet = Workbook(write_only=True).create_sheet()
    field = XLSXField(
        key="value",
        value=value,
        field=CharField(),
        style=XLSXStyle(),
        mapping=mapping,
        cell_style=None,
    )

    cell = field.write_only_cell(worksheet)

    assert isinstance(cell, WriteOnlyCell)
    assert cell.value == expected


def test_write_only_number_cell_preserves_number_format():
    worksheet = Workbook(write_only=True).create_sheet()
    field = XLSXNumberField(
        key="count",
        value="42",
        field=IntegerField(),
        style=XLSXStyle(),
        mapping="",
        cell_style=None,
    )

    cell = field.write_only_cell(worksheet)

    assert isinstance(cell, WriteOnlyCell)
    assert cell.value == 42
    assert cell.number_format == "0"


def test_write_only_date_cell_preserves_number_format():
    worksheet = Workbook(write_only=True).create_sheet()
    field = XLSXDateField(
        key="created",
        value="2025-01-02T03:04:05",
        field=DateTimeField(),
        style=XLSXStyle(),
        mapping="",
        cell_style=None,
    )

    cell = field.write_only_cell(worksheet)

    assert isinstance(cell, WriteOnlyCell)
    assert cell.value.year == 2025
    assert cell.number_format == "yyyy-mm-dd h:mm:ss"

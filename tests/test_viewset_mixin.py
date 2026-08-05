import datetime as dt

import pytest
from rest_framework.test import APIClient
from time_machine import TimeMachineFixture

from tests.testapp.models import AllFieldsModel, ExampleModel, SecretFieldModel, Tag

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def test_simple_viewset_model(api_client, workbook_reader):
    ExampleModel.objects.create(title="test 1", description="This is a test")
    ExampleModel.objects.create(title="test 2", description="Another test")
    ExampleModel.objects.create(title="test 3", description="Testing this out")

    response = api_client.get("/examples/")

    assert response.status_code == 200
    assert (
        response.headers["Content-Type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet; charset=utf-8"
    )
    assert (
        response.headers["content-disposition"] == "attachment; filename=my_export.xlsx"
    )

    wb = workbook_reader(response.content)

    assert len(wb.worksheets) == 1
    sheet = wb.worksheets[0]
    rows = list(sheet.rows)
    assert len(rows) == 4
    r0, r1, r2, r3 = rows

    assert len(r0) == 2
    assert r0[0].value == "title"
    assert r0[1].value == "description"

    assert len(r1) == 2
    assert r1[0].value == "test 1"
    assert r1[1].value == "This is a test"

    assert len(r2) == 2
    assert r2[0].value == "test 2"
    assert r2[1].value == "Another test"

    assert len(r3) == 2
    assert r3[0].value == "test 3"
    assert r3[1].value == "Testing this out"


def test_all_fields_viewset(
    api_client, time_machine: TimeMachineFixture, workbook_reader
):
    time_machine.move_to(dt.datetime(2023, 9, 10, 15, 44, 37))
    instance = AllFieldsModel.objects.create(title="Hello", age=36, is_active=True)
    instance.tags.set(
        [
            Tag.objects.create(name="test"),
            Tag.objects.create(name="example"),
        ]
    )
    response = api_client.get("/all-fields/")
    assert response.status_code == 200

    wb = workbook_reader(response.content)
    sheet = wb.worksheets[0]
    rows = list(sheet.rows)
    assert len(rows) == 2
    r0, r1 = rows

    assert [col.value for col in r0] == [
        "title",
        "created_at",
        "updated_date",
        "updated_time",
        "age",
        "is_active",
        "tags",
    ]
    assert [col.value for col in r1] == [
        "Hello",
        dt.datetime(2023, 9, 10, 15, 44, 37),
        dt.datetime(2023, 9, 10, 0, 0),
        dt.time(15, 44, 37),
        36,
        True,
        "test, example",
    ]


def test_secret_field_viewset(api_client, workbook_reader):
    SecretFieldModel.objects.create(title="foo", secret="bar")

    response = api_client.get("/secret-field/")
    assert response.status_code == 200

    wb = workbook_reader(response.content)
    sheet = wb.worksheets[0]
    rows = list(sheet.rows)
    assert len(rows) == 2
    header, data = rows

    # Check that the secret field is not included in the header or data
    assert [col.value for col in header] == ["title"]
    assert [col.value for col in data] == ["foo"]


def test_dynamic_field_viewset(api_client, workbook_reader):
    response = api_client.get("/dynamic-field/")
    assert response.status_code == 200

    wb = workbook_reader(response.content)
    sheet = wb.worksheets[0]

    header, data = list(sheet.rows)

    header_values = [cell.value for cell in header]
    assert header_values == ["field_1", "field_2", "field_99", "field_98"]

    row_1_values = [cell.value for cell in data]
    assert row_1_values == ["YUL", "CDG", "YYZ", "MAR"]


def test_auto_filter_viewset(api_client, workbook_reader):
    ExampleModel.objects.create(title="test 1", description="This is a test")

    response = api_client.get("/auto-filter/")
    assert response.status_code == 200

    # Note: auto_filter.ref is not available for read-only workbooks
    wb = workbook_reader(response.content, read_only=False)
    sheet = wb.worksheets[0]

    assert sheet.auto_filter.ref == "A1:B2"


def test_nested_serializer_viewset(api_client, workbook_reader):
    """Covers nested serializer flattening."""
    response = api_client.get("/nested/")
    assert response.status_code == 200

    wb = workbook_reader(response.content)
    sheet = wb.worksheets[0]
    rows = list(sheet.rows)
    assert len(rows) == 3

    header = [col.value for col in rows[0]]
    assert header == ["title", "author.name", "author.email"]

    row1 = [col.value for col in rows[1]]
    assert row1 == ["Post 1", "Alice", "alice@example.com"]

    row2 = [col.value for col in rows[2]]
    assert row2 == ["Post 2", "Bob", "bob@example.com"]


def test_nested_serializer_with_labels(api_client, workbook_reader):
    """Covers nested serializer with use_labels."""
    response = api_client.get("/nested-labels/")
    assert response.status_code == 200

    wb = workbook_reader(response.content)
    sheet = wb.worksheets[0]
    rows = list(sheet.rows)

    header = [col.value for col in rows[0]]
    assert header == ["Title", "Author > Author Name", "Author > Email Address"]


def test_custom_cols_viewset(api_client, workbook_reader):
    """Covers custom_cols header creation."""
    response = api_client.get("/custom-cols/")
    assert response.status_code == 200

    wb = workbook_reader(response.content)
    sheet = wb.worksheets[0]
    rows = list(sheet.rows)

    header = [col.value for col in rows[0]]
    assert "Extra Column" in header
    assert "title" in header
    assert "description" in header


def test_column_titles_override(api_client, workbook_reader):
    """Covers column_titles override."""
    ExampleModel.objects.create(title="test", description="desc")

    response = api_client.get("/column-titles/")
    assert response.status_code == 200

    wb = workbook_reader(response.content)
    sheet = wb.worksheets[0]
    rows = list(sheet.rows)

    header = [col.value for col in rows[0]]
    assert header == ["Title Override", "Description Override"]


def test_column_width_as_list(api_client, workbook_reader):
    """Covers column_width as a list."""
    ExampleModel.objects.create(title="test", description="desc")

    response = api_client.get("/column-width-list/")
    assert response.status_code == 200

    wb = workbook_reader(response.content, read_only=False)
    sheet = wb.worksheets[0]

    assert sheet.column_dimensions["A"].width == 10
    assert sheet.column_dimensions["B"].width == 30


def test_row_color(api_client, workbook_reader):
    """Covers row_color handling."""
    response = api_client.get("/row-color/")
    assert response.status_code == 200

    wb = workbook_reader(response.content, read_only=False)
    sheet = wb.worksheets[0]
    rows = list(sheet.rows)

    # row_color should not appear as a column header
    header = [col.value for col in rows[0]]
    assert "row_color" not in header

    # The data row should have the fill color applied
    data_row = rows[1]
    assert data_row[0].fill.start_color.rgb == "00FF0000"


def test_use_labels_viewset(api_client, workbook_reader):
    """Covers use_labels on simple fields."""
    ExampleModel.objects.create(title="test", description="desc")

    response = api_client.get("/use-labels/")
    assert response.status_code == 200

    wb = workbook_reader(response.content)
    sheet = wb.worksheets[0]
    rows = list(sheet.rows)

    header = [col.value for col in rows[0]]
    assert header == ["Title", "Description"]


class TestSpecifyHeaders:
    @pytest.fixture
    def rows_at(self, api_client, workbook_reader):
        """Return the header and first data row values of the export at ``url``."""

        def _rows_at(url):
            response = api_client.get(url)
            assert response.status_code == 200

            wb = workbook_reader(response.content)
            rows = list(wb.worksheets[0].rows)
            return (
                [cell.value for cell in rows[0]],
                [cell.value for cell in rows[1]] if len(rows) > 1 else [],
            )

        return _rows_at

    def test_specified_fields_only(self, rows_at):
        """Only the specified fields are exported, with their values."""
        AllFieldsModel.objects.create(title="Hello", age=36)

        assert rows_at("/specify-headers/") == (["title"], ["Hello"])

    def test_unknown_field_is_ignored(self, rows_at):
        """Names that don't match a serializer field are silently dropped.

        Columns keep the serializer's declaration order, not the order given in
        ``xlsx_specify_headers``.
        """
        AllFieldsModel.objects.create(title="Hello", age=36)

        assert rows_at("/specify-headers-order/") == (["title", "age"], ["Hello", 36])

    def test_with_ignore_headers(self, rows_at):
        """``xlsx_ignore_headers`` wins over ``xlsx_specify_headers``."""
        AllFieldsModel.objects.create(title="Hello", age=36)

        assert rows_at("/specify-and-ignore-headers/") == (["title"], ["Hello"])

    def test_nested_field(self, rows_at):
        """A nested field can be specified with a dotted path."""
        assert rows_at("/specify-nested-headers/") == (
            ["title", "author.name"],
            ["Post 1", "Alice"],
        )

    def test_nested_serializer(self, rows_at):
        """Specifying a nested serializer includes all of its fields."""
        assert rows_at("/specify-nested-parent-header/") == (
            ["author.name", "author.email"],
            ["Alice", "alice@example.com"],
        )

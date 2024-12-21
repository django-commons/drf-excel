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

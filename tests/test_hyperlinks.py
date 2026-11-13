import pytest
from openpyxl import Workbook
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.test import APIClient

from drf_excel.fields import XLSXField
from drf_excel.mixins import XLSXHyperlinkMixin
from drf_excel.renderers import XLSXRenderer
from drf_excel.utilities import XLSXStyle
from tests.testapp.models import ExampleModel


class HyperlinkSerializer(serializers.Serializer):
    title = serializers.CharField()
    website = serializers.CharField()


class HyperlinkView(XLSXHyperlinkMixin, GenericAPIView):
    serializer_class = HyperlinkSerializer

    def get_cell_hyperlink(self, row, column):
        if column == "website":
            return row.get("website")

        return None


class TestXLSXHyperlinkField:
    def test_regular_cell(self, worksheet):
        field = XLSXField(
            key="website",
            value="example.com",
            field=serializers.CharField(),
            style=XLSXStyle(),
            mapping="",
            cell_style=None,
            hyperlink="https://example.com",
        )
        cell = field.cell(worksheet, 1, 1)

        assert cell.value == "example.com"
        assert cell.hyperlink.target == "https://example.com"

    def test_write_only_cell(self):
        worksheet = Workbook(write_only=True).create_sheet()
        field = XLSXField(
            key="website",
            value="example.com",
            field=serializers.CharField(),
            style=XLSXStyle(),
            mapping="",
            cell_style=None,
            hyperlink="https://example.com",
        )
        cell = field.write_only_cell(worksheet)

        assert cell.value == "example.com"
        assert cell.hyperlink.target == "https://example.com"


class TestXLSXHyperlinkMixin:
    def test_default_get_cell_hyperlink_returns_none(self):
        assert XLSXHyperlinkMixin().get_cell_hyperlink({}, "website") is None

    def test_get_cell_hyperlink(self):
        view = HyperlinkView()

        assert (
            view._get_cell_hyperlink(
                {"website": "https://example.com"},
                "website",
            )
            == "https://example.com"
        )

    def test_get_cell_hyperlink_returns_none(self):
        view = HyperlinkView()

        assert (
            view._get_cell_hyperlink(
                {"title": "Example"},
                "title",
            )
            is None
        )

    def test_get_cell_hyperlink_rejects_invalid_type(self):
        class InvalidView(XLSXHyperlinkMixin):
            def get_cell_hyperlink(self, row, column):
                return 123

        with pytest.raises(TypeError):
            InvalidView()._get_cell_hyperlink({}, "website")


def test_renderer_adds_hyperlinks(workbook_reader):
    class MyView(HyperlinkView):
        @staticmethod
        def get_serializer(*args, **kwargs):
            return HyperlinkSerializer()

    response = Response(
        [
            {
                "title": "Example",
                "website": "https://example.com",
            },
            {
                "title": "Django",
                "website": "https://www.djangoproject.com",
            },
        ]
    )

    renderer = XLSXRenderer()
    result = renderer.render(
        response.data,
        renderer_context={"view": MyView()},
    )

    workbook = workbook_reader(result, read_only=False)
    worksheet = workbook.active

    assert worksheet["B2"].hyperlink.target == "https://example.com"
    assert worksheet["B3"].hyperlink.target == "https://www.djangoproject.com"


@pytest.mark.django_db
def test_queryset_export_adds_hyperlinks(workbook_reader):
    ExampleModel.objects.create(
        title="Example",
        description="Example description",
    )

    response = APIClient().get("/hyperlinks/")

    assert response.status_code == 200
    assert response.streaming is True

    workbook = workbook_reader(response, read_only=False)
    worksheet = workbook.active

    assert worksheet["A2"].value == "Example"
    assert worksheet["A2"].hyperlink.target == "https://example.com"

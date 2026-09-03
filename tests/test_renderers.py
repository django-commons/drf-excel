from django.utils.translation import gettext_lazy as _
from PIL import Image
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from drf_excel.renderers import XLSXRenderer


class MySerializer(serializers.Serializer):
    title = serializers.CharField()


class MyBaseView(GenericAPIView):
    serializer_class = MySerializer

    def retrieve(self, request, *args, **kwargs):
        return Response({"title": "example"})


class TestXLSXRenderer:
    renderer = XLSXRenderer()

    def test_validation_error(self):
        assert self.renderer.render({"detail": "invalid"}) == '{"detail": "invalid"}'

    def test_validation_with_successful_response(self):
        """
        A successful (200) response whose payload happens to contain a
        "detail" key - a perfectly ordinary field name for real data -
        should still be treated as valid data, not short-circuited to raw
        JSON.

        https://github.com/django-commons/drf-excel/issues/26
        """
        data = {"detail": "Successfully processed 3 records", "count": 3}
        response = Response(data, status=200)
        response.renderer_context = {"response": response}
        assert self.renderer._check_validation_data(data, response.renderer_context)

    def test_validation_with_custom_error_response(self):
        """
        A real error response from a custom exception handler that
        doesn't use Django REST Framework's "detail" convention should
        still be treated as an error, based on the response status code.
        """
        data = {"error_code": "RATE_LIMITED", "message": "Too many requests"}
        response = Response(data, status=429)
        response.renderer_context = {"response": response}
        assert not self.renderer._check_validation_data(data, response.renderer_context)

    def test_none(self):
        assert self.renderer.render(None) == b""

    def test_with_header_attribute(self, tmp_path, workbook_reader):
        image_path = tmp_path / "image.png"
        with Image.new(mode="RGB", size=(100, 100), color="blue") as img:
            img.save(image_path, format="png")

        class MyView(MyBaseView):
            header = {
                "use_header": True,
                "header_title": "My Header",
                "tab_title": "My Tab",
                "img": str(image_path),
                "style": {"font": {"name": "Arial"}},
            }

        result = self.renderer.render({}, renderer_context={"view": MyView})
        wb = workbook_reader(result)
        sheet = wb.worksheets[0]
        rows = list(sheet.rows)
        assert len(rows) == 1
        row0_col0 = rows[0][0]
        assert row0_col0.value == "My Header"
        assert row0_col0.font.name == "Arial"

    def test_lazy_string_promise_value(self, workbook_reader):
        """Covers Promise handling in _flatten_data."""

        class LazySerializer(serializers.Serializer):
            title = serializers.CharField()

        class LazyView(MyBaseView):
            serializer_class = LazySerializer

            @staticmethod
            def get_serializer(*args, **kwargs):
                return LazySerializer()

        result = self.renderer.render(
            [{"title": _("Hello")}],
            renderer_context={"view": LazyView},
        )
        wb = workbook_reader(result)
        sheet = wb.worksheets[0]
        rows = list(sheet.rows)
        assert rows[1][0].value == "Hello"

    def test_render_single_dict_result(self, workbook_reader):
        """Covers dict results branch in render."""

        class DictView(MyBaseView):
            @staticmethod
            def get_serializer(*args, **kwargs):
                return MySerializer()

        result = self.renderer.render(
            {"title": "single"},
            renderer_context={"view": DictView},
        )
        wb = workbook_reader(result)
        sheet = wb.worksheets[0]
        rows = list(sheet.rows)
        assert len(rows) == 2
        assert rows[1][0].value == "single"

    def test_row_color_as_serializer_field(self, workbook_reader):
        """Covers row_color skip in header and body loops."""

        class RowColorSerializer(serializers.Serializer):
            title = serializers.CharField()
            row_color = serializers.CharField()

        class RowColorView(MyBaseView):
            serializer_class = RowColorSerializer

            @staticmethod
            def get_serializer(*args, **kwargs):
                return RowColorSerializer()

        result = self.renderer.render(
            [{"title": "test", "row_color": "FF0000"}],
            renderer_context={"view": RowColorView},
        )
        wb = workbook_reader(result)
        sheet = wb.worksheets[0]
        rows = list(sheet.rows)
        header = [col.value for col in rows[0]]
        # row_color should be skipped in headers
        assert "row_color" not in header
        assert header == ["title"]

    def test_nested_serializer_no_label_with_use_labels(self, workbook_reader):
        """Covers fallback to key when field has no label with use_labels."""

        class InnerSerializer(serializers.Serializer):
            name = serializers.CharField()

        class OuterSerializer(serializers.Serializer):
            title = serializers.CharField(label="Title")
            author = InnerSerializer(label="Author")

        class NestedNoLabelView(MyBaseView):
            serializer_class = OuterSerializer
            xlsx_use_labels = True

            @staticmethod
            def get_serializer(*args, **kwargs):
                s = OuterSerializer()
                # Remove label from inner field to trigger _get_label -> False
                s.fields["author"].fields["name"].label = None
                return s

        result = self.renderer.render(
            [{"title": "test", "author": {"name": "Alice"}}],
            renderer_context={"view": NestedNoLabelView},
        )
        wb = workbook_reader(result)
        sheet = wb.worksheets[0]
        rows = list(sheet.rows)
        header = [col.value for col in rows[0]]
        assert "Title" in header
        # When label is None, _get_label returns False, so key is used
        assert "author.name" in header

    def test_render_no_header(self, workbook_reader):
        """Covers use_header=False path."""

        class NoHeaderView(MyBaseView):
            header = {"use_header": False}

            @staticmethod
            def get_serializer(*args, **kwargs):
                return MySerializer()

        result = self.renderer.render(
            [{"title": "test"}],
            renderer_context={"view": NoHeaderView},
        )
        wb = workbook_reader(result)
        sheet = wb.worksheets[0]
        rows = list(sheet.rows)
        # Without header, first row is column headers, second is data
        assert len(rows) == 2
        assert rows[0][0].value == "title"
        assert rows[1][0].value == "test"

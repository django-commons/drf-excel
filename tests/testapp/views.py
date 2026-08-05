from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from drf_excel.mixins import XLSXFileMixin
from drf_excel.renderers import XLSXRenderer

from .models import AllFieldsModel, ExampleModel, SecretFieldModel
from .serializers import (
    AllFieldsSerializer,
    DynamicFieldSerializer,
    ExampleSerializer,
    NestedSerializer,
    SecretFieldSerializer,
)


class ExampleViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = ExampleModel.objects.all()
    serializer_class = ExampleSerializer
    renderer_classes = (XLSXRenderer,)
    filename = "my_export.xlsx"


class AllFieldsViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = AllFieldsModel.objects.all()
    serializer_class = AllFieldsSerializer
    renderer_classes = (XLSXRenderer,)
    filename = "al_fileds.xlsx"


class SecretFieldViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = SecretFieldModel.objects.all()
    serializer_class = SecretFieldSerializer
    renderer_classes = (XLSXRenderer,)
    filename = "secret.xlsx"


class DynamicFieldViewSet(XLSXFileMixin, GenericViewSet):
    serializer_class = DynamicFieldSerializer
    renderer_classes = (XLSXRenderer,)
    filename = "dynamic_field.xlsx"

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data={
                "field_1": "YUL",
                "field_2": "CDG",
                "field_55": "LHR",
                "field_98": "MAR",
                "field_99": "YYZ",
            }
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class NestedViewSet(XLSXFileMixin, GenericViewSet):
    serializer_class = NestedSerializer
    renderer_classes = (XLSXRenderer,)
    filename = "nested.xlsx"

    def list(self, request, *args, **kwargs):
        return Response(
            [
                {
                    "title": "Post 1",
                    "author": {"name": "Alice", "email": "alice@example.com"},
                },
                {
                    "title": "Post 2",
                    "author": {"name": "Bob", "email": "bob@example.com"},
                },
            ]
        )


class NestedLabelsViewSet(NestedViewSet):
    xlsx_use_labels = True


class CustomColsViewSet(XLSXFileMixin, GenericViewSet):
    serializer_class = ExampleSerializer
    renderer_classes = (XLSXRenderer,)
    filename = "custom_cols.xlsx"
    xlsx_custom_cols = {
        "extra": {"label": "Extra Column", "formatter": lambda row: "computed"},
    }

    def list(self, request, *args, **kwargs):
        return Response([{"title": "test", "description": "desc"}])

    def get_serializer(self, *args, **kwargs):
        return ExampleSerializer()


class ColumnTitlesViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = ExampleModel.objects.all()
    serializer_class = ExampleSerializer
    renderer_classes = (XLSXRenderer,)
    column_header = {
        "titles": ["Title Override", "Description Override"],
    }


class ColumnWidthListViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = ExampleModel.objects.all()
    serializer_class = ExampleSerializer
    renderer_classes = (XLSXRenderer,)
    column_header = {
        "column_width": [10, 30],
    }


class RowColorViewSet(XLSXFileMixin, GenericViewSet):
    serializer_class = ExampleSerializer
    renderer_classes = (XLSXRenderer,)
    filename = "row_color.xlsx"

    def list(self, request, *args, **kwargs):
        return Response(
            [
                {"title": "colored", "description": "row", "row_color": "FF0000"},
            ]
        )

    def get_serializer(self, *args, **kwargs):
        return ExampleSerializer()


class UseLabelsViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = ExampleModel.objects.all()
    serializer_class = ExampleSerializer
    renderer_classes = (XLSXRenderer,)
    xlsx_use_labels = True


class AutoFilterViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = ExampleModel.objects.all()
    serializer_class = ExampleSerializer
    renderer_classes = (XLSXRenderer,)

    xlsx_auto_filter = True


class SpecifyHeadersViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = AllFieldsModel.objects.all()
    serializer_class = AllFieldsSerializer
    renderer_classes = (XLSXRenderer,)

    xlsx_specify_headers = ["title"]


class SpecifyHeadersOrderViewSet(SpecifyHeadersViewSet):
    # Declared in a different order than the serializer, and with a field that
    # doesn't exist on the serializer
    xlsx_specify_headers = ["age", "title", "does_not_exist"]


class SpecifyAndIgnoreHeadersViewSet(SpecifyHeadersViewSet):
    xlsx_specify_headers = ["title", "age"]
    xlsx_ignore_headers = ["age"]


class SpecifyNestedHeadersViewSet(NestedViewSet):
    # Nested field addressed with a dotted path
    xlsx_specify_headers = ["title", "author.name"]


class SpecifyNestedParentHeaderViewSet(NestedViewSet):
    # Nested serializer addressed by its own key
    xlsx_specify_headers = ["author"]

from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from drf_excel.mixins import XLSXFileMixin
from drf_excel.renderers import XLSXRenderer

from .models import AllFieldsModel, ExampleModel, SecretFieldModel
from .serializers import (
    AllFieldsSerializer,
    DynamicFieldSerializer,
    ExampleSerializer,
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

from django.http import Http404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

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


class DynamicFieldViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    serializer_class = DynamicFieldSerializer
    renderer_classes = (XLSXRenderer,)
    filename = "dynamic_field.xlsx"
    queryset = [{
        "field_1": "YUL",
        "field_2": "CDG",
        "field_55": "LHR",
        "field_98": "MAR",
        "field_99": "YYZ",
    }]

    def get_object(self):
        """Get object by index from the list assigned to queryset."""

        try:
            return self.queryset[int(self.kwargs["pk"])]
        except (KeyError, ValueError):
            raise Http404


class AutoFilterViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = ExampleModel.objects.all()
    serializer_class = ExampleSerializer
    renderer_classes = (XLSXRenderer,)

    xlsx_auto_filter = True


class PlainResponseView(GenericAPIView):
    serializer_class = ExampleSerializer

    def get(self, request):
        """Get response with built-in dict not from serializer data."""

        return Response({"title": "Test Title", "description": "Test Description"})

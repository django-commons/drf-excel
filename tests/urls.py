from rest_framework import routers

from .testapp.views import (
    AllFieldsViewSet,
    AutoFilterViewSet,
    ColumnTitlesViewSet,
    ColumnWidthListViewSet,
    CustomColsViewSet,
    DynamicFieldViewSet,
    ExampleViewSet,
    NestedLabelsViewSet,
    NestedViewSet,
    RowColorViewSet,
    SecretFieldViewSet,
    SpecifyAndIgnoreHeadersViewSet,
    SpecifyHeadersOrderViewSet,
    SpecifyHeadersViewSet,
    SpecifyNestedHeadersViewSet,
    SpecifyNestedParentHeaderViewSet,
    UseLabelsViewSet,
)

router = routers.SimpleRouter()
router.register(r"examples", ExampleViewSet)
router.register(r"all-fields", AllFieldsViewSet)
router.register(r"secret-field", SecretFieldViewSet)
router.register(r"dynamic-field", DynamicFieldViewSet, basename="dynamic-field")
router.register(r"auto-filter", AutoFilterViewSet, basename="auto-filter")
router.register(r"nested", NestedViewSet, basename="nested")
router.register(r"nested-labels", NestedLabelsViewSet, basename="nested-labels")
router.register(r"custom-cols", CustomColsViewSet, basename="custom-cols")
router.register(r"column-titles", ColumnTitlesViewSet, basename="column-titles")
router.register(
    r"column-width-list", ColumnWidthListViewSet, basename="column-width-list"
)
router.register(r"row-color", RowColorViewSet, basename="row-color")
router.register(r"use-labels", UseLabelsViewSet, basename="use-labels")
router.register(r"specify-headers", SpecifyHeadersViewSet, basename="specify-headers")
router.register(
    r"specify-headers-order",
    SpecifyHeadersOrderViewSet,
    basename="specify-headers-order",
)
router.register(
    r"specify-and-ignore-headers",
    SpecifyAndIgnoreHeadersViewSet,
    basename="specify-and-ignore-headers",
)
router.register(
    r"specify-nested-headers",
    SpecifyNestedHeadersViewSet,
    basename="specify-nested-headers",
)
router.register(
    r"specify-nested-parent-header",
    SpecifyNestedParentHeaderViewSet,
    basename="specify-nested-parent-header",
)

urlpatterns = router.urls

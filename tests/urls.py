from rest_framework import routers

from .testapp.views import (
    AllFieldsViewSet,
    AutoFilterViewSet,
    DynamicFieldViewSet,
    ExampleViewSet,
    SecretFieldViewSet,
)

router = routers.SimpleRouter()
router.register(r"examples", ExampleViewSet)
router.register(r"all-fields", AllFieldsViewSet)
router.register(r"secret-field", SecretFieldViewSet)
router.register(r"dynamic-field", DynamicFieldViewSet, basename="dynamic-field")
router.register(r"auto-filter", AutoFilterViewSet, basename="auto-filter")

urlpatterns = router.urls

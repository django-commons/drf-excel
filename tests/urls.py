from rest_framework import routers

from .testapp.views import (
    AllFieldsViewSet,
    DynamicFieldViewSet,
    ExampleViewSet,
    SecretFieldViewSet,
    SpecifyHeadersViewSet,
)

router = routers.SimpleRouter()
router.register(r"examples", ExampleViewSet)
router.register(r"all-fields", AllFieldsViewSet)
router.register(r"secret-field", SecretFieldViewSet)
router.register(r"dynamic-field", DynamicFieldViewSet, basename="dynamic-field")
router.register(r"specify-headers", SpecifyHeadersViewSet, basename="specify-headers")

urlpatterns = router.urls

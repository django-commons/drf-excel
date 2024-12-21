from rest_framework import routers

from .testapp.views import (
    AllFieldsViewSet,
    DynamicFieldViewSet,
    ExampleViewSet,
    SecretFieldViewSet,
)

router = routers.SimpleRouter()
router.register(r"examples", ExampleViewSet)
router.register(r"all-fields", AllFieldsViewSet)
router.register(r"secret-field", SecretFieldViewSet)
router.register(r"dynamic-field", DynamicFieldViewSet, basename="dynamic-field")

urlpatterns = router.urls

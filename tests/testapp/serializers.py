from rest_framework import serializers

from .models import AllFieldsModel, ExampleModel, SecretFieldModel


class ExampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExampleModel
        fields = ("title", "description")


class AllFieldsSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(source="get_tag_names")

    class Meta:
        model = AllFieldsModel
        fields = (
            "title",
            "created_at",
            "updated_date",
            "updated_time",
            "age",
            "is_active",
            "tags",
        )


class SecretFieldSerializer(serializers.ModelSerializer):
    secret_external = serializers.CharField(write_only=True)

    class Meta:
        model = SecretFieldModel
        fields = ("title", "secret", "secret_external")

        extra_kwargs = {"secret": {"write_only": True}}


class DynamicFieldSerializer(serializers.Serializer):
    field_1 = serializers.CharField()
    field_2 = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Fields can be added dynamically
        self.fields["field_99"] = serializers.CharField()
        self.fields["field_98"] = serializers.CharField()

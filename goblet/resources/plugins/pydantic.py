from typing import Any, Optional, DictStrAny

from apispec import BasePlugin, APISpec
from pydantic import BaseModel


class PydanticPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__()
        self.spec: APISpec | None = None

    def init_spec(self, spec: APISpec) -> None:
        super().init_spec(spec)
        self.spec = spec

    def schema_helper(
        self,
        name: str,
        definition: dict,
        model: Optional[BaseModel] = None,
        **kwargs: Any
    ) -> Optional[DictStrAny]:
        if model is None:
            return None

        schema = model.schema(ref_template="#/components/schemas/{model}")

        # if "definitions" in schema:
        #     for (k, v) in schema["definitions"].items():
        #         self.spec.components.schema(k, v)
        #     del schema["definitions"]

        return schema

    def response_helper(self, response: dict, **kwargs: Any) -> Optional[DictStrAny]:
        self.resolve_schema(response)
        if "headers" in response:
            for header in response["headers"].values():
                self.resolve_schema(header)
        return response

    def resolve_schema(self, data):
        if not isinstance(data, dict):
            return

        if "schema" in data:
            data["schema"] = self.resolve_schema_dict(data["schema"])

    def resolve_schema_dict(self, schema):
        if isinstance(schema, dict):
            if schema.get("type") == "array" and "items" in schema:
                schema["items"] = self.resolve_schema_dict(schema["items"])
            if schema.get("type") == "object" and "properties" in schema:
                schema["properties"] = {
                    k: self.resolve_schema_dict(v)
                    for k, v in schema["properties"].items()
                }
            for keyword in ("oneOf", "anyOf", "allOf"):
                if keyword in schema:
                    schema[keyword] = [
                        self.resolve_schema_dict(s) for s in schema[keyword]
                    ]
            if "not" in schema:
                schema["not"] = self.resolve_schema_dict(schema["not"])
            return schema

        return self.get_model_schema(schema)

    def get_model_schema(self, model):
        return model.schema(ref_template="#/components/schemas/{model}")

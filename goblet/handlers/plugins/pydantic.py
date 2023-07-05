from typing import Any, Optional

from apispec import BasePlugin, APISpec
from pydantic import BaseModel
import copy


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
    ):
        if model is None:
            return None

        org_schema = model.schema(ref_template="#/definitions/{model}")
        schema = copy.deepcopy(org_schema)
        if "definitions" in schema:
            for k, v in schema["definitions"].items():
                if k not in self.spec.components.schemas:
                    self.spec.components.schema(k, v)
            del schema["definitions"]

        return schema

    def operation_helper(self, path=None, operations=None, **kwargs) -> None:
        self.resolve_operation_parameters(operations)
        return

    def resolve_operation_parameters(self, operations):
        """
        Handle pydantic paramters in operations
        """
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            if "parameters" in operation:
                operation["parameters"] = self.resolve_parameters(
                    operation["parameters"]
                )

    def resolve_parameters(self, parameters):
        """
        Handle Pydantic class paramters
        """
        resolved = []
        for parameter in parameters:
            if (
                isinstance(parameter, dict)
                and issubclass(type(parameter.get("schema", {})), BaseModel)
                and "in" in parameter
            ):
                schema_instance = parameter.pop("schema")
                model_params = self.resolve_pydantic_model(schema_instance)
                resolved.extend(model_params)
            else:
                resolved.append(parameter)
        return resolved

    def resolve_pydantic_model(self, model):
        """
        Extract Properties from pydantic model and convert into query params
        """
        schema = model.schema()
        params = []
        for key, value in schema["properties"].items():
            param = {
                "in": "query",
                "name": key,
                "type": value["type"],
                "required": key in schema.get("required", []),
            }
            if value["type"] == "array":
                param["items"] = value["items"]
            params.append(param)
        return params

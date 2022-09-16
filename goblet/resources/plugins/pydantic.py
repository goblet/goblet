from typing import Any, Union

from apispec import BasePlugin, APISpec
from apispec.exceptions import DuplicateComponentNameError
from pydantic import BaseModel


class PydanticPlugin(BasePlugin):
    """
    An APISpec plugin that will register Pydantic models with APISpec.
    Uses the built-in schema export provided by Pydantic with minor modifications to provide
    the right structure for OpenAPI.
    Example:
        from pydantic import BaseModel
        class MyModel(BaseModel):
            hello: str
            world: str
        spec = APISPec(plugins=[PydanticPlugin()])
        spec.components.schema("MyModel", model=MyModel)
    """

    def schema_helper(
        self, name: str, definition: dict, **kwargs: Any
    ) -> Union[dict, None]:
        model: Union[BaseModel, None] = kwargs.pop("model", None)
        if model:
            schema = model.schema(ref_template="#/components/schemas/{model}")

            # If the spec has passed, we probably have nested models to contend with.
            spec: Union[APISpec, None] = kwargs.pop("spec", None)
            if spec and "definitions" in schema:
                for (k, v) in schema["definitions"].items():
                    try:
                        spec.components.schema(k, v)
                    except DuplicateComponentNameError:
                        pass

            if "definitions" in schema:
                del schema["definitions"]

            return schema

        return None



# from apispec import BasePlugin, APISpec
# from pydantic import BaseModel
# from apispec.ext.marshmallow.openapi import OpenAPIConverter
# from apispec.ext.marshmallow.schema_resolver import SchemaResolver
# from apispec.ext.marshmallow.common import resolve_schema_instance, make_schema_key, resolve_schema_cls

# from apispec.utils import OpenAPIVersion


# def resolver(schema: type[Schema]) -> str:
#     """Default schema name resolver function that strips 'Schema' from the end of the class name."""
#     schema_cls = resolve_schema_cls(schema)
#     name = schema_cls.__name__
#     if name.endswith("Schema"):
#         return name[:-6] or name
#     return name


# class PydanticPlugin(BasePlugin):

#     Converter = OpenAPIConverter
#     Resolver = SchemaResolver
    
#     def __init__(self) -> None:
#         super().__init__()
#         self.schema_name_resolver = resolver
#         self.spec: APISpec | None = None
#         self.openapi_version: OpenAPIVersion | None = None
#         self.converter: OpenAPIConverter | None = None
#         self.resolver: SchemaResolver | None = None

#     def init_spec(self, spec: APISpec) -> None:
#         super().init_spec(spec)
#         self.spec = spec
#         self.openapi_version = spec.openapi_version
#         self.converter = self.Converter(
#             openapi_version=spec.openapi_version,
#             schema_name_resolver=self.schema_name_resolver,
#             spec=spec,
#         )
#         self.resolver = self.Resolver(
#             openapi_version=spec.openapi_version, converter=self.converter
#         )

#     def schema_helper(
#         self,
#         name: str,
#         definition: dict,
#         model: Optional[BaseModel] = None,
#         **kwargs: Any
#     ):
#         if model is None:
#             return None

#         schema = model.schema(ref_template="#/components/schemas/{model}")

#         # if "definitions" in schema:
#         #     for (k, v) in schema["definitions"].items():
#         #         self.spec.components.schema(k, v)
#         #     del schema["definitions"]

#         return schema

#     def response_helper(self, response: dict, **kwargs: Any):
#         self.resolve_schema(response)
#         if "headers" in response:
#             for header in response["headers"].values():
#                 self.resolve_schema(header)
#         return response

#     def resolve_schema(self, data):
#         if not isinstance(data, dict):
#             return

#         if "schema" in data:
#             data["schema"] = self.resolve_schema_dict(data["schema"])

#     def resolve_schema_dict(self, schema):
#         if isinstance(schema, dict):
#             if schema.get("type") == "array" and "items" in schema:
#                 schema["items"] = self.resolve_schema_dict(schema["items"])
#             if schema.get("type") == "object" and "properties" in schema:
#                 schema["properties"] = {
#                     k: self.resolve_schema_dict(v)
#                     for k, v in schema["properties"].items()
#                 }
#             for keyword in ("oneOf", "anyOf", "allOf"):
#                 if keyword in schema:
#                     schema[keyword] = [
#                         self.resolve_schema_dict(s) for s in schema[keyword]
#                     ]
#             if "not" in schema:
#                 schema["not"] = self.resolve_schema_dict(schema["not"])
#             return schema

#         return self.get_model_schema(schema)

#     def get_model_schema(self, model):
#         return model.schema(ref_template="#/components/schemas/{model}")

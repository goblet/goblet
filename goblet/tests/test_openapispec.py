from typing import List, Optional
from marshmallow import Schema, fields

from goblet.config import GConfig
from goblet.handlers.routes import OpenApiSpec, RouteEntry
from pydantic import BaseModel


def dummy():
    pass


class DummySchema(Schema):
    id = fields.Int()
    flt = fields.Float()


class DummySchemaRequired(Schema):
    id = fields.Int()
    flt = fields.Float(required=True)


class NestedModel(BaseModel):
    text: str


class PydanticModelSimple(BaseModel):
    id: Optional[int] = None
    flt: float
    idlist: Optional[List[int]] = None


class PydanticModelSimpleOptional(BaseModel):
    id: Optional[int] = None
    flt: Optional[float] = None


class PydanticModel(BaseModel):
    id: int
    nested: NestedModel


class PydanticModelDuplicate(BaseModel):
    id: int
    nested: NestedModel


class PydanticModelReturnComplex(BaseModel):
    id: int
    nested: NestedModel
    option: Optional[int]
    objects: List[str]


def dummy_pydantic_return() -> PydanticModelReturnComplex:
    pass


class TestOpenApiSpec:
    def test_add_route(self):
        route = RouteEntry(dummy, "route", "/home", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        expected_json = {
            "/home": {
                "get": {
                    "x-google-backend": {
                        "address": "xyz.cloudfunction",
                        "protocol": "h2",
                        "deadline": 15,
                        "path_translation": "APPEND_PATH_TO_ADDRESS",
                    },
                    "operationId": "get_route",
                    "responses": {"200": {"description": "A successful response"}},
                }
            }
        }
        spec_dict = spec.component_spec.to_dict()
        assert spec_dict["paths"] == expected_json

    def test_custom_deadlines(self):
        route = RouteEntry(
            dummy,
            "route",
            "/home",
            "GET",
        )
        route2 = RouteEntry(dummy, "deadline", "/deadline", "GET", deadline=30)
        spec = OpenApiSpec("test", "xyz.cloudfunction", deadline=10)
        spec.add_route(route)
        spec.add_route(route2)
        spec_dict = spec.component_spec.to_dict()

        assert spec_dict["paths"]["/home"]["get"]["x-google-backend"]["deadline"] == 10
        assert (
            spec_dict["paths"]["/deadline"]["get"]["x-google-backend"]["deadline"] == 30
        )

    def test_add_route_post(self):
        route = RouteEntry(dummy, "route", "/home", "GET")
        route_post = RouteEntry(dummy, "route", "/home", "POST")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec.add_route(route_post)
        spec_dict = spec.component_spec.to_dict()

        assert spec_dict["paths"]["/home"].get("post")
        assert spec_dict["paths"]["/home"].get("get")

    def test_security_definitions(self):
        security_def = GConfig(
            config={
                "your_custom_auth_id": {
                    "authorizationUrl": "",
                    "flow": "implicit",
                    "type": "oauth2",
                    "x-google-issuer": "issuer of the token",
                    "x-google-jwks_uri": "url to the public key",
                }
            }
        )
        spec = OpenApiSpec(
            "test", "xyz.cloudfunction", security_definitions=security_def
        )
        spec_dict = spec.component_spec.to_dict()

        assert spec_dict["securityDefinitions"] == security_def
        assert spec_dict["security"] == [{"your_custom_auth_id": []}]

    def test_security_config(self):
        security_def = GConfig(
            config={
                "your_custom_auth_id": {
                    "authorizationUrl": "",
                    "flow": "implicit",
                    "type": "oauth2",
                    "x-google-issuer": "issuer of the token",
                    "x-google-jwks_uri": "url to the public key",
                }
            }
        )
        spec = OpenApiSpec(
            "test",
            "xyz.cloudfunction",
            security_definitions=security_def,
            security=[{"custom": []}],
        )
        spec_dict = spec.component_spec.to_dict()

        assert spec_dict["securityDefinitions"] == security_def
        assert spec_dict["security"] == [{"custom": []}]

    def test_write_config(self):
        import io

        security_def = GConfig(
            config={
                "your_custom_auth_id": {
                    "authorizationUrl": "",
                    "flow": "implicit",
                    "type": "oauth2",
                    "x-google-issuer": "issuer of the token",
                    "x-google-jwks_uri": "url to the public key",
                }
            }
        )

        expected_yaml = """swagger: '2.0'
securityDefinitions:
  your_custom_auth_id:
    authorizationUrl: ''
    flow: implicit
    type: oauth2
    x-google-issuer: issuer of the token
    x-google-jwks_uri: url to the public key
security:
- custom: []
schemes:
- https
produces:
- application/json
paths: {}
info:
  title: test
  version: 1.0.0
"""

        spec = OpenApiSpec(
            "test",
            "xyz.cloudfunction",
            security_definitions=security_def,
            security=[{"custom": []}],
        )
        output = io.StringIO()
        spec.write(output)
        output.seek(0)
        writen_yaml = "".join(output.readlines())
        assert writen_yaml == expected_yaml

    def test_security_method(self):
        route = RouteEntry(
            dummy, "route", "/home", "POST", security=[{"your_custom_auth_id": []}]
        )
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        assert spec_dict["paths"]["/home"]["post"]["security"] == [
            {"your_custom_auth_id": []}
        ]

    def test_add_primitive_types(self):
        def prim_typed(param: str, param2: bool) -> int:
            return 200

        route = RouteEntry(prim_typed, "route", "/home/{param}/{param2}", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        params = spec_dict["paths"]["/home/{param}/{param2}"]["get"]["parameters"]
        assert len(params) == 2
        assert params[0] == {
            "in": "path",
            "name": "param",
            "required": True,
            "type": "string",
        }
        assert params[1] == {
            "in": "path",
            "name": "param2",
            "required": True,
            "type": "boolean",
        }
        response_content = spec_dict["paths"]["/home/{param}/{param2}"]["get"][
            "responses"
        ]["200"]["schema"]
        assert response_content == {"type": "integer"}

    def test_return_schema_regular(self):
        def schema_typed() -> DummySchema:
            return DummySchema()

        route = RouteEntry(schema_typed, "route", "/home", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        response_content = spec_dict["paths"]["/home"]["get"]["responses"]["200"][
            "schema"
        ]
        assert response_content == {"$ref": "#/definitions/DummySchema"}
        assert len(spec_dict["definitions"]["DummySchema"]["properties"]) == 2

    def test_return_lists(self):
        def schema_typed_list() -> List[DummySchema]:
            return []

        route = RouteEntry(schema_typed_list, "route", "/home", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        response_content = spec_dict["paths"]["/home"]["get"]["responses"]["200"][
            "schema"
        ]
        assert response_content == {
            "type": "array",
            "items": {"$ref": "#/definitions/DummySchema"},
        }
        assert len(spec_dict["definitions"]["DummySchema"]["properties"]) == 2

        def prim_typed_list() -> List[str]:
            return []

        route = RouteEntry(prim_typed_list, "route", "/home", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()
        response_content = spec_dict["paths"]["/home"]["get"]["responses"]["200"][
            "schema"
        ]
        assert response_content == {"type": "array", "items": {"type": "string"}}
        assert not spec_dict.get("definitions")

    def test_custom_response(self):
        route = RouteEntry(
            dummy, "route", "/home", "GET", responses={"400": {"description": "400"}}
        )
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        response = spec_dict["paths"]["/home"]["get"]["responses"]
        assert response["400"] == {"description": "400"}

    def test_form_data(self):
        route = RouteEntry(dummy, "route", "/home", "GET", form_data=True)
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        params = spec_dict["paths"]["/home"]["get"]["parameters"][0]
        assert params == {"in": "formData", "name": "file", "type": "string"}
        assert spec_dict["paths"]["/home"]["get"]["consumes"] == ["multipart/form-data"]

    def test_query_params(self):
        route = RouteEntry(
            dummy,
            "route",
            "/home",
            "GET",
            query_params=[
                {"name": "test", "type": "string", "required": True},
                {"name": "test2", "type": "string", "required": True},
            ],
        )
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()
        params = spec_dict["paths"]["/home"]["get"]["parameters"][0]
        params2 = spec_dict["paths"]["/home"]["get"]["parameters"][1]

        assert params == {
            "in": "query",
            "name": "test",
            "type": "string",
            "required": True,
        }
        assert params2 == {
            "in": "query",
            "name": "test2",
            "type": "string",
            "required": True,
        }

    def test_query_params_class(self):
        route = RouteEntry(
            dummy,
            "route",
            "/home",
            "GET",
            query_params=[
                {"in": "query", "schema": "DummySchemaRequired"},
                {
                    "in": "query",
                    "name": "test2",
                    "type": "string",
                    "required": True,
                },
            ],
        )
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        assert {
            "in": "query",
            "name": "flt",
            "type": "number",
            "required": True,
        } in spec_dict["paths"]["/home"]["get"]["parameters"]
        assert {
            "in": "query",
            "name": "id",
            "type": "integer",
            "required": False,
        } in spec_dict["paths"]["/home"]["get"]["parameters"]
        assert {
            "in": "query",
            "name": "test2",
            "type": "string",
            "required": True,
        } in spec_dict["paths"]["/home"]["get"]["parameters"]

    def test_custom_backend(self):
        route = RouteEntry(
            dummy, "route", "/home", "GET", form_data=True, backend="CLOUDRUN/URL"
        )
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        entry = spec_dict["paths"]["/home"]["get"]
        assert entry["x-google-backend"]["address"] == "CLOUDRUN/URL"

    def test_marshmallow_attribute_function(self):
        def schema_typed() -> DummySchema:
            return DummySchema()

        def dummyschema_to_properties(self, field, **kwargs):
            if isinstance(field, fields.Float):
                return {"type": "custom"}
            if isinstance(field, fields.Int):
                return {"type": "custom"}
            return {}

        route = RouteEntry(schema_typed, "route", "/home", "GET")
        spec = OpenApiSpec(
            "test",
            "xyz.cloudfunction",
            marshmallow_attribute_function=dummyschema_to_properties,
        )
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        response_content = spec_dict["paths"]["/home"]["get"]["responses"]["200"][
            "schema"
        ]
        assert response_content == {"$ref": "#/definitions/DummySchema"}
        assert (
            spec_dict["definitions"]["DummySchema"]["properties"]["flt"]["type"]
            == "custom"
        )
        assert (
            spec_dict["definitions"]["DummySchema"]["properties"]["id"]["type"]
            == "custom"
        )

    # <------------------------------- Pydantic plugin tests ------------------------------->

    def test_reponse_pyndantic(self):
        def schema_typed() -> PydanticModel:
            return PydanticModel()

        route = RouteEntry(schema_typed, "route", "/home", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        response_content = spec_dict["paths"]["/home"]["get"]["responses"]["200"][
            "schema"
        ]
        assert response_content == {"$ref": "#/definitions/PydanticModel"}

    def test_request_body_pyndantic(self):
        def schema_typed() -> PydanticModel:
            return PydanticModel()

        route = RouteEntry(
            schema_typed, "route", "/home", "GET", request_body=PydanticModel
        )
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        request_content = spec_dict["paths"]["/home"]["get"]["parameters"][0]
        pydantic_definitions = spec_dict["definitions"]
        assert request_content == {
            "in": "body",
            "name": "requestBody",
            "schema": {"$ref": "#/definitions/PydanticModel"},
        }
        assert "PydanticModel" in pydantic_definitions.keys()
        assert "NestedModel" in pydantic_definitions.keys()
        assert (
            "id" in pydantic_definitions["PydanticModel"]["properties"]
            and "nested" in pydantic_definitions["PydanticModel"]["properties"]
        )

    def test_request_body_list_pyndantic(self):
        def schema_typed() -> PydanticModel:
            return PydanticModel()

        route = RouteEntry(
            schema_typed, "route", "/home", "GET", request_body=List[PydanticModel]
        )
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        request_content = spec_dict["paths"]["/home"]["get"]["parameters"][0]
        assert request_content == {
            "in": "body",
            "name": "requestBody",
            "schema": {
                "type": "array",
                "items": {"$ref": "#/definitions/PydanticModel"},
            },
        }

    def test_duplicate_nested_pydantic(self):
        def schema_typed() -> PydanticModel:
            return PydanticModel()

        route = RouteEntry(
            schema_typed, "route", "/home", "GET", request_body=List[PydanticModel]
        )

        route2 = RouteEntry(
            schema_typed,
            "route",
            "/home2",
            "GET",
            request_body=List[PydanticModelDuplicate],
        )

        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec.add_route(route2)
        spec_dict = spec.component_spec.to_dict()

        request_content = spec_dict["paths"]["/home"]["get"]["parameters"][0]
        assert request_content == {
            "in": "body",
            "name": "requestBody",
            "schema": {
                "type": "array",
                "items": {"$ref": "#/definitions/PydanticModel"},
            },
        }

    def test_query_params_class_pydantic(self):
        route = RouteEntry(
            dummy,
            "route",
            "/home",
            "GET",
            query_params=[
                {"in": "query", "schema": PydanticModelSimple},
                {
                    "in": "query",
                    "name": "test2",
                    "type": "string",
                    "required": True,
                },
            ],
        )
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        assert {
            "in": "query",
            "name": "flt",
            "type": "number",
            "required": True,
        } in spec_dict["paths"]["/home"]["get"]["parameters"]
        assert {
            "in": "query",
            "name": "id",
            "type": "integer",
            "required": False,
        } in spec_dict["paths"]["/home"]["get"]["parameters"]
        assert {
            "in": "query",
            "name": "idlist",
            "type": "array",
            "items": {"type": "integer"},
            "required": False,
        } in spec_dict["paths"]["/home"]["get"]["parameters"]
        assert {
            "in": "query",
            "name": "test2",
            "type": "string",
            "required": True,
        } in spec_dict["paths"]["/home"]["get"]["parameters"]

    def test_query_params_class_pydantic_optional(self):
        route = RouteEntry(
            dummy,
            "route",
            "/home",
            "GET",
            query_params=[
                {"in": "query", "schema": PydanticModelSimpleOptional},
                {
                    "in": "query",
                    "name": "test2",
                    "type": "string",
                    "required": True,
                },
            ],
        )
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        assert {
            "in": "query",
            "name": "flt",
            "type": "number",
            "required": False,
        } in spec_dict["paths"]["/home"]["get"]["parameters"]
        assert {
            "in": "query",
            "name": "id",
            "type": "integer",
            "required": False,
        } in spec_dict["paths"]["/home"]["get"]["parameters"]
        assert {
            "in": "query",
            "name": "test2",
            "type": "string",
            "required": True,
        } in spec_dict["paths"]["/home"]["get"]["parameters"]

    def test_query_params_class_pydantic_return(self):
        route = RouteEntry(
            dummy_pydantic_return,
            "route",
            "/home/{id}",
            "GET",
            query_params=[{"in": "query", "schema": PydanticModelSimpleOptional}],
        )
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec_dict = spec.component_spec.to_dict()

        return_obj_props = spec_dict["definitions"]["PydanticModelReturnComplex"][
            "properties"
        ]
        assert return_obj_props["option"]["type"] == "integer"
        assert return_obj_props["objects"]["items"]["type"] == "string"

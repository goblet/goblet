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
            for (k, v) in schema["definitions"].items():
                if k not in self.spec.components.schemas:
                    self.spec.components.schema(k, v)
            del schema["definitions"]

        return schema

#!/usr/bin/env python3
import os.path

import requests
import json

CLOUDRUN_V2 = "https://run.googleapis.com/$discovery/rest?version=v2"
CLOUDFUNCTIONS_V1 = "https://cloudfunctions.googleapis.com/$discovery/rest?version=v1"
CLOUDFUNCTIONS_V2 = "https://cloudfunctions.googleapis.com/$discovery/rest?version=v2"
CLOUDBUILD_V1 = "https://cloudbuild.googleapis.com/$discovery/rest?version=v1"
APIGATEWAY_V1 = "https://apigateway.googleapis.com/$discovery/rest?version=v1"
VPCACCESS_V1 = "https://vpcaccess.googleapis.com/$discovery/rest?version=v1"
REDIS_V1 = "https://redis.googleapis.com/$discovery/rest?version=v1"
CLOUDTASKS_V2 = "https://cloudtasks.googleapis.com/$discovery/rest?version=v2"

DRAFT_7_STRICT = True

GOOGLE_APIS = [
    CLOUDFUNCTIONS_V1,
    CLOUDFUNCTIONS_V2,
    CLOUDRUN_V2,
    CLOUDBUILD_V1,
    APIGATEWAY_V1,
    REDIS_V1,
    VPCACCESS_V1,
    CLOUDTASKS_V2,
]


def get_template():
    with open(
            f"{'/'.join(os.path.realpath(__file__).split('/')[:-1])}/template.json", "r"
    ) as f:
        template = "".join(f.readlines())

    template = template.replace('"%(definitions)s"', "%(definitions)s")
    template = template.replace(
        '"__gobletProperties__": "__gobletProperties__"', get_goblet_properties()
    )
    return template


def get_goblet_properties():
    properties = []
    with open(
            f"{'/'.join(os.path.realpath(__file__).split('/')[:-1])}/properties.json", "r"
    ) as f:
        for property_name, property_object in json.loads("".join(f.readlines()))[
            "properties"
        ].items():
            properties.append(f'"{property_name}": {json.dumps(property_object)}')
    return ",".join(properties)


def fetch_schemas(url):
    r = requests.get(url=url)
    service_id = r.json()["id"]
    return service_id, r.json()["schemas"]


def scrub(obj, bad_key="_this_is_bad"):
    if isinstance(obj, dict):
        # the call to `list` is useless for py2 but makes
        # the code py2/py3 compatible
        for key in list(obj.keys()):
            if key == bad_key:
                del obj[key]
            else:
                scrub(obj[key], bad_key)
    elif isinstance(obj, list):
        for i in reversed(range(len(obj))):
            if obj[i] == bad_key:
                del obj[i]
            else:
                scrub(obj[i], bad_key)

    else:
        # neither a dict nor a list, do nothing
        pass


def getSecurityDefinitions():
    return {
        "type": "object",
        "oneOf": [
            {
                "$ref": "https://json.schemastore.org/swagger-2.0.json#/definitions/basicAuthenticationSecurity"
            },
            {
                "$ref": "https://json.schemastore.org/swagger-2.0.json#/definitions/apiKeySecurity"
            },
            {
                "$ref": "https://json.schemastore.org/swagger-2.0.json#/definitions/oauth2ImplicitSecurity"
            },
            {
                "$ref": "https://json.schemastore.org/swagger-2.0.json#/definitions/oauth2PasswordSecurity"
            },
            {
                "$ref": "https://json.schemastore.org/swagger-2.0.json#/definitions/oauth2ApplicationSecurity"
            },
            {
                "$ref": "https://json.schemastore.org/swagger-2.0.json#/definitions/oauth2AccessCodeSecurity"
            }
        ]
    }


def gcp_definitions():
    definitions = {}
    for url in GOOGLE_APIS:
        service_id, service_schemas = fetch_schemas(url=url)
        for name, definition in service_schemas.items():
            definition["$id"] = f"#/definitions/{service_id}:{definition['id']}"
            del definition["id"]
            if DRAFT_7_STRICT:
                scrub(definition, "enumDescriptions")
                scrub(definition, "enumDeprecated")

            json_definition = (
                json.dumps(definition)
                .replace('"$ref": "', f'"$ref": "#/definitions/{service_id}:')
                .replace('"type": "any"', '"type": "object"')
            )
            if DRAFT_7_STRICT:
                json_definition = json_definition.replace(
                    "google-datetime", "date-time"
                ).replace("google-duration", "duration")

            definitions[f"{service_id}:{name}"] = json.loads(
                json_definition
            )

    definitions["securityDefinitions"] = getSecurityDefinitions()
    return definitions


def write_json_schema():
    definitions = gcp_definitions()
    with open(
            f"{'/'.join(os.path.realpath(__file__).split('/')[:-1])}/../../goblet.schema.json",
            "w",
    ) as f:
        f.write(
            json.dumps(
                json.loads(get_template() % {"definitions": json.dumps(definitions)}),
                indent=2,
            )
        )


if __name__ == "__main__":
    write_json_schema()

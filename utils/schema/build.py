import json
import os

import requests

raw_url = 'https://raw.githubusercontent.com/mauriciowittenberg/goblet/feature/json-schema/utils/schema/references'
references = set()


def get_references(d):
    for k, v in d.items():
        if isinstance(v, dict):
            get_references(v)
        else:
            if k == '$ref' and v.startswith('https://'):
                references.add(v.split('#')[0])


with open('base.json', 'r') as f:
    schema_base = ''.join(f.readlines())
    get_references(json.loads(schema_base))

for reference in references:
    reference_json = json.loads(requests.get(url=reference).text.replace('"$ref": "', '"$ref": "#/schemas/'))
    reference_filename = f"{reference_json['id'].replace(':', '.')}.json"
    reference_raw_url = f"{raw_url}/{reference_filename}"
    with open(f"references/{reference_filename}", 'w') as f:
        f.write(json.dumps(reference_json, indent=2, sort_keys=True))

    schema_base = schema_base.replace(reference, reference_raw_url)

with open(f"{'/'.join(os.path.realpath(__file__).split('/')[:-1])}/../../goblet.schema.json", "w") as f:
    f.write(json.dumps(json.loads(schema_base), indent=2, sort_keys=True))


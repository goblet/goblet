from goblet.app import Goblet
import pytest
from jsonschema import ValidationError

valid_schema = {
    "type" : "object",
    "properties" : {
        "name" : {"type" : "string"},
        "Id" : {"type" : "number"},
    },
    "additionalProperties": False,
    "required": ["name", "Id"]
}

failed_schema = {
    "type" : "object",
    "properties" : {
        "not_real" : {"type" : "string"},
    },
    "required": ["not_real"],
    "additionalProperties": False
}

test_event = {'@type': 'type.googleapis.com/google.pubsub.v1.PubsubMessage', 'attributes': {"event_type":"test"},  'data': 'eyJuYW1lIjoiYXVzIiwiSWQiOjEwfQ=='}

def dummy_entry_point(event,context={}):
    return True

class TestGoblet:

    def test_valid_schema(self):
        assert Goblet().entry_point(event_schema=valid_schema)(dummy_entry_point)(test_event,{}) == None

    def test_invalid_schema(self):
        with pytest.raises(ValidationError):
            Goblet().entry_point(event_schema=failed_schema, log_error=False)(dummy_entry_point)(test_event,{})

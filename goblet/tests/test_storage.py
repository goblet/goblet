from goblet import Goblet
from goblet.deploy import Deployer
from goblet.resources.storage import Storage
from goblet.test_utils import get_responses, dummy_function, mock_dummy_function

from unittest.mock import Mock
import pytest


class TestPubSub:

    def test_add_bucket(self, monkeypatch):
        app = Goblet(function_name="goblet_example")

        app.storage('test', 'finalize')(dummy_function)
        app.storage('test2', 'archive')(dummy_function)

        storage = app.handlers["storage"]
        assert(len(storage.buckets) == 2)
        assert(storage.buckets[0]['event_type'] == 'finalize')
        assert(storage.buckets[1]['event_type'] == 'archive')

    def test_add_invalid_event(self):
        app = Goblet(function_name="goblet_example")

        with pytest.raises(Exception):
            app.storage('test', 'wrong')(dummy_function)

    def test_call_storage(self, monkeypatch):
        app = Goblet(function_name="goblet_example")
        mock = Mock()

        app.storage('test', 'finalize')(mock_dummy_function(mock))

        mock_context = Mock()
        mock_context.event_type = 'providers/cloud.storage/eventTypes/bucket.finalize'
        event = {'bucket': 'test'}

        app(event, mock_context)
        assert(mock.call_count == 1)

    def test_deploy_storage(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "storage-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_storage")
        setattr(app, "entrypoint", 'app')

        app.storage('test', 'finalize')(dummy_function)

        Deployer().deploy(app, force=True)

        responses = get_responses('storage-deploy')

        assert(len(responses) == 3)
        assert(responses[2]['body']['metadata']['target'].endswith('goblet_storage-storage-test-finalize'))
        assert(responses[2]['body']['metadata']['request']['eventTrigger']['resource'] == 'projects/goblet/buckets/test')
        assert(responses[2]['body']['metadata']['request']['eventTrigger']['eventType'] == 'google.storage.object.finalize')

    def test_destroy_pubsub(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "storage-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        storage = Storage('goblet_storage', buckets=[{'bucket': 'test', 'event_type': 'finalize'}])
        storage.destroy()

        responses = get_responses('storage-destroy')

        assert(len(responses) == 1)
        assert(responses[0]['body']['metadata']['type'] == 'DELETE_FUNCTION')
        assert(responses[0]['body']['metadata']['target'].endswith('goblet_storage-storage-test-finalize'))

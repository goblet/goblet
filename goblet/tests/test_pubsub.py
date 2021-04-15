from goblet import Goblet
from goblet.deploy import Deployer
from goblet.resources.pubsub import PubSub
from goblet.test_utils import get_responses

from unittest.mock import Mock
import base64
import pytest


class TestPubSub:

    def test_add_topic(self, monkeypatch):
        app = Goblet(function_name="goblet_example", region='us-central-1')
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        @app.topic('test')
        def dummy_function(self):
            return True
        pubsub = app.handlers["pubsub"]
        assert(len(pubsub.topics) == 1)
        assert(pubsub.topics['test']['dummy_function'] == {'func': dummy_function, 'attributes': {}})

    def test_add_topic_attributes(self, monkeypatch):
        app = Goblet(function_name="goblet_example", region='us-central-1')
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        @app.topic('test', attributes={'test': True})
        def dummy_function(self):
            return True
        pubsub = app.handlers["pubsub"]
        assert(len(pubsub.topics) == 1)
        assert(pubsub.topics['test']['dummy_function'] == {'func': dummy_function, 'attributes': {'test': True}})

    def test_call_topic(self, monkeypatch):
        app = Goblet(function_name="goblet_example", region='us-central-1')
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        @app.topic('test')
        def dummy_function(data):
            assert data == 'test'

        mock_context = Mock()
        mock_context.resource = 'projects/GOOGLE_PROJECT/topics/test'
        mock_context.event_type = 'providers/cloud.pubsub/eventTypes/topic.publish'

        event = {'data': base64.b64encode('test'.encode())}

        # assert dummy_function is run
        app(event, mock_context)

    def test_call_topic_attributes(self, monkeypatch):
        app = Goblet(function_name="goblet_example", region='us-central-1')
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        @app.topic('test', attributes={'t': 1})
        def dummy_function(data):
            assert data == 'test'

        @app.topic('test', attributes={'t': 3})
        def dummy_function2(data):
            raise Exception()

        mock_context = Mock()
        mock_context.resource = 'projects/GOOGLE_PROJECT/topics/test'
        mock_context.event_type = 'providers/cloud.pubsub/eventTypes/topic.publish'

        event = {'data': base64.b64encode('test'.encode()), 'attributes': {'t': 1}}
        event2 = {'data': base64.b64encode('test2'.encode()), 'attributes': {'t': 2}}
        event3 = {'data': base64.b64encode('test3'.encode()), 'attributes': {'t': 3}}

        # assert dummy_function is run
        app(event, mock_context)
        app(event2, mock_context)
        # assert dummy function2 is run
        with pytest.raises(Exception):
            app(event3, mock_context)

    def test_deploy_pubsub(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "pubsub-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")
        
        app = Goblet(function_name="goblet_topic")
        setattr(app, "entrypoint", 'app')

        @app.topic('test-topic')
        def dummy_function(data):
            assert data == 'test'

        Deployer().deploy(app)

        responses = get_responses('pubsub-deploy')

        assert(len(responses) == 4)
        assert(responses[3]['body']['metadata']['target'].endswith('goblet_topic-topic-test-topic'))
        assert(responses[3]['body']['metadata']['request']['eventTrigger']['resource'] == 'projects/goblet/topics/test-topic')
        assert(responses[3]['body']['metadata']['request']['eventTrigger']['eventType'] == 'providers/cloud.pubsub/eventTypes/topic.publish')

    def test_destroy_pubsub(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "pubsub-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")
        
        pubsub = PubSub('goblet_topic', topics={'test-topic':{}})
        pubsub.destroy()

        responses = get_responses('pubsub-destroy')

        assert(len(responses) == 1)
        assert(responses[0]['body']['metadata']['type'] == 'DELETE_FUNCTION')
        assert(responses[0]['body']['metadata']['target'].endswith('goblet_topic-topic-test-topic'))

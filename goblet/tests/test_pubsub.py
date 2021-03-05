from goblet import Goblet
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

        @app.topic('test', attributes={'t':1})
        def dummy_function(data):
            assert data == 'test' 

        @app.topic('test', attributes={'t':3})
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



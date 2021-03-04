from goblet import Goblet


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
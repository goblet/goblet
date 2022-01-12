from goblet.config import GConfig

test_config = {
    "cloudfunction": {"environmentVariables": {"key": "value"}},
    "stages": {
        "dev": {
            "function_name": "dev",
            "cloudfunction": {"environmentVariables": {"key": "dev"}},
        }
    },
}


class TestGConfig:
    def test_get_item(self):
        config = GConfig(test_config)
        assert config.cloudfunction == {"environmentVariables": {"key": "value"}}
        assert not config.not_exists

    def test_set_item(self):
        config = GConfig(test_config)
        config.new = 1
        assert config.new == 1

    def test_stages(self):
        config = GConfig(test_config, stage="dev")
        assert config.cloudfunction["environmentVariables"]["key"] == "dev"

    def test_env_variable(self, monkeypatch):
        monkeypatch.setenv("TEST", "test")
        assert GConfig().TEST == "test"

    def test_stages_env(self, monkeypatch):
        monkeypatch.setenv("STAGE", "dev")
        config = GConfig(test_config)
        assert config.cloudfunction["environmentVariables"]["key"] == "dev"

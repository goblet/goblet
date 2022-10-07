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
        config.update_g_config()
        assert config.cloudfunction["environmentVariables"]["key"] == "dev"

    def test_env_variable(self, monkeypatch):
        monkeypatch.setenv("TEST", "test")
        assert GConfig().TEST == "test"

    def test_stages_env(self, monkeypatch):
        monkeypatch.setenv("STAGE", "dev")
        config = GConfig(test_config)
        config.update_g_config()
        assert config.cloudfunction["environmentVariables"]["key"] == "dev"

    def test_update_config(self):
        config = GConfig(test_config)
        config.update_g_config(
            values={"cloudfunction": {"environmentVariables": {"key2": "value2"}}}
        )
        assert config.cloudfunction["environmentVariables"]["key"] == "value"
        assert config.cloudfunction["environmentVariables"]["key2"] == "value2"

    def test_update_config_list(self):
        config = GConfig({"cloudrun_container": {"env": [{"key1": "value1"}]}})
        config.update_g_config(
            values={"cloudrun_container": {"env": [{"key2": "value2"}]}}
        )
        assert len(config.cloudrun_container["env"]) == 2
        assert config.cloudrun_container["env"][0]["key1"] == "value1"
        assert config.cloudrun_container["env"][1]["key2"] == "value2"

    def test_update_config_stage(self):
        config = GConfig(test_config)
        config.update_g_config(stage="dev")
        assert config.cloudfunction["environmentVariables"]["key"] == "dev"

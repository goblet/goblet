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
        # config.update_g_config()
        assert config.cloudfunction["environmentVariables"]["key"] == "dev"

    def test_env_variable(self, monkeypatch):
        monkeypatch.setenv("TEST", "test")
        assert GConfig().TEST == "test"

    def test_env_variable_empty_dict(self):
        assert GConfig({"TEST": {}}).TEST == {}

    def test_stages_env(self, monkeypatch):
        monkeypatch.setenv("STAGE", "dev")
        config = GConfig(test_config)
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

    def test_config_assignment(self):
        config = GConfig(test_config)
        config.cloudfunction = "new_value"
        assert config.cloudfunction == "new_value"
        assert config["cloudfunction"] == "new_value"

        config = GConfig(test_config)
        config["cloudfunction"] = "new_value"
        assert config.cloudfunction == "new_value"
        assert config["cloudfunction"] == "new_value"

        config = GConfig(test_config)
        config.cloudfunction = {"new_key": "value"}
        config.cloudfunction.new_key = "new_value"
        assert config["cloudfunction"]["new_key"] == "new_value"

    def test_unpacking(self):
        config = GConfig(test_config)
        new_dict = {**config}

        assert new_dict.get("cloudfunction", False).get(
            "environmentVariables", False
        ) == {"key": "value"}
        assert new_dict["cloudfunction"]["environmentVariables"] == {"key": "value"}

        new_dict = {**config["cloudfunction"]}
        assert new_dict.get("environmentVariables", False) == {"key": "value"}
        assert new_dict["environmentVariables"] == {"key": "value"}

        new_dict = {**config.cloudfunction}
        assert new_dict.get("environmentVariables", False) == {"key": "value"}
        assert new_dict["environmentVariables"] == {"key": "value"}

    def test_compare(self):
        config1 = GConfig(test_config)
        config2 = GConfig(test_config)

        assert id(config1) != id(config2)
        assert config1 == config2
        assert config1.stage == config2.stage

    def test_json_dumps(self):
        import json

        config = GConfig(test_config)
        assert json.dumps(config, sort_keys=True) == json.dumps(
            test_config, sort_keys=True
        )
        assert json.dumps(config.cloudfunction, sort_keys=True) == json.dumps(
            test_config["cloudfunction"], sort_keys=True
        )

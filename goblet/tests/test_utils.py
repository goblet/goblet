import json
import os
import unittest
import goblet.utils as utils


class TestUtils(unittest.TestCase):
    def test_nested_update(self):
        d = {"k1": "v1", "k2": {"k3": "v2", "k5": "v4"}}
        u = {"k2": {"k4": "v3", "k5": "v5"}, "k6": "v6"}
        result = utils.nested_update(d, u)
        self.assertEqual(
            result, {"k1": "v1", "k2": {"k3": "v2", "k4": "v3", "k5": "v5"}, "k6": "v6"}
        )
        d = {"k1": "v1", "k2": {"k3": "v2", "k5": "v4"}}
        u = {}
        result = utils.nested_update(d, u)
        self.assertEqual(result, {"k1": "v1", "k2": {"k3": "v2", "k5": "v4"}})
        d = {}
        u = {"k1": "v1", "k2": {"k3": "v2", "k5": "v4"}}
        result = utils.nested_update(d, u)
        self.assertEqual(result, {"k1": "v1", "k2": {"k3": "v2", "k5": "v4"}})

    def test_attributes_to_filter(self):
        attributes = {"attr1": "val1", "attr2": "val2"}
        filter_string = utils.attributes_to_filter(attributes)
        assert filter_string == 'attributes.attr1 = "val1" OR attributes.attr2 = "val2"'

    def test_build_stage_config(self):
        import tempfile

        source_config_file = tempfile.NamedTemporaryFile(mode="w")
        source_config = '{"k1": "v1", "k2": {"k3": "v3"}, "k5": "v5","stages": {"s1": {"k1": "v2", "k2": {"k3": "v6", "k4": "v4"}}}}'
        with open(source_config_file.name, "w") as f:
            f.write(source_config)

        config_file = utils.build_stage_config(
            config_path=source_config_file.name, stage="s1"
        )
        config_file_name = config_file.name
        with open(config_file_name, "r") as f:
            config = json.loads("".join(f.readlines()))

        config_file.close()

        assert config["k1"] == "v2"
        assert config["k2"]["k3"] == "v6"
        assert config["k2"]["k4"] == "v4"
        assert config["k5"] == "v5"
        assert config.get("stages", None) is None
        assert os.path.exists(config_file_name) is False

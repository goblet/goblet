import unittest
import goblet.utils as utils

class TestUtils(unittest.TestCase):
    def test_nested_update(self):
        d = {"k1": "v1", "k2": {"k3": "v2", "k5": "v4"}}
        u = {"k2": {"k4": "v3", "k5": "v5"}, "k6": "v6"}
        result = utils.nested_update(d, u)
        self.assertEqual(result, {"k1": "v1", "k2": {"k3": "v2", "k4": "v3", "k5": "v5"}, "k6": "v6"})
        d = {"k1": "v1", "k2": {"k3": "v2", "k5": "v4"}}
        u = {}
        result = utils.nested_update(d, u)
        self.assertEqual(result, {"k1": "v1", "k2": {"k3": "v2", "k5": "v4"}})
        d = {}
        u = {"k1": "v1", "k2": {"k3": "v2", "k5": "v4"}}
        result = utils.nested_update(d, u)
        self.assertEqual(result, {"k1": "v1", "k2": {"k3": "v2", "k5": "v4"}})
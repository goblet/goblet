from goblet.deploy import RevisionSpec
import unittest

class testRevision(unittest.TestCase):
    def test_modifyTraffic(self):
        testSpec = RevisionSpec(config={"cloudrun": {"traffic": 25}})
        serviceConfig = {
            "latestReadyRevision": "latestTest",
            "trafficStatuses": [
                {
                    "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                    "revision": "test",
                    "percent": 20
                },
                {
                    "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                    "revision": "anotherTest",
                    "percent": 55
                },
                {
                    "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST",
                    "percent": 25
                }
            ] 
        }
        testSpec.modifyTraffic(serviceConfig=serviceConfig)
        result = testSpec.req_body["traffic"]

        self.assertEqual(result, [
        {'type': 'TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION', 'revision': 'test', 'percent': 15}, 
        {'type': 'TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION', 'revision': 'anotherTest', 'percent': 42}, 
        {'type': 'TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION', 'revision': 'latestTest', 'percent': 19}, 
        {'type': 'TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST', 'percent': 24}])





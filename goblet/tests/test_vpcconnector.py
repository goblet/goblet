from goblet import Goblet
from goblet.test_utils import get_response, get_responses, dummy_function
from goblet.infrastructures.vpcconnector import VPCConnector
from goblet.resources.http import HTTP


class TestVPCConnector:
    def test_add_vpcconnector(self):
        app = Goblet(function_name="goblet_example")

        app.vpcconnector(name="vpc-test")
        vpc = app.infrastructure["vpcconnector"]
        assert vpc.resources["name"] == "vpc-test"

    def test_deploy_vpcconnector(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "vpcconnector-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet-example")
        app.vpcconnector(name="vpc-test", ipCidrRange="10.32.1.0/28")

        # app.deploy(
        #     force=True,
        #     skip_backend=True,
        #     skip_resources=True,
        #     config={"vpcconnector": {"ipCidrRange": "10.32.1.0/28"}},
        # )

        post_vpc = get_response(
            "vpcconnector-deploy",
            "post-v1-projects-goblet-locations-us-central1-connectors_1.json",
        )
        assert "vpc-test" in post_vpc["body"]["metadata"]["target"]

    def test_destroy_vpcconnector(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "vpcconnector-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        # vpc = VPCConnector("goblet-vpc", resources={"name": "vpc-test"})
        # vpc.destroy()

        responses = get_responses("vpcconnector-destroy")
        assert len(responses) == 2
        assert "vpc-test" in responses[0]["body"]["metadata"]["target"]
        assert "vpc-test" in responses[1]["body"]["metadata"]["target"]
        assert responses[1]["body"]["done"] == True

    # def test_deploy_vpcconnector_cloudrun(self, monkeypatch):
    #     monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
    #     monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
    #     monkeypatch.setenv("GOBLET_TEST_NAME", "vpcconnector-deploy-cloudrun")
    #     monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

    #     # requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

    #     app = Goblet(function_name="goblet-example-vpc", backend="cloudrun")
    #     setattr(app, "entrypoint", "app")

    #     app.handlers["http"] = HTTP(dummy_function)

    #     app.vpcconnector(name="vpc-test", ipCidrRange="10.32.1.0/28")
    #     app.deploy(skip_resources=True, force=True, config={})

    # def test_deploy_vpcconnector_cloudfunction(self, monkeypatch):
    #     monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
    #     monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
    #     monkeypatch.setenv("GOBLET_TEST_NAME", "vpcconnector-deploy-cloudfunction")
    #     monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

    #     app = Goblet(function_name="goblet-example-vpc", backend="cloudfunction")
    #     setattr(app, "entrypoint", "app")

    #     app.handlers["http"] = HTTP(dummy_function)

    #     app.vpcconnector(name="vpc-test", ipCidrRange="10.32.1.0/28")
    #     app.deploy(
    #         skip_infra=True,
    #         skip_resources=True,
    #         force=True,
    #         config={"cloudfunction": {"availableMemoryMb": 45}},
    #     )

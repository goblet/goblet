import pytest
from goblet import Goblet
from goblet.test_utils import dummy_function
from pytest import raises
from goblet_gcp_client import get_response, get_responses

from goblet.infrastructures.vpcconnector import VPCConnector


class TestVPCConnector:
    def test_add_vpcconnector(self):
        app = Goblet(
            function_name="goblet_example",
            config={"vpcconnector": {"ipCidrRange": "10.32.1.0/28"}},
        )

        app.vpcconnector(name="vpc-test")
        vpc = app.infrastructure["vpcconnector"]
        assert vpc.resources["name"] == "vpc-test"

    def test_add_invalid_vpcconnector(self):
        app = Goblet(function_name="goblet_example")
        with raises(ValueError):
            app.vpcconnector(name="vpc-test")

    def test_deploy_vpcconnector(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "vpcconnector-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet-example",
            config={"vpcconnector": {"ipCidrRange": "10.32.1.0/28"}},
        )
        app.vpcconnector(name="vpc-test")

        app.deploy(
            force=True,
            skip_backend=True,
            skip_handlers=True,
        )

        vpc_conn = get_response(
            "vpcconnector-deploy",
            "get-v1-projects-goblet-locations-us-central1-connectors-vpc-test_1.json",
        )
        assert "vpc-test" in vpc_conn["body"]["name"]
        assert "default" == vpc_conn["body"]["network"]
        assert "10.32.1.0/28" == vpc_conn["body"]["ipCidrRange"]

    def test_destroy_vpcconnector(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "vpcconnector-destroy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        vpc = VPCConnector("goblet-vpc", resources={"name": "vpc-test"})
        vpc.destroy()

        responses = get_responses("vpcconnector-destroy")
        assert len(responses) == 2
        assert "vpc-test" in responses[0]["body"]["metadata"]["target"]
        assert "vpc-test" in responses[1]["body"]["metadata"]["target"]
        assert responses[1]["body"]["done"]

    def test_deploy_cloudrun(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "vpcconnector-deploy-cloudrun")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet-example-vpc",
            backend="cloudrun",
            config={"vpcconnector": {"ipCidrRange": "10.32.1.0/28"}},
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"].register("", dummy_function, {})

        app.vpcconnector(name="vpc-test")
        app.deploy(
            skip_infra=True,
            skip_handlers=True,
            force=True,
        )

        app.destroy(skip_infra=True)
        response = get_response(
            "vpcconnector-deploy-cloudrun",
            "post-v2-projects-goblet-locations-us-central1-services_1.json",
        )
        cloudrun_metadata = response["body"]["metadata"]
        assert (
            "PRIVATE_RANGES_ONLY"
            == cloudrun_metadata["template"]["vpcAccess"]["egress"]
        )
        assert "vpc-test" in cloudrun_metadata["template"]["vpcAccess"]["connector"]

    def test_deploy_cloudfunction(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "vpcconnector-deploy-function")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet-example-vpc",
            backend="cloudfunction",
            config={"vpcconnector": {"ipCidrRange": "10.32.1.0/28"}},
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"].register("", dummy_function, {})

        app.vpcconnector(name="vpc-test")
        app.deploy(
            skip_handlers=True,
            skip_infra=True,
            force=True,
        )

        app.destroy(skip_infra=True)
        response = get_response(
            "vpcconnector-deploy-function",
            "post-v1-projects-goblet-locations-us-central1-functions_1.json",
        )

        function_metadata = response["body"]["metadata"]["request"]
        assert "PRIVATE_RANGES_ONLY" == function_metadata["vpcConnectorEgressSettings"]
        assert "vpc-test" in function_metadata["vpcConnector"]

    def test_deploy_cloudfunctionv2(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "vpcconnector-deploy-functionv2")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet-example-vpc",
            backend="cloudfunctionv2",
            config={"vpcconnector": {"ipCidrRange": "10.32.1.0/28"}},
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"].register("", dummy_function, {})

        app.vpcconnector(name="vpc-test")
        app.deploy(
            skip_handlers=True,
            skip_infra=True,
            force=True,
        )

        app.destroy(skip_infra=True)
        response = get_response(
            "vpcconnector-deploy-functionv2",
            "get-v2-projects-goblet-locations-us-central1-operations-operation-1664907376650-5ea3974c4e78a-ad732159-2582b07a_1.json",
        )

        function_v2_metadata = response["body"]["metadata"]["requestResource"]
        assert "GEN_2" == function_v2_metadata["environment"]
        assert (
            "PRIVATE_RANGES_ONLY"
            == function_v2_metadata["serviceConfig"]["vpcConnectorEgressSettings"]
        )
        assert "vpc-test" in function_v2_metadata["serviceConfig"]["vpcConnector"]

    def test_deploy_vpcconnector_solo(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "vpcconnector-deploy-solo")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet-example",
            config={"vpcconnector": {"ipCidrRange": "10.32.1.0/28"}},
            backend="cloudrun",
        )
        app.vpcconnector(name="vpc-test")
        app.job(name="job-test")(dummy_function)

        app.deploy(
            force=True, infras=["vpcconnector"], skip_backend=True, skip_handlers=True
        )

        responses = get_responses("vpcconnector-deploy-solo")
        assert len(responses) == 3
        assert "vpc-test" in responses[0]["body"]["name"]

        with pytest.raises(FileNotFoundError) as _:
            get_response(
                "vpcconnector-deploy-solo",
                "post-v2-projects-goblet-locations-us-central1-jobs_1.json",
            )

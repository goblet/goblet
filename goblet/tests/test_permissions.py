from goblet.permissions import (
    gcp_generic_resource_permissions,
    create_custom_role_policy,
)
from goblet import Goblet
from goblet.test_utils import dummy_function
from goblet.handlers.pubsub import PubSub
from goblet.handlers.routes import Routes

from goblet.backends.cloudfunctionv1 import CloudFunctionV1

from goblet_gcp_client import (
    get_response,
    get_replay_count,
    reset_replay_count,
)


class TestPermissions:
    def test_gcp_generic_resource_permissions(self):
        permissions = gcp_generic_resource_permissions("cloudfunctions", "functions")
        assert "cloudfunctions.functions.create" in permissions
        assert len(permissions) == 5

    def test_get_permissions(self):
        app = Goblet(function_name="goblet_example")
        app.topic("test")(dummy_function)
        permissions = app.get_permissions()

        assert all(p in permissions for p in PubSub.permissions)
        assert all(p in permissions for p in CloudFunctionV1.permissions)
        assert not all(p in permissions for p in Routes.permissions)

    def test_create_service_account(self, monkeypatch):
        """Deploy a custom role and service account"""
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "permissions-create-service-account")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        reset_replay_count()

        app = Goblet(function_name="goblet-create-service-account")
        app.topic("test")(dummy_function)
        permissions = app.get_permissions()
        role_policy = create_custom_role_policy(app.function_name, permissions)
        app.create_service_account(role_policy)

        assert get_replay_count() == 4

        service_account_email = (
            "goblet-create-service-account@goblet.iam.gserviceaccount.com"
        )
        role_name = "Goblet_Deployment_Role_goblet_create_service_account"

        create_sa_resp = get_response(
            "permissions-create-service-account",
            "post-v1-projects-goblet-serviceAccounts_1.json",
        )

        create_role = get_response(
            "permissions-create-service-account",
            "post-v1-projects-goblet-roles_1.json",
        )

        set_iam_resp = get_response(
            "permissions-create-service-account",
            "post-v3-projects-goblet-setIamPolicy_1.json",
        )

        assert create_sa_resp["body"]["email"] == service_account_email
        assert role_name in create_role["body"]["name"]

        assert (
            service_account_email in set_iam_resp["body"]["bindings"][0]["members"][0]
        )
        assert role_name in set_iam_resp["body"]["bindings"][0]["role"]

    def test_set_invoker_permissions_cloudrun(self, monkeypatch):
        """Deploy a custom role and service account"""
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "permissions-set_invoker-cloudrun")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet-set-invoker-permissions",
            backend="cloudrun",
            config={
                "pubsub": {
                    "serviceAccountEmail": "sa_pubsub@goblet.iam.gserviceaccount.com"
                },
                "scheduler": {
                    "serviceAccount": "sa_scheduler@goblet.iam.gserviceaccount.com"
                },
            },
        )
        app.topic("test")(dummy_function)
        app.schedule("* * * * *")(dummy_function)

        app.deploy(force=True, skip_backend=True)

        set_iam_resp_1 = get_response(
            "permissions-set_invoker-cloudrun",
            "post-v2-projects-goblet-locations-us-central1-services-goblet-set-invoker-permissions-setIamPolicy_1.json",
        )
        set_iam_resp_2 = get_response(
            "permissions-set_invoker-cloudrun",
            "post-v2-projects-goblet-locations-us-central1-services-goblet-set-invoker-permissions-setIamPolicy_2.json",
        )
        assert (
            "sa_pubsub@goblet.iam.gserviceaccount.com"
            in set_iam_resp_1["body"]["bindings"][0]["members"][0]
        )
        assert "run.invoker" in set_iam_resp_1["body"]["bindings"][0]["role"]
        assert len(set_iam_resp_2["body"]["bindings"][0]["members"]) == 2

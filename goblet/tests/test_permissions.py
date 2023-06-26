from goblet.permissions import gcp_generic_resource_permissions, create_custom_role
from goblet import Goblet
from goblet.test_utils import dummy_function
from goblet.handlers.pubsub import PubSub
from goblet.handlers.routes import Routes

from goblet.backends.cloudfunctionv1 import CloudFunctionV1

from goblet_gcp_client import (
    get_responses,
    get_response,
    get_replay_count,
    reset_replay_count,
)


class TestPermissions:
    def test_gcp_generic_resource_permissions(self):
        permissions = gcp_generic_resource_permissions("cloudfunctions", "functions")
        assert "cloudfunctions.function.create" in permissions
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

        app = Goblet(function_name="goblet_test_service_account")
        app.topic("test")(dummy_function)
        permissions = app.get_permissions()
        role = create_custom_role(app.function_name, permissions)
        app.create_service_account(role)

    def test_add_binding(self, monkeypatch):
        """Deploy a custom role and service account"""
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "permissions-add-binding")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_test_service_account")
        app.topic("test")(dummy_function)
        permissions = app.get_permissions()
        role = create_custom_role(app.function_name, permissions)
        app.create_service_account(role)
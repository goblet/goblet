import os
from goblet.client import VersionedClients
import goblet.globals as g
from goblet.common_cloud_actions import check_or_enable_service


class Infrastructure:
    """Base Infrastructure Class"""

    resource_type = ""
    can_sync = False
    supports_local = False
    required_apis = []
    permissions = []

    def __init__(
        self,
        name,
        backend=None,
        resources=None,
    ):
        self.name = name
        self.backend = backend
        self.resources = resources or {}
        self.config = g.config
        self.versioned_clients = VersionedClients()

    def register(self, name, kwargs):
        raise NotImplementedError("register")

    def deploy(self):
        if (
            not self.supports_local and os.getenv("X_GOBLET_LOCAL", False)
        ) and not os.getenv("G_HTTP_TEST") == "REPLAY":
            pass
        else:
            self._deploy()

    def _deploy(self):
        raise NotImplementedError("deploy")

    def destroy(self):
        raise NotImplementedError("destroy")

    def sync(self, dryrun=False):
        if self.can_sync:
            self._sync(dryrun)

    def _sync(self, dryrun=False):
        pass

    def get_config(self):
        return None

    def _check_or_enable_service(self, enable=False):
        if not self.resources:
            return
        return check_or_enable_service(self.required_apis, enable)

    def get_permissions(self):
        if len(self.resources) > 0:
            return self.permissions
        return []

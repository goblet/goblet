import logging
import os

from goblet.client import VersionedClients
from goblet_gcp_client.client import get_default_project, get_default_location
from goblet.common_cloud_actions import check_or_enable_service
import goblet.globals as g

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class Handler:
    """Base Handler class"""

    valid_backends = []
    resources = None
    resource_type = ""
    can_sync = False
    supports_local = False
    required_apis = []
    permissions = []
    service_accounts = []

    def __init__(
        self,
        name,
        backend,
        versioned_clients: VersionedClients = None,
        resources=None,
    ):
        self.config = g.config
        self.name = name
        self.backend = backend
        self.resources = resources or {}
        self.versioned_clients = versioned_clients or VersionedClients()
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{name}"

    def register(self, name, func, kwargs):
        raise NotImplementedError("register")

    def deploy(self, source=None, entrypoint=None):
        if self.resources and self.backend.resource_type not in self.valid_backends:
            log.info(
                f"skipping... {self.backend.resource_type} not supported for {self.resource_type}"
            )
            return
        if not self.resources:
            return
        if (
            not self.supports_local and os.getenv("X_GOBLET_LOCAL", False)
        ) and not os.getenv("G_HTTP_TEST") == "REPLAY":
            return
        self._deploy(source, entrypoint)
        try:
            self.set_invoker_permissions()
        except Exception:
            log.warning(f"Error setting invoker permissions for {self.resource_type}")

    def _deploy(self, source=None, entrypoint=None):
        raise NotImplementedError("deploy")

    def destroy(self):
        raise NotImplementedError("destroy")

    def sync(self, dryrun=False):
        if self.can_sync:
            log.info(f"syncing {self.resource_type}")
            self._sync(dryrun)

    def _sync(self, dryrun=False):
        pass

    def __call__(self, request, context=None):
        raise NotImplementedError("__call__")

    def __add__(self, other):
        if other.resources:
            self.resources.update(other.resources)
        return self

    def _check_or_enable_service(self, enable=False):
        if not self.resources:
            return
        return check_or_enable_service(self.required_apis, enable)

    def get_permissions(self):
        if len(self.resources) > 0:
            return self.permissions
        return []

    def set_invoker_permissions(self):
        if self.service_accounts:
            self.backend.add_invoker_binding(self.service_accounts)

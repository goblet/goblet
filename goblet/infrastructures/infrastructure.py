from goblet.client import VersionedClients
import goblet.globals as g
from goblet.common_cloud_actions import check_or_enable_service


class Infrastructure:
    """Base Infrastructure Class"""

    resource_type = ""
    can_sync = False
    required_apis = []

    def __init__(
        self,
        name,
        backend=None,
        resource=None,
    ):
        self.name = name
        self.backend = backend
        self.resource = resource or {}
        self.config = g.config
        self.versioned_clients = VersionedClients()

    def register(self, name, kwargs):
        raise NotImplementedError("register")

    def deploy(self):
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
        if not self.resource:
            return
        return check_or_enable_service(self.required_apis, enable)

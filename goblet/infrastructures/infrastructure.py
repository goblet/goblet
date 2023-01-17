from goblet.client import VersionedClients
from goblet.config import GConfig


class Infrastructure:
    """Base Infrastructure Class"""

    resource_type = ""
    can_sync = False

    def __init__(
        self,
        name,
        backend=None,
        versioned_clients: VersionedClients = None,
        resource=None,
        config={},
    ):
        self.name = name
        self.backend = backend
        self.client = versioned_clients or VersionedClients()
        self.resource = resource or {}
        self.config = GConfig(config=config)

    def register(self, name, kwargs):
        raise NotImplementedError("register")

    def deploy(self, config={}):
        raise NotImplementedError("deploy")

    def destroy(self, config={}):
        raise NotImplementedError("destroy")

    def sync(self, dryrun=False):
        if self.can_sync:
            self._sync(dryrun)

    def _sync(self, dryrun=False):
        pass

    def get_config(self, config={}):
        raise NotImplementedError("get_config")

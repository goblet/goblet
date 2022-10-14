from goblet.client import VersionedClients
from goblet.config import GConfig


class Infrastructure:
    """Base Infrastructure Class"""

    resource_type = ""

    def __init__(
        self,
        name,
        backend="cloudfunction",
        versioned_clients: VersionedClients = None,
        resource=None,
        config={},
    ):
        self.name = name
        self.backend = backend
        self.client = versioned_clients or VersionedClients()
        self.resource = resource or {}
        self.config = GConfig(config=config)

    def deploy(self, config={}):
        raise NotImplementedError("deploy")

    def destroy(self, config={}):
        raise NotImplementedError("destroy")

    def get_config(self, config={}):
        raise NotImplementedError("get_config")

from goblet.client import VersionedClients


class Infrastructure:
    """Base Infrastructure Class"""

    resource_type = ""

    def __init__(
        self,
        name,
        backend="cloudfunction",
        versioned_clients: VersionedClients = None,
        resources=None,
    ):
        self.name = name
        self.backend = backend
        self.client = versioned_clients or VersionedClients()
        self.resources = resources or {}

    def deploy(self, config={}):
        raise NotImplementedError("deploy")

    def destroy(self, config={}):
        raise NotImplementedError("destroy")

    def get_config(self, config={}):
        raise NotImplementedError("get_config")

import logging

from goblet.client import VersionedClients, get_default_location, get_default_project

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class Handler:
    """Base Handler class"""

    valid_backends = []
    resources = None
    resource_type = ""
    backend = "cloudfunction"
    can_sync = False

    def __init__(
        self,
        name,
        versioned_clients: VersionedClients = None,
        resources=None,
        backend="cloudfunction",
    ):
        self.name = name
        self.backend = backend
        self.resources = resources or {}
        self.versioned_clients = versioned_clients or VersionedClients()
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{name}"

    def deploy(self, sourceUrl=None, entrypoint=None, config={}):
        if self.resources and self.backend not in self.valid_backends:
            log.info(
                f"skipping... {self.backend} not supported for {self.resource_type}"
            )
            return
        self._deploy(sourceUrl, entrypoint, config=config)

    def _deploy(self, sourceUrl=None, entrypoint=None, config={}):
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

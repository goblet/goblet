import logging

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class Handler:
    """Base Handler class"""

    valid_backends = []
    resources = None
    resource_type = ""
    backend = "cloudfunction"

    def deploy(self, sourceUrl=None, entrypoint=None):
        if self.resources and self.backend not in self.valid_backends:
            log.info(
                f"skipping... {self.backend} not supported for {self.resource_type}"
            )
            return
        self._deploy(sourceUrl, entrypoint)

    def _deploy(self, sourceUrl=None, entrypoint=None):
        raise NotImplementedError("deploy")

    def destroy(self):
        raise NotImplementedError("destroy")

    def __call__(self, request, context=None):
        raise NotImplementedError("__call__")

    def __add__(self, other):
        if other.resources:
            self.resources.update(other.resources)
        return self

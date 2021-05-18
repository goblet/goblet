class Handler:
    """Base Handler class"""

    def deploy(self, sourceUrl=None, entrypoint=None):
        raise NotImplementedError("deploy")

    def destroy(self):
        raise NotImplementedError("destroy")

    def __call__(self, request, context=None):
        raise NotImplementedError("__call__")

    def __add__(self):
        raise NotImplementedError("__add__")

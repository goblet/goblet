class Handler:

    def deploy(self):
        raise NotImplementedError("deploy")

    def destroy(self):
        raise NotImplementedError("destroy")

    def __call__(self, request, context=None):
        raise NotImplementedError("__call__")

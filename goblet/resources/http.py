from goblet.handler import Handler


class HTTP(Handler):
    def __init__(self, http=None):
        self.http = http

    def register_http(self, func):
        self.http = func

    def __call__(self, request, context=None):
        return self.http(request)

    def __add__(self, other):
        if other.http:
            self.http = other.http
        return self

    def deploy(self, sourceUrl=None, entrypoint=None):
        return

    def destroy(self):
        return

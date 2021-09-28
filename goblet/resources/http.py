from goblet.handler import Handler


class HTTP(Handler):
    """Http Trigger"""
    def __init__(self, http=None):
        self.http = http or []

    def register_http(self, func, kwargs):
        self.http.append({"func": func, "headers": kwargs.get("headers", {})})

    def __call__(self, request, context=None):
        headers = request.headers or {}
        for http_endpoint in self.http:
            endpoint_headers = http_endpoint["headers"]
            if isinstance(endpoint_headers, dict) and endpoint_headers.items() <= dict(headers.items()).items():
                return http_endpoint["func"](request)
            if isinstance(endpoint_headers, set) and endpoint_headers <= set(headers.keys()):
                return http_endpoint["func"](request)

    def __add__(self, other):
        if other.http:
            self.http.extend(other.http)
        return self

    def deploy(self, sourceUrl=None, entrypoint=None):
        return

    def destroy(self):
        return

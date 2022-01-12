from goblet.handler import Handler


class HTTP(Handler):
    """Http Trigger"""

    resource_type = "http"
    valid_backends = ["cloudfunction", "cloudrun"]

    def __init__(self, resources=None, backend="cloudfunction"):
        self.resources = resources or []
        self.backend = backend

    def register_http(self, func, kwargs):
        self.resources.append({"func": func, "headers": kwargs.get("headers", {})})

    def __call__(self, request, context=None):
        headers = request.headers or {}
        for http_endpoint in self.resources:
            endpoint_headers = http_endpoint["headers"]
            if (
                isinstance(endpoint_headers, dict)
                and endpoint_headers.items() <= dict(headers.items()).items()
            ):
                return http_endpoint["func"](request)
            if isinstance(endpoint_headers, set) and endpoint_headers <= set(
                headers.keys()
            ):
                return http_endpoint["func"](request)

    def _deploy(self, sourceUrl=None, entrypoint=None):
        return

    def destroy(self):
        return

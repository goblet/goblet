import json


class Response(object):
    """
    Generic Response class based on Flask Response
    """

    def __init__(self, body, headers=None, status_code=200):
        self.body = body
        if headers is None:
            headers = {"Content-type": "text/plain"}
        self.headers = headers
        self.status_code = status_code

    def __call__(self, environ, start_response):
        body = self.body
        if not isinstance(body, (str, bytes)):
            body = json.dumps(body, separators=(",", ":"))
        status = self.status_code
        headers = [(k, v) for k, v in self.headers.items()]
        start_response(status, headers)
        return [body]

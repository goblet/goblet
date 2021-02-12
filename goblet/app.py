import logging
import json
import sys

from goblet.decorators import Register_Handlers

logging.basicConfig()


class Goblet(Register_Handlers):
    def __init__(self, function_name="goblet", region="us-east4", local=None):
        super(Goblet, self).__init__(function_name=function_name)
        self.function_name = function_name
        self.region = region
        self.log = logging.getLogger(__name__)
        self.headers = {}
        self.g = G()
        if local and sys.modules.get('main'):
            def local_func(request):
                return self(request)
            setattr(sys.modules['main'], local, local_func)

    # Will deprecate
    def jsonify(self, *args, **kwargs):
        indent = None
        separators = (',', ':')
        headers = {'Content-Type': 'application/json'}
        headers.update(self.headers)

        if args and kwargs:
            raise TypeError('jsonify() behavior undefined when passed both args and kwargs')
        elif len(args) == 1:  # single args are passed directly to dumps()
            data = args[0]
        else:
            data = args or kwargs

        json_string = json.dumps(data, indent=indent, separators=separators)
        return (json_string, 200, headers)


class Response(object):
    def __init__(self, body, headers=None, status_code=200):
        self.body = body
        if headers is None:
            headers = {'Content-type': 'text/plain'}
        self.headers = headers
        self.status_code = status_code

    def __call__(self, environ, start_response):
        body = self.body
        if not isinstance(body, (str, bytes)):
            body = json.dumps(body, separators=(',', ':'))
        status = self.status_code
        headers = [(k, v) for k, v in self.headers.items()]
        start_response(status, headers)
        return [body]


def jsonify(*args, **kwargs):
    indent = None
    separators = (',', ':')
    headers = {'Content-Type': 'application/json'}
    headers.update(kwargs.get('headers', {}))

    if args and kwargs:
        raise TypeError('jsonify() behavior undefined when passed both args and kwargs')
    elif len(args) == 1:  # single args are passed directly to dumps()
        data = args[0]
    else:
        data = args or kwargs

    if not isinstance(data, (str, bytes)):
        data = json.dumps(data, indent=indent, separators=separators)
    return (data, 200, headers)


class G:
    pass

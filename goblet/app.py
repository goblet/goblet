from goblet.config import GConfig
import logging
import json
import sys

from goblet.decorators import Register_Handlers

logging.basicConfig()


class Goblet(Register_Handlers):
    """
    Main class which inherits most of its logic from the Register_Handlers class. Local param is used
    to set the entrypoint for running goblet locally
    """
    def __init__(self, function_name="goblet", local="local", cors=None):
        self.function_name = GConfig().function_name or function_name
        super(Goblet, self).__init__(function_name=self.function_name, cors=cors)
        self.log = logging.getLogger(__name__)
        self.headers = {}
        self.g = G()
        if local and sys.modules.get('main'):
            self.log = logging.getLogger('werkzeug')

            def local_func(request):
                return self(request)
            setattr(sys.modules['main'], local, local_func)


class Response(object):
    """
    Generic Response class based on Flask Response
    """
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
    """
    Helper based on flask jsonify and helsp convert lists and dicts into valid reponses.
    """
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
    """
    Global class that allows users to set and pass variables between middlewares.
    """
    pass


def goblet_entrypoint(app, entrypoint="goblet_entrypoint"):
    """
    Wrapper around Goblet app to make it a function, since a recent GCP bug forces the entrypoint to be of type function
    whereas before any type of callable was allowed.
    """
    if sys.modules.get('main'):
        def goblet_entrypoint_wrapper(request, context=None):
            return app(request, context)
        setattr(sys.modules['main'], entrypoint, goblet_entrypoint_wrapper)

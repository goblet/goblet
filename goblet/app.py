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


class G:
    pass

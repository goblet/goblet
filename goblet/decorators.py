from goblet.routes import RouteEntry, ApiGateway
import logging

log = logging.getLogger(__name__)

EVENT_TYPES = ["all", 'http']

class DecoratorAPI:
    def middleware(self, event_type='all'):
        if event_type not in EVENT_TYPES:
            raise ValueError(f"{event_type} not in {EVENT_TYPES}")
        def _middleware_wrapper(func):
            self.register_middleware(func, event_type)
            return func
        return _middleware_wrapper
 
    # def schedule(self, expression, description=''):
    #     return self._create_registration_function(
    #         handler_type='schedule',
    #         registration_kwargs={'expression': expression,
    #                              'description': description},
    #     )

    def route(self, path, methods=['GET'], **kwargs):
        return self._create_registration_function(
            handler_type='route',
            registration_kwargs={'path': path,'methods':methods, 'kwargs': kwargs},
        )

    def _create_registration_function(self, handler_type,
                                      registration_kwargs=None):
        def _register_handler(user_handler):
            handler_name = user_handler.__name__
            kwargs = registration_kwargs or {}
            self._register_handler(handler_type, handler_name,
                                   user_handler, kwargs)
            return user_handler
        return _register_handler


    def _register_handler(self, handler_type, name,
                          func, kwargs, options=None):
        raise NotImplementedError("_register_handler")

    def register_middleware(self, func, event_type='all'):
        raise NotImplementedError("register_middleware")


class Register_Handlers(DecoratorAPI):

    def __init__(self,function_name):
        self.handlers = {
            "route":ApiGateway(function_name)
        }
        self.middleware_handlers = {}
        self.current_request = None

    def __call__(self, request, context=None):
        self.current_request = request
        # TODO: get event_type
        event_type = 'http'
        request = self._call_middleware(request,event_type)
        return self.handlers["route"](request)

    def _call_middleware(self, event, event_type):
        middleware = self.middleware_handlers.get('all', [])
        middleware.extend(self.middleware_handlers.get(event_type, []))
        for m in middleware:
            event = m(event)

        return event

    def _register_handler(self, handler_type, name,
                          func, kwargs, options=None):

        getattr(self, '_register_%s' % handler_type)(
            name=name,
            func=func,
            kwargs=kwargs,
        )

    def deploy(self):
        for k,v in self.handlers.items():
            log.info(f"deploying {k}")
            v.deploy()

    def destroy(self):
        for k,v in self.handlers.items():
            log.info(f"deploying {k}")
            v.destroy()

    def register_middleware(self, func, event_type='all'):
        middleware_list = self.middleware_handlers.get(event_type,[])
        middleware_list.append(func)
        self.middleware_handlers[event_type] = middleware_list

    def _register_route(self, name, func, kwargs):
        self.handlers["route"].register_route(name=name, func=func, kwargs=kwargs)

class LegacyDecoratorAPI:

    def _set_coorelation_id(self, event):
        if event.get('attributes'):
            self.correlation_id = event.get('attributes').get("correlation_id", str(uuid.uuid4()))
        else:
            self.correlation_id = str(uuid.uuid4())
                    
    def entry_point(self, log_error=True, event_type=None, event_schema=None):
        def cloudfunction_wrapper(func):
            def cloudfunction_event(event, context):
                self.event = event
                self._set_coorelation_id
                if event_type and (not event.get('attributes') or event_type != event['attributes'].get("event_type")):
                    return self.log.info(f"event type of {event.get('event_type')} does not match expected event type of {event_type}")
                self.data = json.loads(base64.b64decode(event['data']).decode('utf-8')) # assumes json event
                self.context = context
                if event_schema:
                    try:
                        validate(instance=self.data, schema=event_schema)
                    except ValidationError as e:
                        if log_error:
                            return self.log.exception(e.message)
                        else:
                            raise e
                try:   
                    func(event,context)
                except Exception as e:
                    if log_error:
                        self.log.exception(e)

            return cloudfunction_event

        return cloudfunction_wrapper

    def http_entry_point(self,log_error=True,event_schema=None, cors=False):
        def cloudfunction_wrapper(func):
            def cloudfunction_request(request):
                if cors:
                    cors_headers = cors if isinstance(cors,dict) else {} 
                    # Set CORS headers for the preflight request
                    if request.method == 'OPTIONS':
                        # Allows GET requests from any origin with the Content-Type
                        # header and caches preflight response for an 3600s
                        headers = {
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'GET',
                            'Access-Control-Allow-Headers': 'Content-Type',
                            'Access-Control-Max-Age': '3600'
                        }
                        headers.update(cors_headers)
                        return ('', 204, headers)
                    # Set CORS headers for the main request
                    self.headers = {
                        'Access-Control-Allow-Origin': '*'
                    }
                    self.headers.update(cors_headers)
                
                if request.content_type == "application/x-www-form-urlencoded":
                    self.data = request.form
                else:
                    # TODO: add support for different content types
                    self.data = request.get_json() 

                if self.data.get('attributes'):
                    self.correlation_id = self.data['attributes'].get("correlation_id", str(uuid.uuid4()))
                else:
                    self.correlation_id = str(uuid.uuid4())
                    
                if event_schema:
                    try:
                        validate(instance=self.data, schema=event_schema)
                    except ValidationError as e:
                        if log_error:
                            return self.log.exception(e.message)
                        else:
                            raise e
                try:   
                    return func(request)
                except Exception as e:
                    if log_error:
                        self.log.exception(e)
                    return (json.dumps(e),400,self.headers)

            return cloudfunction_request

        return cloudfunction_wrapper

    def configure_pubsub_topic(self,name, schema=None):
        self.pubsub_topic_name=name, 
        self.pubsub_topic_schema = schema,

    def publish(self, data, extra_attributes={}):
        if not pubsub_topic_name:
            raise ValueError("Missing Pubsub topic name")

        if self.pubsub_topic_schema:
            try:
                validate(instance=data, schema=self.pubsub_topic_schema)
            except ValidationError as e:
                if log_error:
                    return self.log.exception(e.message)
                else:
                    raise e

        publisher = pubsub_v1.PublisherClient()

        future = publisher.publish(
            self.pubsub_topic_name,
            data=json.dumps(data).encode("utf-8")
            **{
                "correlation_id":self.correlation_id,
                **extra_attributes
            }
            )

        future.result(3)
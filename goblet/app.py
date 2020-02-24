import logging
import os 
import sys
import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler, setup_logging
from google.cloud.logging.resource import Resource
import uuid
from jsonschema import validate, ValidationError
from google.cloud import pubsub_v1
import base64
import json

class Goblet():
    FORMAT_STRING = '%(name)s - %(levelname)s - %(message)s'

    def __init__(self, function_name="goblet", region="us-east4", debug=False, stackdriver=False, env=None):
        super(Goblet, self).__init__()
        self.function_name = function_name
        self.region = region
        self._debug = debug
        self.log = logging.getLogger()
        self.data = None
        self.event = None
        self.context = None
        self.correlation_id = None
        if stackdriver:
            self._initialize_stackdriver_logging()
            self.log = logging.getLogger(name=self.function_name)
            self._configure_log_level()
        else:
            self._configure_logging()

    def _initialize_stackdriver_logging(self):
        stackdriver_client = google.cloud.logging.Client()
        stackdriver_handler = CloudLoggingHandler(stackdriver_client,name=self.function_name, resource=self.log_resource, labels={})
        setup_logging(stackdriver_handler)

    @property
    def log_resource(self):
        return Resource(type="cloud_function", 
                labels={
                    "function_name": self.function_name, 
                    "region": self.region,
                    "correlation_id": self.correlation_id or "missing"
                },
    )

    def _configure_logging(self):
        if self._already_configured(self.log):
            return
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(self.FORMAT_STRING)
        handler.setFormatter(formatter)
        self.log.propagate = False
        self._configure_log_level()
        self.log.addHandler(handler)

    def _already_configured(self, log):
        if not log.handlers:
            return False
        for handler in log.handlers:
            if isinstance(handler, logging.StreamHandler):
                if handler.stream == sys.stdout:
                    return True
        return False

    @property
    def debug(self):
        return self._debug

    @debug.setter
    def debug(self, value):
        self._debug = value
        self._configure_log_level()

    def _configure_log_level(self):
        if self._debug:
            level = logging.DEBUG
        else:
            level = logging.ERROR
        self.log.setLevel(level)


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

    def http_entry_point(self,log_error=True,event_schema=None):
        def cloudfunction_wrapper(func):
            def cloudfunction_request(request):
                self.data = request.get_json 
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
                    func(request)
                except Exception as e:
                    if log_error:
                        self.log.exception(e)

            return cloudfunction_event

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
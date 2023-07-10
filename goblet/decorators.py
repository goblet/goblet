from __future__ import annotations
import os
import yaml
from warnings import warn
import logging

from goblet_gcp_client.client import get_default_location, get_default_project

from goblet.backends.cloudfunctionv1 import CloudFunctionV1
from goblet.backends.cloudfunctionv2 import CloudFunctionV2
from goblet.backends.cloudrun import CloudRun

from goblet.infrastructures.redis import Redis
from goblet.infrastructures.vpcconnector import VPCConnector
from goblet.infrastructures.cloudtask import CloudTaskQueue
from goblet.infrastructures.pubsub import PubSubTopic
from goblet.infrastructures.alerts import PubSubDLQCondition

log = logging.getLogger(__name__)
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))

EVENT_TYPES = [
    "all",
    "http",
    "schedule",
    "pubsub",
    "storage",
    "route",
    "eventarc",
    "job",
    "bqremotefunction",
    "cloudtasktarget",
]

SUPPORTED_BACKENDS = {
    "cloudfunction": CloudFunctionV1,
    "cloudfunctionv2": CloudFunctionV2,
    "cloudrun": CloudRun,
}

SUPPORTED_INFRASTRUCTURES = {
    "redis": Redis,
    "vpcconnector": VPCConnector,
    "cloudtaskqueue": CloudTaskQueue,
    "pubsub_topic": PubSubTopic,
}


class Goblet_Decorators:
    """Decorator endpoints that are called by the user. Returns _create_registration_function which will trigger the corresponding
    registration function in the Register_Handlers class. For example _create_registration_function with type route will call
    _register_route"""

    def before_request(self, event_type="all"):
        """Function called before request for preeprocessing"""

        if event_type not in EVENT_TYPES:
            raise ValueError(f"{event_type} not in {EVENT_TYPES}")

        def _middleware_wrapper(func):
            self.register_middleware(func, event_type, before_or_after="before")
            return func

        return _middleware_wrapper

    def after_request(self, event_type="all"):
        """Function called after request for postprocessing"""

        if event_type not in EVENT_TYPES:
            raise ValueError(f"{event_type} not in {EVENT_TYPES}")

        def _middleware_wrapper(func):
            self.register_middleware(func, event_type, before_or_after="after")
            return func

        return _middleware_wrapper

    def middleware(self, event_type="all"):
        """Middleware functions that are called before events for preprocessing.
        This is deprecated and will be removed in the future. Use before_request instead
        """
        warn(
            "Middleware method is deprecated. Use before_request instead",
            DeprecationWarning,
            stacklevel=2,
        )

        if event_type not in EVENT_TYPES:
            raise ValueError(f"{event_type} not in {EVENT_TYPES}")

        def _middleware_wrapper(func):
            self.register_middleware(func, event_type)
            return func

        return _middleware_wrapper

    def route(self, path, methods=["GET"], **kwargs):
        """Api Gateway route"""
        return self._create_registration_function(
            handler_type="route",
            registration_kwargs={"path": path, "methods": methods, "kwargs": kwargs},
        )

    def schedule(self, schedule, timezone="UTC", **kwargs):
        """Scheduler job Http trigger"""
        return self._create_registration_function(
            handler_type="schedule",
            registration_kwargs={
                "schedule": schedule,
                "timezone": timezone,
                "kwargs": kwargs,
            },
        )

    def bqremotefunction(
        self, dataset_id, vectorize_func=False, max_batching_rows=0, **kwargs
    ):
        """
        BigQuery remote function trigger
        dataset_id: Where the function will be registered
        vectorize_func: If True, ensure every argument of your function is a list, and returns a list
        max_batching_rows: Max number of rows in each batch sent to the remote service. 0 for dynamic
        """
        return self._create_registration_function(
            handler_type="bqremotefunction",
            registration_kwargs={
                "dataset_id": dataset_id,
                "vectorize_func": vectorize_func,
                "max_batching_rows": max_batching_rows,
                "kwargs": kwargs,
            },
        )

    def pubsub_subscription(self, topic, **kwargs):
        """Pubsub topic trigger"""
        dlq = kwargs.pop("dlq", False)
        dlq_topic_config = kwargs.pop("dlq_topic_config", {})
        dlq_alert = kwargs.pop("dlq_alert", False)
        dlq_alert_config = kwargs.pop("dlq_alert_config", {})
        if dlq:
            log.info(f"DLQ enabled use of subscription will be forced to topic {topic}")
            kwargs["use_subscription"] = True
            dlq_topic_name = (
                f"{topic}-dlq"
                if "name" not in dlq_topic_config
                else dlq_topic_config.pop("name")
            )
            dlq_pull_subscription_config = dlq_topic_config.pop(
                "pull_subscription_config", {}
            )
            dlq_pull_subscription_name = (
                f"{dlq_topic_name}-pull-subscription"
                if "name" not in dlq_pull_subscription_config
                else dlq_pull_subscription_config.pop("name")
            )
            # Create DLQ topic
            self._register_infrastructure(
                handler_type="pubsub_topic",
                kwargs={
                    "name": dlq_topic_name,
                    "kwargs": {
                        "config": dlq_topic_config,
                        "dlq": True,
                        "dlq_pull_subscription": {
                            "name": dlq_pull_subscription_name,
                            "config": dlq_pull_subscription_config,
                        },
                    },
                },
            )
            dlq_policy = {
                "deadLetterPolicy": {
                    "deadLetterTopic": self.infrastructure["pubsub_topic"].resources[
                        dlq_topic_name
                    ]["name"],
                }
            }
            if "config" in kwargs:
                kwargs["config"].update(dlq_policy)
            else:
                kwargs["config"] = dlq_policy

            if dlq_alert:
                sub_name = f"{self.function_name}-{topic}"
                log.info(f"DLQ alert enabled for subscription {sub_name}")
                dlq_alert_name = (
                    f"{sub_name}-dlq-alert"
                    if "name" not in dlq_alert_config
                    else dlq_alert_config.pop("name")
                )
                dlq_alert_trigger_value = (
                    0
                    if "trigger_value" not in dlq_alert_config
                    else dlq_alert_config.pop("trigger_value")
                )
                dlq_alert_config["conditions"] = [
                    PubSubDLQCondition(
                        "pubsub",
                        subscription_id=sub_name,
                        value=dlq_alert_trigger_value,
                    )
                ]
                self._register_infrastructure(
                    handler_type="alerts",
                    kwargs={"name": dlq_alert_name, "kwargs": dlq_alert_config},
                )

        return self._create_registration_function(
            handler_type="pubsub",
            registration_kwargs={"topic": topic, "kwargs": kwargs},
        )

    def topic(self, topic, **kwargs):
        warn(
            "This method is deprecated, use @app.pubsub_subscription",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.pubsub_subscription(topic, **kwargs)

    def cloudtasktarget(self, name, **kwargs):
        """CloudTask trigger"""
        kwargs["name"] = name
        return self._create_registration_function(
            handler_type="cloudtasktarget",
            registration_kwargs={"name": name, "kwargs": kwargs},
        )

    def storage(self, bucket, event_type, name=None):
        """Storage event trigger"""
        return self._create_registration_function(
            handler_type="storage",
            registration_kwargs={
                "bucket": bucket,
                "event_type": event_type,
                "name": name,
            },
        )

    def eventarc(self, topic=None, event_filters=[], **kwargs):
        """Eventarc trigger"""
        return self._create_registration_function(
            handler_type="eventarc",
            registration_kwargs={
                "topic": topic,
                "event_filters": event_filters,
                "kwargs": kwargs,
            },
        )

    def http(self, headers={}):
        """Base http trigger"""
        return self._create_registration_function(
            handler_type="http",
            registration_kwargs={"headers": headers},
        )

    def job(self, name, task_id=0, schedule=None, timezone="UTC", **kwargs):
        """Cloudrun Job"""
        if schedule and task_id != 0:
            raise ValueError("Schedule can only be added to task_id with value 0")
        if kwargs and task_id != 0:
            raise ValueError("Arguments can only be added to task_id with value 0")
        if schedule:
            self._register_handler(
                "schedule",
                f"schedule-job-{name}",
                None,
                kwargs={
                    "schedule": schedule,
                    "timezone": timezone,
                    "kwargs": {
                        "uri": f"https://{get_default_location()}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/{get_default_project()}/jobs/{self.function_name}-{name}:run",
                        "httpMethod": "POST",
                        "authMethod": "oauthToken",
                        **kwargs,
                    },
                },
            )
        return self._create_registration_function(
            handler_type="jobs",
            registration_kwargs={"name": name, "task_id": task_id, "kwargs": kwargs},
        )

    def apigateway(self, name, backend_url, filename=None, openapi_dict=None, **kwargs):
        """Api Gateway Infrastructure with an existing openapi spec.
        Requires either a filename or openapi_dict"""
        if not filename and not openapi_dict:
            raise ValueError(
                "Either a filename or the openapi_dict needs to be provided"
            )
        if filename and openapi_dict:
            raise ValueError(
                "Only one of either a filename or the openapi_dict needs to be provided"
            )
        if filename:
            with open(filename) as f:
                openapi_dict = yaml.safe_load(f.read())
        return self._register_infrastructure(
            handler_type="apigateway",
            kwargs={
                "name": name,
                "kwargs": {
                    "backend_url": backend_url,
                    "openapi_dict": openapi_dict,
                    **kwargs,
                },
            },
        )

    def alert(self, name, conditions, **kwargs):
        """Alert Resource"""
        kwargs["conditions"] = conditions
        return self._register_infrastructure(
            handler_type="alerts",
            kwargs={"name": name, "kwargs": kwargs},
        )

    def cloudtaskqueue(self, name, config=None, **kwargs):
        """CloudTask Queue Infrastructure"""
        kwargs["config"] = config
        return self._register_infrastructure(
            handler_type="cloudtaskqueue",
            kwargs={"name": name, "config": config, "kwargs": kwargs},
        )

    def pubsub_topic(self, name, config=None, **kwargs):
        """PubSub Topic Infrastructure"""
        kwargs["config"] = config
        return self._register_infrastructure(
            handler_type="pubsub_topic",
            kwargs={"name": name, "config": config, "kwargs": kwargs},
        )

    def redis(self, name, **kwargs):
        """Redis Infrastructure"""
        return self._register_infrastructure(
            handler_type="redis",
            kwargs={"name": name, "kwargs": kwargs},
        )

    def vpcconnector(self, name, **kwargs):
        """VPC Connector Infrastructure"""
        return self._register_infrastructure(
            handler_type="vpcconnector",
            kwargs={"name": name, "kwargs": kwargs},
        )

    def stage(self, stage=None, stages=[]):
        if not stage and not stages:
            raise ValueError("One of stage or stages should be set")

        # Only registers if stage matches.
        def _register_stage(func):
            if os.getenv("STAGE") == stage or os.getenv("STAGE") in stages:
                return func

        return _register_stage

    def _create_registration_function(self, handler_type, registration_kwargs=None):
        def _register_handler(user_handler):
            if user_handler:
                handler_name = user_handler.__name__
                kwargs = registration_kwargs or {}
                self._register_handler(handler_type, handler_name, user_handler, kwargs)
            return user_handler

        return _register_handler

    def _register_handler(self, handler_type, name, func, kwargs, options=None):
        name = kwargs.get("kwargs", {}).get("name") or name
        self.handlers[handler_type].register(name=name, func=func, kwargs=kwargs)

    def _register_infrastructure(self, handler_type, kwargs, options=None):
        return self.infrastructure[handler_type].register(
            kwargs["name"], kwargs=kwargs.get("kwargs", {})
        )

    def register_middleware(self, func, event_type="all", before_or_after="before"):
        middleware_list = self.middleware_handlers[before_or_after].get(event_type, [])
        middleware_list.append(func)
        self.middleware_handlers[before_or_after][event_type] = middleware_list

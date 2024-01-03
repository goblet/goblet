import logging
import os

from goblet_gcp_client.client import get_default_project

from googleapiclient.errors import HttpError

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class AlertCondition:
    """Base class for Alert Conditions. Only one of type threshold, absense, log_match, or MQL can be specified per condition.
    The method format_filter_or_query is used to inject values from the backend into the filters and conditions. These can be injected into
    custom filters as well. Currently monitoring_type,resource_name, and monitoring_label_key are supported.
    """

    def __init__(
        self, name, threshold=None, absence=None, log_match=None, MQL=None
    ) -> None:
        self.name = name
        self.app_name = ""
        if [threshold, absence, log_match, MQL].count(None) != 3:
            raise ValueError("Exactly 1 condition option can be set")
        if threshold:
            self.condition_key = "conditionThreshold"
            self._condition = threshold
        if absence:
            self.condition_key = "conditionAbsent"
            self._condition = absence
        if log_match:
            self.condition_key = "conditionMatchedLog"
            self._condition = log_match
        if MQL:
            self.condition_key = "conditionMonitoringQueryLanguage"
            self._condition = MQL
        self.filter = self._condition.get("filter")
        # For MQL
        self.query = self._condition.get("query")
        self.default_alert_kwargs = {}

    @property
    def condition(self):
        if self._condition.get("filter"):
            self._condition["filter"] = self.filter
        if self._condition.get("query"):
            self._condition["query"] = self.query
        return {
            "displayName": f"{self.name}",
            self.condition_key: self._condition,
        }

    def format_filter_or_query(self, **kwargs):
        self.filter = self.filter.format(**kwargs)
        return

    def deploy_extra(self, versioned_clients):
        pass

    def destroy_extra(self, versioned_clients):
        pass


class MetricCondition(AlertCondition):
    """
    https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies#MetricThreshold
    """

    def __init__(
        self, name, metric, value, duration="60s", comparison="COMPARISON_GT", **kwargs
    ) -> None:
        super().__init__(
            name=name,
            threshold={
                "filter": 'resource.type="{monitoring_type}" AND resource.labels.{monitoring_label_key}="{resource_name}" AND metric.type = "{metric}"'.format(
                    metric=metric,
                    monitoring_type="{monitoring_type}",
                    monitoring_label_key="{monitoring_label_key}",
                    resource_name="{resource_name}",
                ),
                "thresholdValue": value,
                "duration": duration,
                "comparison": comparison,
                "aggregations": [
                    {
                        "alignmentPeriod": "300s",
                        "crossSeriesReducer": "REDUCE_NONE",
                        "perSeriesAligner": "ALIGN_MEAN",
                    }
                ],
                **kwargs,
            },
        )


class CustomMetricCondition(MetricCondition):
    """
    Creates and deploys a custom metric specified by the user, before creating a generic metric condition.
    """

    def __init__(
        self, name, metric_filter, value, metric_descriptor={}, **kwargs
    ) -> None:
        self.metric_filter = (
            'resource.type="{monitoring_type}" resource.labels.{monitoring_label_key}="{resource_name}" '
            + metric_filter
        )

        super().__init__(
            name=name,
            metric=f"logging.googleapis.com/user/{{resource_name}}-{name}",
            value=value,
            **kwargs,
        )

    def format_filter_or_query(
        self, app_name, monitoring_type, resource_name, monitoring_label_key
    ):
        self.app_name = app_name
        self.filter = self.filter.format(
            monitoring_type=monitoring_type,
            resource_name=resource_name,
            monitoring_label_key=monitoring_label_key,
        )

        self.metric_filter = self.metric_filter.format(
            monitoring_type=monitoring_type,
            resource_name=resource_name,
            monitoring_label_key=monitoring_label_key,
        )
        return

    def deploy_extra(self, versioned_clients):
        # Defaults
        metric_descriptor = {
            "name": f"projects/{get_default_project}/metricDescriptors/logging.googleapis.com/user/{self.app_name}-{self.name}",
            "metricKind": "DELTA",
            "valueType": "INT64",
            "unit": "1",
            "description": "measure error rates in media-metadata-service cloudfunction",
            "type": f"logging.googleapis.com/user/{self.app_name}-{self.name}",
        }
        # User Override
        metric_descriptor.update(metric_descriptor)

        metric_body = {
            "name": f"{self.app_name}-{self.name}",
            "description": f"Goblet generated custom metric for metric {self.app_name}-{self.name}",
            "filter": self.metric_filter,
            "metricDescriptor": metric_descriptor,
        }
        try:
            versioned_clients.logging_metric.execute(
                "create",
                params={"body": metric_body},
            )
            log.info(f"deploying custom metric {self.app_name}-{self.name}")
        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"updating custom metric {self.app_name}-{self.name}")
                versioned_clients.logging_metric.execute(
                    "update",
                    parent_key="metricName",
                    parent_schema=f"projects/{get_default_project()}/metrics/{self.app_name}-{self.name}",
                    params={"body": metric_body},
                )
            else:
                raise e

    def destroy_extra(self, versioned_clients):
        try:
            versioned_clients.logging_metric.execute(
                "delete",
                parent_key="metricName",
                parent_schema=f"projects/{get_default_project()}/metrics/{self.app_name}-{self.name}",
            )
            log.info(f"deleting custom metric {self.app_name}-{self.name}")
        except HttpError as e:
            if e.resp.status == 404:
                log.info(f"Custom metric {self.app_name}-{self.name} already destroyed")
            else:
                raise e


class LogMatchCondition(AlertCondition):
    """
    https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies#LogMatch
    """

    def __init__(self, name, filter, **kwargs) -> None:
        super().__init__(
            name=name,
            log_match={
                "filter": filter
                if kwargs.get("replace_filter", False)
                else 'resource.type="{monitoring_type}"\nresource.labels.{monitoring_label_key}="{resource_name}"\n'
                + filter
            },
        )
        self.default_alert_kwargs = {
            "alertStrategy": {
                "notificationRateLimit": {"period": "300s"},
                "autoClose": "604800s",
            }
        }


class PubSubDLQCondition(MetricCondition):
    """
    Creates and deploys an alert for dead letter queue messages in a pubsub subscription.
    """

    def __init__(self, name, value=0, **kwargs) -> None:
        super().__init__(
            name=name,
            metric="pubsub.googleapis.com/subscription/dead_letter_message_count",
            value=value,
            filter='resource.labels.subscription_id = "{subscription_id}" AND resource.type = "pubsub_subscription" AND metric.type = "pubsub.googleapis.com/subscription/dead_letter_message_count"',
            **kwargs,
        )


class UptimeCondition(MetricCondition):
    """
    Creates and deploys an alert condition for failed uptime checks.
    Supports `uptime_url` or `cloud_run_revision`
    """

    def __init__(self, name, value=0.5, **kwargs) -> None:
        super().__init__(
            name=name,
            metric="monitoring.googleapis.com/uptime_check/check_passed",
            value=value,
            filter='resource.type = "uptime_url" AND metric.labels.check_id = "{check_id}" AND metric.type = "monitoring.googleapis.com/uptime_check/check_passed"',
            aggregations=[
                {
                    "alignmentPeriod": "1200s",
                    "crossSeriesReducer": "REDUCE_NONE",
                    "perSeriesAligner": "ALIGN_FRACTION_TRUE",
                }
            ],
            comparison="COMPARISON_LT",
            **kwargs,
        )

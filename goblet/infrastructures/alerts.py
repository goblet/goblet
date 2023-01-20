import logging

from goblet.infrastructures.infrastructure import Infrastructure
from goblet.client import (
    get_default_project,
)
from goblet.config import GConfig

from googleapiclient.errors import HttpError

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class Alerts(Infrastructure):
    """Cloud Monitoring Alert Policies that can trigger notification channels based on built in or custom metrics.
    https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies. Alerts and Alert conditions contain a
    few common defaults, that are used by GCP. These can be overriden by passing in the correct params.
    """

    resource_type = "alerts"
    can_sync = True
    _gcp_deployed_alerts = {}

    def register(self, name, **kwargs):
        kwargs = kwargs.get("kwargs", {})
        conditions = kwargs.pop("conditions")
        notification_channels = kwargs.pop("notification_channels", [])
        self.resource[f"{self.name}-{name}"] = {
            "name": f"{self.name}-{name}",
            "conditions": conditions,
            "notification_channels": notification_channels,
            "kwargs": kwargs,
        }

    @property
    def gcp_deployed_alerts(self):
        """
        List of deployed gcp alerts, since we need to get unique id's from alerts in order to patch or avoid creating duplicates
        """
        if not self._gcp_deployed_alerts:
            alerts = self.client.monitoring_alert.execute(
                "list",
                parent_key="name",
                params={"filter": f'display_name=starts_with("{self.name}-")'},
            )
            for alert in alerts.get("alertPolicies", []):
                self._gcp_deployed_alerts[alert["displayName"]] = alert
        return self._gcp_deployed_alerts

    def get_config(self):
        return None

    def deploy(self, source=None, entrypoint=None, config={}):
        if not self.resource:
            return
        gconfig = GConfig(config=config)
        config_notification_channels = []
        if gconfig.alerts:
            config_notification_channels = gconfig.alerts.get(
                "notification_channels", []
            )

        log.info("deploying alerts......")
        for alert_name, alert in self.resource.items():
            self.deploy_alert(alert_name, alert, config_notification_channels)

    def deploy_alert(self, alert_name, alert, notification_channels):
        formatted_conditions = []
        default_alert_kwargs = {}
        for condition in alert["conditions"]:
            condition.format_filter_or_query(
                self.name,
                self.backend.monitoring_type,
                self.backend.name,
                self.backend.monitoring_label_key,
            )
            default_alert_kwargs.update(condition.default_alert_kwargs)
            formatted_conditions.append(condition.condition)

            # deploy custom metrics if needed
            condition.deploy_extra(self.client)

        default_alert_kwargs.update(alert["kwargs"])
        alert["notification_channels"].extend(notification_channels)

        body = {
            "displayName": alert_name,
            "conditions": formatted_conditions,
            "notificationChannels": alert["notification_channels"],
            "combiner": "OR",
            **default_alert_kwargs,
        }
        # check if exists
        if alert_name in self.gcp_deployed_alerts:
            # patch
            self.client.monitoring_alert.execute(
                "patch",
                parent_key="name",
                parent_schema=self.gcp_deployed_alerts[alert_name]["name"],
                params={"updateMask": ",".join(body.keys()), "body": body},
            )

            log.info(f"updated alert: {alert_name}")
        else:
            # deploy
            self.client.monitoring_alert.execute(
                "create",
                parent_key="name",
                params={"body": body},
            )
            log.info(f"created alert: {alert_name}")

    def _sync(self, dryrun=False):
        # Does not sync custom metrics
        for alert_name in self.gcp_deployed_alerts.keys():
            if not self.resource.get(alert_name):
                log.info(f"Detected unused alert {alert_name}")
                if not dryrun:
                    self._destroy_alert(alert_name)

    def destroy(self):
        if not self.resource:
            return
        for alert_name in self.resource.keys():
            self._destroy_alert(alert_name)

    def _destroy_alert(self, alert_name):
        if not self.gcp_deployed_alerts.get(alert_name):
            log.info(f"Alert {alert_name} already destroyed")
        else:
            try:
                self.client.monitoring_alert.execute(
                    "delete",
                    parent_key="name",
                    parent_schema=self.gcp_deployed_alerts[alert_name]["name"],
                )
                log.info(f"Destroying alert {alert_name}......")
            except HttpError as e:
                if e.resp.status == 404:
                    log.info(f"Alert {alert_name} already destroyed")
                else:
                    raise e
        for condition in self.resource.get(alert_name, {}).get("conditions", []):
            condition.format_filter_or_query(
                self.name,
                self.backend.monitoring_type,
                self.backend.name,
                self.backend.monitoring_label_key,
            )
            condition.destroy_extra(self.client)


class AlertCondition:
    """Base class for Alert Conditions. Only one of type threshold, absense, log_match, or MQL can be specified per condition.
    The method format_filter_or_query is used to inject values from the backend into the filters and conditions. These can be injected into
    custom filters as well. Currently monitoring_type,resource_name, and monitoring_label_key are supported."""

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
            "displayName": f"{self.app_name}-{self.name}",
            self.condition_key: self._condition,
        }

    def format_filter_or_query(
        self, app_name, monitoring_type, resource_name, monitoring_label_key
    ):
        self.app_name = app_name
        self.filter = self.filter.format(
            monitoring_type=monitoring_type,
            resource_name=resource_name,
            monitoring_label_key=monitoring_label_key,
        )
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
                "filter": 'resource.type="{monitoring_type}"\nresource.labels.{monitoring_label_key}="{resource_name}"\n'
                + filter
            },
        )
        self.default_alert_kwargs = {
            "alertStrategy": {
                "notificationRateLimit": {"period": "300s"},
                "autoClose": "604800s",
            }
        }

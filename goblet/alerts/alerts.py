import logging
import os
import goblet.globals as g

from goblet.permissions import gcp_generic_resource_permissions
from goblet.client import VersionedClients
from goblet.errors import GobletValidationError

from googleapiclient.errors import HttpError

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class Alerts:
    """Cloud Monitoring Alert Policies that can trigger notification channels based on built in or custom metrics.
    https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies.
    """

    permissions = [
        *gcp_generic_resource_permissions("monitoring", "alertPolicies"),
        *gcp_generic_resource_permissions("logging", "logMetrics"),
    ]
    required_apis = ["logging"]
    can_sync = True
    checked_alerts = False
    _gcp_deployed_alerts = {}

    def __init__(self, name, resources=None) -> None:
        self.config = g.config
        self.versioned_clients = VersionedClients()
        self.name = name
        self.resources = resources or {}

    def register(self, alert):
        self.resources[alert.name] = alert

    @property
    def gcp_deployed_alerts(self):
        """
        List of deployed gcp alerts, since we need to get unique id's from alerts in order to patch or avoid creating duplicates
        """
        if not self.checked_alerts:
            self.checked_alerts = True
            alerts = self.versioned_clients.monitoring_alert.execute(
                "list",
                parent_key="name",
                params={"filter": f'display_name=starts_with("{self.name}-")'},
            )
            for alert in alerts.get("alertPolicies", []):
                self._gcp_deployed_alerts[alert["displayName"]] = alert
        return self._gcp_deployed_alerts

    def deploy(self, alert_type):
        if not self.resources:
            return
        filtered_alerts = [
            alert
            for _, alert in self.resources.items()
            if alert.alert_type == alert_type
        ]

        for alert in filtered_alerts:
            alert.deploy(self.name, self.gcp_deployed_alerts)

    def destroy(self, alert_type):
        if not self.resources:
            return
        filtered_alerts = [
            alert
            for _, alert in self.resources.items()
            if alert.alert_type == alert_type
        ]

        for alert in filtered_alerts:
            alert.destroy(
                self.name, self.gcp_deployed_alerts[f"{self.name}-{alert.name}"]["name"]
            )

    def sync(self, dryrun=False):
        # Does not sync custom metrics
        for alert_name, alert in self.gcp_deployed_alerts.values():
            if not self.resources.get(alert_name):
                log.info(f"Detected unused alert {alert_name}")
                if not dryrun:
                    self.resources[alert_name].destroy(alert["name"])


class Alert:
    """Cloud Monitoring Alert Policies that can trigger notification channels based on built in or custom metrics.
    https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies. Alerts and Alert conditions contain a
    few common defaults, that are used by GCP. These can be overriden by passing in the correct params.
    """

    alert_type = None
    extras = {}

    def __init__(self, name, conditions, channels=[], extras=None, **kwargs) -> None:
        self.config = g.config
        self.versioned_clients = VersionedClients()
        self.name = name
        self.app_name = ""
        self.conditions = conditions
        self.notification_channels = self.config.alerts.get(
            "notification_channels", channels
        )
        self.kwargs = kwargs
        if extras:
            self.extras = extras

    def deploy(self, app_name, gcp_deployed_alerts):
        self.app_name = app_name
        if not self.validate_extras():
            raise GobletValidationError("Missing extra fields needed for this alert")
        formatted_conditions = []
        default_alert_kwargs = {}
        for condition in self.conditions:
            condition.format_filter_or_query(**self._condition_arguments())
            formatted_conditions.append(condition.condition)

            # deploy custom metrics if needed
            condition.deploy_extra(self.versioned_clients)

            # some conditions require certain alert configuration
            default_alert_kwargs.update(condition.default_alert_kwargs)

        default_alert_kwargs.update(self.kwargs)

        body = {
            "displayName": self.name,
            "conditions": formatted_conditions,
            "notificationChannels": self.notification_channels,
            "combiner": "OR",
            **default_alert_kwargs,
        }
        # check if exists
        if self.name in gcp_deployed_alerts:
            # patch
            self.versioned_clients.monitoring_alert.execute(
                "patch",
                parent_key="name",
                parent_schema=gcp_deployed_alerts[self.name]["name"],
                params={"updateMask": ",".join(body.keys()), "body": body},
            )

            log.info(f"updated alert: {self.name}")
        else:
            # deploy
            self.versioned_clients.monitoring_alert.execute(
                "create",
                parent_key="name",
                params={"body": body},
            )
            log.info(f"created alert: {self.name}")

    def destroy(self, app_name, full_alert_name):
        self.app_name = app_name
        for condition in self.conditions:
            condition.format_filter_or_query(**self._condition_arguments())

        self._destroy_alert(full_alert_name)

    def _destroy_alert(self, full_alert_name):
        try:
            self.versioned_clients.monitoring_alert.execute(
                "delete",
                parent_key="name",
                parent_schema=full_alert_name,
            )
            log.info(f"Destroying alert {self.name}......")
        except HttpError as e:
            if e.resp.status == 404:
                log.info(f"Alert {self.name} already destroyed")
            else:
                raise e
        for condition in self.conditions:
            condition.destroy_extra(self.versioned_clients)

    def validate_extras(self):
        return True

    def _condition_arguments(self):
        return {"app_name": self.app_name}

    def update_extras(self, extras):
        self.extras.update(extras)
        return


class BackendAlert(Alert):
    alert_type = "backend"

    def validate_extras(self):
        return list(self.extras.keys()) == [
            "monitoring_type",
            "resource_name",
            "monitoring_label_key",
        ]

    def _condition_arguments(self):
        return {
            "app_name": self.app_name,
            "monitoring_type": self.extras["monitoring_type"],
            "resource_name": self.extras["resource_name"],
            "monitoring_label_key": self.extras["monitoring_label_key"],
        }


class PubSubDLQAlert(Alert):
    alert_type = "handler"

    def validate_extras(self):
        return "topic" in self.extras.keys()

    def _condition_arguments(self):
        return {
            "app_name": self.app_name,
            "subscription_id": f"{self.name}-{self.extras['topic']}",
        }

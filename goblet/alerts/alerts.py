import logging
import os
import goblet.globals as g

# from goblet_gcp_client.client import get_default_project
from goblet.permissions import gcp_generic_resource_permissions
from goblet.client import VersionedClients
from goblet.backends.backend import Backend
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
        if not self._gcp_deployed_alerts:
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
            alert for _, alert in self.resources.items() if alert.type == alert_type
        ]

        for alert in filtered_alerts:
            alert.deploy(self.versioned_clients, self.gcp_deployed_alerts)

    def destroy(self, alert_type):
        if not self.resources:
            return
        filtered_alerts = [
            alert for _, alert in self.resources.items() if alert.type == alert_type
        ]

        for alert in filtered_alerts:
            alert.destroy(self.versioned_clients, self.gcp_deployed_alerts)

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

    def __init__(self, name, resource, conditions, channels=[], **kwargs) -> None:
        self.config = g.config
        self.versioned_clients = VersionedClients()
        self.name = name
        self.resource = resource
        if not self.validate_resource_type():
            raise GobletValidationError("Not a valid resource for this type of alert")

        self.conditions = conditions
        self.notification_channels = self.config.alerts.get(
            "notification_channels", channels
        )
        self.kwargs = kwargs

    def deploy(self, gcp_deployed_alerts):
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

    def destroy(self, full_alert_name):
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

    def validate_resource_type(self):
        return True

    def _condition_arguments(self):
        return {"name": self.name}


class BackendAlert(Alert):
    type = "backend"

    def validate_resource_type(self):
        return isinstance(self.resource, Backend)

    def _condition_arguments(self):
        return {
            "app_name": self.name,
            "monitoring_type": self.resource.monitoring_type,
            "resource_name": self.resource.name,
            "monitoring_label_key": self.resource.monitoring_label_key,
        }

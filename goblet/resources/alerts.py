import logging

from goblet.resources.handler import Handler
from goblet.client import (
    get_default_project,
    get_default_location,
)
from goblet.common_cloud_actions import get_cloudrun_url
from goblet.config import GConfig

from googleapiclient.errors import HttpError

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class Alerts(Handler):
    """Cloud Monitoring Alert Policies that can trigger notification channels based on built in or custom metrics.
    https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies
    """

    resource_type = "alerts"
    valid_backends = ["cloudfunction", "cloudfunctionv2", "cloudrun"]
    can_sync = True

    def register_alert(self, name, conditions, notification_channels=[], **kwargs):
        # custom log condition?
        self.resources[name] = {
            "name": name,
            "conditions": conditions,
            "notification_channels": notification_channels,
            "kwargs": kwargs,
        }

    def _deploy(self, source=None, entrypoint=None, config={}):
        if not self.resources:
            return

        log.info("deploying alerts......")
        for alert_name, alert in self.resources.items():
            self.deploy_alert(alert_name, alert)

    def deploy_alert(self, alert_name, alert):
        formatted_conditions = []
        default_alert_kwargs = {}
        for condition in alert["conditions"]:
            condition.format_filter_or_query(
                self.backend.monitoring_type,
                self.backend.name,
                self.backend.monitoring_label_key,
            )
            default_alert_kwargs.update(condition.default_alert_kwargs)
            formatted_conditions.append(condition.condition)

            # deploy custom metrics if needed
            condition.deploy_extra(self.versioned_clients)

        default_alert_kwargs.update(alert["kwargs"])
        try:
            self.versioned_clients.monitoring_alert.execute(
                "create",
                parent_key="name",
                params={
                    "body": {
                        "displayName": alert_name,
                        "conditions": formatted_conditions,
                        "notificationChannels": alert["notification_channels"],
                        "combiner": "OR",
                        **default_alert_kwargs,
                    }
                },
            )
            log.info(f"created alert: {alert_name} for {self.name}")
        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"updated scheduled job: {alert_name} for {self.name}")
                # self.versioned_clients.cloudscheduler.execute(
                #     "patch",
                #     parent_key="name",
                #     parent_schema=job["name"],
                #     params={"body": job},
                # )
            else:
                raise e

    # def _sync(self, dryrun=False):
    #     jobs = self.versioned_clients.cloudscheduler.execute("list").get("jobs", [])
    #     filtered_jobs = list(
    #         filter(lambda job: f"jobs/{self.name}-" in job["name"], jobs)
    #     )
    #     for filtered_job in filtered_jobs:
    #         split_name = filtered_job["name"].split("/")[-1].split("-")
    #         filtered_name = split_name[1]
    #         if not self.resources.get(filtered_name):
    #             log.info(f'Detected unused job in GCP {filtered_job["name"]}')
    #             if not dryrun:
    #                 # TODO: Handle deleting multiple jobs with same name
    #                 self._destroy_job(filtered_name)

    # def deploy_job(self, job_name, job):
    #     try:
    #         self.versioned_clients.cloudscheduler.execute(
    #             "create", params={"body": job}
    #         )
    #         log.info(f"created scheduled job: {job_name} for {self.name}")
    #     except HttpError as e:
    #         if e.resp.status == 409:
    #             log.info(f"updated scheduled job: {job_name} for {self.name}")
    #             self.versioned_clients.cloudscheduler.execute(
    #                 "patch",
    #                 parent_key="name",
    #                 parent_schema=job["name"],
    #                 params={"body": job},
    #             )
    #         else:
    #             raise e

    # def destroy(self):
    #     if not self.resources:
    #         return
    #     for job_name in self.resources.keys():
    #         self._destroy_job(job_name)

    # def _destroy_job(self, job_name):
    #     try:
    #         self.versioned_clients.cloudscheduler.execute(
    #             "delete",
    #             parent_key="name",
    #             parent_schema="projects/{project_id}/locations/{location_id}/jobs/"
    #             + self.name
    #             + "-"
    #             + job_name,
    #         )
    #         log.info(f"Destroying scheduled job {job_name}......")
    #     except HttpError as e:
    #         if e.resp.status == 404:
    #             log.info("Scheduled jobs already destroyed")
    #         else:
    #             raise e


class AlertCondition:
    def __init__(
        self, name, threshold=None, absence=None, log_match=None, MQL=None
    ) -> None:
        self.name = name
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
        return {"displayName": self.name, self.condition_key: self._condition}

    def format_filter_or_query(
        self, monitoring_type, resource_name, monitoring_label_key
    ):
        self.filter = self.filter.format(
            monitoring_type=monitoring_type,
            resource_name=resource_name,
            monitoring_label_key=monitoring_label_key,
        )
        return

    def deploy_extra(self, versioned_clients):
        pass


class MetricCondition(AlertCondition):
    # https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies#MetricThreshold
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
    def __init__(
        self, name, metric_filter, value, metric_descriptor={}, **kwargs
    ) -> None:
        self.metric_filter = 'resource.type="{monitoring_type}" resource.labels.{monitoring_label_key}="{resource_name}" ' + metric_filter
        # Defaults
        self.metric_descriptor = {
            "name":f"projects/{get_default_project}/metricDescriptors/logging.googleapis.com/user/{name}",
            "metricKind": "DELTA",
            "valueType": "INT64",
            "unit": "1",
            "description": "measure error rates in media-metadata-service cloudfunction",
            "type": f"logging.googleapis.com/user/{name}",
        }
        # User Override
        self.metric_descriptor.update(metric_descriptor)

        super().__init__(
            name=name,
            metric=f"logging.googleapis.com/user/{name}",
            value=value,
            **kwargs
        )


    def format_filter_or_query(
        self, monitoring_type, resource_name, monitoring_label_key
    ):
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
        metric_body = {
            "name": self.name,
            "description": f"Goblet generated custom metric for metric {self.name}",
            "filter": self.metric_filter,
            "metricDescriptor": self.metric_descriptor
        }
        log.info(f"deploying custom metric {self.name}")
        versioned_clients.logging_metric.execute(
                "create",
                params={
                    "body": metric_body
                },
            )


        # severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)
# "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"media-metadata-service\" severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)
# {
#   "name": "media-metadata-service-errors-metric",
#   "description": "measure error rates in media-metadata-service cloudfunction",
#   "filter": "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"media-metadata-service\" severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)",
#   "metricDescriptor": {
#     "name": "projects/premise-data-platform-prod/metricDescriptors/logging.googleapis.com/user/media-metadata-service-errors-metric",
#     "metricKind": "DELTA",
#     "valueType": "INT64",
#     "unit": "1",
#     "description": "measure error rates in media-metadata-service cloudfunction",
#     "type": "logging.googleapis.com/user/media-metadata-service-errors-metric"
#   },
#   "createTime": "2022-09-28T20:58:57.256243488Z",
#   "updateTime": "2022-10-18T14:00:17.944708237Z"
# }



class ErrorLoggedCondition(AlertCondition):
    def __init__(self, name, **kwargs) -> None:
        super().__init__(
            name=name,
            log_match={
                "filter": 'resource.type="{monitoring_type}" \n severity>=ERROR \n resource.labels.{monitoring_label_key}="{resource_name}"'
            },
        )
        self.default_alert_kwargs = {
            "alertStrategy": {
                "notificationRateLimit": {"period": "300s"},
                "autoClose": "604800s",
            }
        }

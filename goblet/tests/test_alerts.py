from goblet import Goblet
from goblet.alerts.alert_conditions import (
    MetricCondition,
    LogMatchCondition,
    CustomMetricCondition,
    PubSubDLQCondition,
)
from goblet.alerts.alerts import BackendAlert, PubSubDLQAlert
from goblet.backends import CloudFunctionV1

from goblet_gcp_client import (
    get_response,
    get_responses,
    reset_replay_count,
    get_replay_count,
)


class TestAlerts:
    def test_add_alert(self):
        app = Goblet(function_name="goblet_example")

        metric_alert = BackendAlert(
            "metric",
            conditions=[
                MetricCondition(
                    "test",
                    metric="cloudfunctions.googleapis.com/function/execution_count",
                    value=10,
                )
            ],
        )
        log_alert = BackendAlert(
            "error",
            conditions=[LogMatchCondition("error", "severity>=ERROR")],
        )
        custom_alert = BackendAlert(
            "custom",
            conditions=[
                CustomMetricCondition(
                    "custom",
                    metric_filter="severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)",
                    value=10,
                )
            ],
        )

        app.alert(metric_alert)
        app.alert(log_alert)
        app.alert(custom_alert)

        alerts = app.alerts
        assert len(alerts.resources) == 3

    def test_format_filter_or_query(self):
        condition = MetricCondition(
            "test",
            metric="cloudfunctions.googleapis.com/function/execution_count",
            value=10,
        )
        condition.format_filter_or_query(
            **{
                "app_name": "test",
                "monitoring_type": CloudFunctionV1.monitoring_type,
                "resource_name": "name",
                "monitoring_label_key": CloudFunctionV1.monitoring_label_key,
            }
        )
        assert (
            condition.filter
            == 'resource.type="cloud_function" AND resource.labels.function_name="name" AND metric.type = "cloudfunctions.googleapis.com/function/execution_count"'
        )

    def test_deploy_alerts(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "alerts-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        reset_replay_count()

        app = Goblet(function_name="alerts-test")

        metric_alert = BackendAlert(
            "metric",
            conditions=[
                MetricCondition(
                    "test",
                    metric="cloudfunctions.googleapis.com/function/execution_count",
                    value=10,
                )
            ],
        )
        log_alert = BackendAlert(
            "error",
            conditions=[LogMatchCondition("error", "severity>=ERROR")],
        )
        custom_alert = BackendAlert(
            "custom",
            conditions=[
                CustomMetricCondition(
                    "custom",
                    metric_filter="severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)",
                    value=10,
                )
            ],
        )

        pubsub_dlq = PubSubDLQAlert(
            "pubsubdlq",
            conditions=[
                PubSubDLQCondition(
                    "pubsubdlq",
                    subscription_id="pubsub-deploy-subscription",
                )
            ],
            extras={"topic": "subscription"},
        )

        app.alert(metric_alert)
        app.alert(log_alert)
        app.alert(custom_alert)
        app.alert(pubsub_dlq)

        app.deploy(skip_infra=True, skip_handlers=True, skip_backend=True)

        post_alert_custom_metric = get_response(
            "alerts-deploy",
            "post-v2-projects-goblet-metrics_1.json",
        )

        assert (
            post_alert_custom_metric["body"]["metricDescriptor"]["type"]
            == "logging.googleapis.com/user/alerts-test-custom"
        )

        post_alert_metric = get_response(
            "alerts-deploy",
            "post-v3-projects-goblet-alertPolicies_1.json",
        )
        assert post_alert_metric["body"]["displayName"] == "alerts-test-metric"
        post_alert_log = get_response(
            "alerts-deploy",
            "post-v3-projects-goblet-alertPolicies_2.json",
        )
        assert post_alert_log["body"]["displayName"] == "alerts-test-error"
        post_alert_custom = get_response(
            "alerts-deploy",
            "post-v3-projects-goblet-alertPolicies_3.json",
        )
        assert post_alert_custom["body"]["displayName"] == "alerts-test-custom"

        post_alert_dlq = get_response(
            "alerts-deploy",
            "post-v3-projects-goblet-alertPolicies_4.json",
        )
        assert (
            post_alert_dlq["body"]["displayName"]
            == "alerts-test-subscription-dlq-alert"
        )

        assert get_replay_count() == 6

    def test_destroy_alerts(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "alerts-destroy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        reset_replay_count()

        app = Goblet(function_name="alerts-test")

        metric_alert = BackendAlert(
            "metric",
            conditions=[
                MetricCondition(
                    "test",
                    metric="cloudfunctions.googleapis.com/function/execution_count",
                    value=10,
                )
            ],
        )
        log_alert = BackendAlert(
            "error",
            conditions=[LogMatchCondition("error", "severity>=ERROR")],
        )
        custom_alert = BackendAlert(
            "custom",
            conditions=[
                CustomMetricCondition(
                    "custom",
                    metric_filter="severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)",
                    value=10,
                )
            ],
        )

        app.alert(metric_alert)
        app.alert(log_alert)
        app.alert(custom_alert)

        app.destroy()

        assert get_replay_count() == 6

    def test_sync_alerts(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "alerts-sync")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="alerts-test")

        custom_alert = BackendAlert(
            "custom",
            conditions=[
                CustomMetricCondition(
                    "custom",
                    metric_filter="severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)",
                    value=10,
                )
            ],
        )
        app.alert(custom_alert)

        app.alerts._gcp_deployed_alerts = {}
        app.alerts.checked_alerts = True
        app.alerts.sync()

        responses = get_responses("alerts-sync")
        alerts = get_response(
            "alerts-sync",
            "get-v3-projects-goblet-alertPolicies_1.json",
        )

        assert len(responses) - 1 == alerts["body"]["totalSize"] - len(
            app.alerts.resources
        )

from goblet import Goblet
from goblet.infrastructures.alerts import (
    MetricCondition,
    LogMatchCondition,
    CustomMetricCondition,
)
from goblet.backends import CloudFunctionV1

from goblet.test_utils import get_responses, get_response


class TestAlerts:
    def test_add_alert(self):
        app = Goblet(function_name="goblet_example")

        app.alert(
            "metric",
            conditions=[
                MetricCondition(
                    "test",
                    metric="cloudfunctions.googleapis.com/function/execution_count",
                    value=10,
                )
            ],
        )
        app.alert("error", conditions=[LogMatchCondition("error", "severity>=ERROR")])
        app.alert(
            "custom",
            conditions=[
                CustomMetricCondition(
                    "custom",
                    metric_filter="severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)",
                    value=10,
                )
            ],
        )

        jobs = app.infrastructure["alerts"]
        assert len(jobs.alerts) == 3

    def test_format_filter_or_query(self):
        condition = MetricCondition(
            "test",
            metric="cloudfunctions.googleapis.com/function/execution_count",
            value=10,
        )
        condition.format_filter_or_query(
            "test",
            CloudFunctionV1.monitoring_type,
            "name",
            CloudFunctionV1.monitoring_label_key,
        )
        assert (
            condition.filter
            == 'resource.type="cloud_function" AND resource.labels.function_name="name" AND metric.type = "cloudfunctions.googleapis.com/function/execution_count"'
        )

    def test_deploy_alerts(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "alerts-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="alerts-test")

        app.alert(
            "metric",
            conditions=[
                MetricCondition(
                    "metric",
                    metric="cloudfunctions.googleapis.com/function/execution_count",
                    value=10,
                )
            ],
        )
        app.alert("error", conditions=[LogMatchCondition("error", "severity>=ERROR")])
        app.alert(
            "custom",
            conditions=[
                CustomMetricCondition(
                    "custom",
                    metric_filter="severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)",
                    value=10,
                )
            ],
        )

        app.deploy(skip_backend=True)

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

    def test_destroy_alerts(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "alerts-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="alerts-test")

        app.alert(
            "metric",
            conditions=[
                MetricCondition(
                    "metric",
                    metric="cloudfunctions.googleapis.com/function/execution_count",
                    value=10,
                )
            ],
        )
        app.alert("error", conditions=[LogMatchCondition("error", "severity>=ERROR")])
        app.alert(
            "custom",
            conditions=[
                CustomMetricCondition(
                    "custom",
                    metric_filter="severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)",
                    value=10,
                )
            ],
        )

        app.destroy()

        responses = get_responses("alerts-destroy")

        assert len(responses) == 6

    def test_sync_alerts(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "alerts-sync")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="alerts-test")

        app.alert(
            "custom",
            conditions=[
                CustomMetricCondition(
                    "custom",
                    metric_filter="severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)",
                    value=10,
                )
            ],
        )

        app.infrastructure["alerts"].sync()

        responses = get_responses("alerts-sync")
        alerts = get_response(
            "alerts-sync",
            "get-v3-projects-goblet-alertPolicies_1.json",
        )

        assert len(responses) - 1 == alerts["body"]["totalSize"] - len(
            app.infrastructure["alerts"].resources
        )

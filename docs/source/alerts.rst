.. _alerts:

======
Alerts
======

You can deploy alerts related to your application in several ways, which creates GCP monitoring alerts behind the scenes. 

You can create allerts for the backend by using the `@alert` decorator and by passing in a `BackendAlert`. Several resources also 
support alerts and these are pass in directly to the resource when creating it.

Each alert takes a name and a list of conditions. Notification channels
can be added to the `alerts.notification_channel` key in `config.json` or explicity in the alert. The base `AlertCondition` class allows you to 
fully customize your alert based on the fields privided by the `GCP Alert Resource <https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies#conditionhttps://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies#condition>`_

If you do not need a fully customized alert you can use the built in classes for `MetricCondition`, `LogMatchCondition`, and `CustomMetricCondition`. These come with 
defaults in terms of duration and aggregations, but can be overriden as needed. The `CustomMetricCondition` creates a custom metric based on the filter provided and then 
creates an alert using that metric.  

For `LogMatchCondition` you can completely replace the filter if necessary by setting the `replace_filter` flag to True. 

.. code:: python

    from goblet.alerts.alert_conditions import MetricCondition,LogMatchCondition,CustomMetricCondition
    from goblet.alerts.alerts import BackendAlert
    app = Goblet()
    
    # Example Metric Alert for the cloudfunction metric execution_count with a threshold of 10
    metric_alert = BackendAlert(
        "metric",
        conditions=[
            MetricCondition(
                "test",
                metric="cloudfunctions.googleapis.com/function/execution_count",
                value=10
            )
        ],
    )
    app.alert(metric_alert)

    # Example Metric Alert for the cloudfunction metric execution_times with a custom aggregation
    metric_alert_2 = BackendAlert(
        "metric",
        conditions=[
            MetricCondition(
                "test",
                metric="cloudfunctions.googleapis.com/function/execution_times",
                value=1000,
                aggregations=[
                    {
                        "alignmentPeriod": "300s",
                        "crossSeriesReducer": "REDUCE_NONE",
                        "perSeriesAligner": "ALIGN_PERCENTILE_50",
                    }
                ],
            )
        ],
    )
    app.alert(metric_alert_2)

    # Example Log Match metric that will trigger an incendent off of any Error logs
    log_alert = BackendAlert(
        "error",
        conditions=[LogMatchCondition("error", "severity>=ERROR")],
    )
    app.alert(log_alert)

    # Example Metric Alert that creates a custom metric for severe errors with http code in the 500's and creates an alert with a threshold of 10
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

`PubSubDLQCondition` is a special case of `MetricCondition` that will create an alert for `pubsub.googleapis.com/subscription/dead_letter_message_count` on a subscription.

.. code:: python

    from goblet.alerts import PubSubDLQAlert, PubSubDLQCondition

    # Pubsub Subscription with DLQ and alert
    # Triggered by pubsub topic. Simulates failure to trigger DLQ
    @app.pubsub_subscription(
        "goblet-created-test-topic",
        dlq=True,
        dlq_alerts=[
            PubSubDLQAlert(
                "pubsubdlq",
                conditions=[
                    PubSubDLQCondition(
                        "pubsublq-condition"
                    )
                ],
            )
        ]
    )
    def failed_subscription(data):
        raise Exception("Simulating failure")

You can also create an alert for an Uptime check 

.. code:: python

    from goblet.alerts import UptimeAlert, UptimeCondition

    # Example uptime check with alert
    @app.uptime(timeout="30s",alerts=[UptimeAlert("uptime", conditions=[UptimeCondition("uptime")])])
    def uptime_check_with_alert():
        app.log.info("success")
        return "success"
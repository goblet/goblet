from goblet import Goblet
from goblet_gcp_client import get_responses, get_response
from goblet.infrastructures.bq_spark_stored_procedure import (
    BigQuerySparkStoredProcedure,
)


class TestBqSparkStoredProcedure:
    def test_register_bqsparkstoredprocedure(self, monkeypatch):
        app = Goblet(function_name="bqsparkstoredprocedure_test")
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us")

        test_dataset_id = "blogs"

        def spark_handler():
            pass

        app.bqsparkstoredprocedure(
            name="test_spark_stored_procedure",
            dataset_id=test_dataset_id,
            func=spark_handler,
        )

        resources = app.infrastructure["bqsparkstoredprocedure"].resources[
            "test_spark_stored_procedure"
        ]

        expected_resources = {
            "routine_name": "test_spark_stored_procedure",
            "dataset_id": test_dataset_id,
            "func": BigQuerySparkStoredProcedure.stringify_func(spark_handler),
            "location": "us",
            "runtime_version": "1.1",
            "spark_file": None,
            "local_code": True,
            "container_image": None,
            "additional_python_files": None,
            "additional_files": None,
            "properties": None,
        }

        for key, value in resources.items():
            assert expected_resources.get(key) == value

    def test_deploy_bqsparkstoredprocedure(self, monkeypatch):
        test_deploy_name = "bqsparkstoredprocedure-deploy"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us")
        monkeypatch.setenv("G_TEST_NAME", test_deploy_name)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        test_name = "bqsparkstoredprocedure_test"
        procedure_name = "test_spark_stored_procedure"
        app = Goblet(function_name=test_name)
        test_dataset_id = "blogs"

        def spark_handler():
            pass

        app.bqsparkstoredprocedure(
            name=procedure_name,
            dataset_id=test_dataset_id,
            func=spark_handler,
        )

        app.deploy(skip_backend=True)
        responses = get_responses(test_deploy_name)
        assert len(responses) > 0

        connection_response = get_response(
            test_deploy_name, "post-v1-projects-goblet-locations-us-connections_1.json"
        )
        assert (
            connection_response["body"]["name"]
            == f"projects/goblet/locations/us/connections/{test_name}"
        )
        assert "spark" in connection_response["body"]

        routine_response = get_response(
            test_deploy_name,
            "post-bigquery-v2-projects-goblet-datasets-blogs-routines_1.json",
        )
        assert (
            routine_response["body"]["routineReference"]["routineId"] == procedure_name
        )
        assert (
            routine_response["body"]["routineReference"]["datasetId"] == test_dataset_id
        )
        assert (
            routine_response["body"]["sparkOptions"]["connection"]
            == connection_response["body"]["name"]
        )

    def test_destroy_bqsparkstoredprocedure(self, monkeypatch):
        test_deploy_name = "bqsparkstoredprocedure-destroy"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us")
        monkeypatch.setenv("G_TEST_NAME", test_deploy_name)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        test_name = "bqsparkstoredprocedure_test"
        app = Goblet(function_name=test_name)
        test_dataset_id = "blogs"

        def spark_handler():
            pass

        app.bqsparkstoredprocedure(
            name="test_spark_stored_procedure",
            dataset_id=test_dataset_id,
            func=spark_handler,
        )

        app.destroy(skip_backend=True)
        responses = get_responses(test_deploy_name)

        assert len(responses) != 0

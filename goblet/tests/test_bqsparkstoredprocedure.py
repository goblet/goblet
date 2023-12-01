import os
from goblet import Goblet
from goblet_gcp_client import (
    get_responses,
    get_response,
    reset_replay_count,
    get_replay_count,
)
from goblet.infrastructures.bq_spark_stored_procedure import (
    BigQuerySparkStoredProcedure,
)


class TestBqSparkStoredProcedure:
    def test_register_bqsparkstoredprocedure(self, monkeypatch):
        app = Goblet(function_name="bqsparkstoredprocedure_test")
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us")
        reset_replay_count()

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

        assert 0 == get_replay_count()

    def test_deploy_bqsparkstoredprocedure(self, monkeypatch):
        test_deploy_name = "bqsparkstoredprocedure-deploy"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us")
        monkeypatch.setenv("G_TEST_NAME", test_deploy_name)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        reset_replay_count()

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
        assert 3 == get_replay_count()

    def test_destroy_bqsparkstoredprocedure(self, monkeypatch):
        test_deploy_name = "bqsparkstoredprocedure-destroy"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us")
        monkeypatch.setenv("G_TEST_NAME", test_deploy_name)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        reset_replay_count()

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
        assert 3 == get_replay_count()

    def test_deploy_bqsparkstoredprocedure_remote_code(self, monkeypatch):
        test_name = "bqsparkstoredprocedure-remote-deploy"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us")
        monkeypatch.setenv("G_TEST_NAME", test_name)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        reset_replay_count()

        procedure_name = "test_spark_stored_procedure"
        app = Goblet(function_name=test_name)
        test_dataset_id = "blogs"

        with open("spark.py", "w") as f:
            f.write(
                """
                def main():
                    print("Hello World!")
                """
            )
        app.bqsparkstoredprocedure(
            name=procedure_name,
            dataset_id=test_dataset_id,
            spark_file="spark.py",
        )

        app.deploy(skip_backend=True)
        responses = get_responses(test_name)
        assert len(responses) > 0

        connection_response = get_response(
            test_name, "post-v1-projects-goblet-locations-us-connections_1.json"
        )
        assert (
            connection_response["body"]["name"]
            == f"projects/goblet/locations/us/connections/{test_name}"
        )
        assert "spark" in connection_response["body"]

        routine_response = get_response(
            test_name,
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
        assert (
            routine_response["body"]["sparkOptions"]["mainFileUri"]
            == f"gs://{test_name}/spark.py"
        )
        assert 5 == get_replay_count()
        os.remove("spark.py")

    def test_destroy_bqsparkstoredprocedure_remote_code(self, monkeypatch):
        test_deploy_name = "bqsparkstoredprocedure-remote-deploy-destroy"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us")
        monkeypatch.setenv("G_TEST_NAME", test_deploy_name)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        reset_replay_count()

        test_name = "bqsparkstoredprocedure-remote-deploy"
        procedure_name = "test_spark_stored_procedure"
        app = Goblet(function_name=test_name)
        test_dataset_id = "blogs"

        app.bqsparkstoredprocedure(
            name=procedure_name,
            dataset_id=test_dataset_id,
            spark_file="spark.py",
        )

        app.destroy(skip_backend=True)
        responses = get_responses(test_deploy_name)

        assert len(responses) != 0
        assert 6 == get_replay_count()

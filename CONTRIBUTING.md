# Goblet Contributions

## Running locally

clone repo `git clone git@github.com:goblet/goblet.git`
install local version in your env by `pip install -e .`


If you are running into issues running tests make sure to set your pythonpath. 

```export PYTHONPATH=$(pwd)```

## Writing Tests

* When mocking tests that interact with GCP you will notice the following env vars set. 

```python
monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
monkeypatch.setenv("GOBLET_TEST_NAME", "job-destroy")
monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")
```

When writing your own tests you will need to set `GOOGLE_PROJECT` to the project you are testing in. `GOBLET_TEST_NAME` should correspond to a new folder that you created under `/tests/data/http/NEW_FOLDER`. Finally you should change `GOBLET_HTTP_TEST` to `RECORD`. After running the test, make sure to reset envs.

* You can run tests by calling `make coverage`

## Lint

run `make lint` to run default linter.
run `black goblet` to format all files correctly
SPHINXBUILD = sphinx-build

default: html

html:
	cd docs && make html

pypi:
	python3 -m build;
	twine upload --skip-existing dist/*;

lint:
	flake8 goblet

format:
	black goblet

coverage:
	export G_HTTP_TEST=REPLAY
	export G_TEST_DATA_DIR=$PWD/goblet/tests/data/http
	export G_MOCK_CREDENTIALS=True
	export G_TEST_PROJECT_ID="goblet"
	coverage run -m pytest goblet/tests;
	coverage report -m --include="goblet/*" --omit="goblet/tests/*";

tests:
	pytest goblet/tests;

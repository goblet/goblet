SPHINXBUILD = sphinx-build

default: html

html:
	cd docs && make html

pypi:
	python3 setup.py sdist bdist_wheel;
	twine upload --skip-existing dist/*;

lint:
	flake8 goblet

coverage:
	export G_HTTP_TEST=REPLAY
	export G_TEST_DATA_DIR=$PWD/goblet/tests/data/http
	export G_MOCK_CREDENTIALS=True
	export G_TEST_PROJECT_ID="goblet"
	coverage run -m pytest goblet/tests;
	coverage report -m --include="goblet/*" --omit="goblet/tests/*";

tests:
	pytest goblet/tests;

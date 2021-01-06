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
	coverage run -m pytest goblet/tests;
	coverage report -m --include="goblet/*" --omit="goblet/tests/*";
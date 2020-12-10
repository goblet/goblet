SPHINXBUILD = sphinx-build

default: html

html:
	cd docs && make html

pypi:
	python3 setup.py sdist bdist_wheel;
	twine upload --skip-existing dist/*;

VERSION := $(shell head -n 1 nextcode/VERSION)

LAST_BUILD = $(shell ls -Art dist/ | tail -n 1)

.PHONY: test cover cover-html build release black docs-setup docs-build

test:
	python3 -m pytest tests/

cover:
	python3 -m pytest tests/ --cov=nextcode/ --disable-warnings --junitxml=test-results/pytest.xml

cover-html:
	python3 -m pytest tests/ --cov=nextcode/ --disable-warnings --junitxml=test-results/pytest.xml --cov-report=html

build:
	python3 setup.py sdist

release:
	twine upload --repository-url=https://upload.pypi.org/legacy/ dist/${LAST_BUILD} -u '${BUILD_USER}' -p '${BUILD_PASS}'

black:
	black --exclude="venv|.tox" .

dev-install:
	pip3 install -r requirements.txt

docs-setup:
	pip3 install -r doc/requirements.txt

docs-build:
	sphinx-build -b html doc docs
	git commit -m "Documentation update for ${VERSION}" -- docs

clean:
	rm -rf dist/
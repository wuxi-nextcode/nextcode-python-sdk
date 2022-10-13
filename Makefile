#VERSION := $(shell head -n 1 nextcode/VERSION)

.PHONY: test cover cover-html build release black docs-setup docs-build

test:
	python3 -m pytest tests/

cover:
	python3 -m pytest tests/ --cov=nextcode/ --disable-warnings --junitxml=test-results/pytest.xml

cover-html:
	python3 -m pytest tests/ --cov=nextcode/ --disable-warnings --junitxml=test-results/pytest.xml --cov-report=html

build:
	poetry build

release:
	poetry publish --build

black:
	black --exclude="venv|.tox" .

dev-install:
	poetry install --all-extras --with test

docs-setup:
	pip3 install -r doc/requirements.txt

#docs-build:
#	sphinx-build -b html doc docs
#	git commit -m "Documentation update for ${VERSION}" -- docs

clean:
	rm -rf dist/ nextcode_sdk.egg-info/ test-results/ .coverage
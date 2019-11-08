VERSION := $(shell head -n 1 nextcode/VERSION)

LAST_BUILD = $(shell ls -Art dist/ | tail -n 1)

.PHONY: test cover cover-html build bump release quickrelease scan tag black

test:
	python3 -m pytest tests/

cover:
	python3 -m pytest tests/ --cov=nextcode/ --disable-warnings --junitxml=test-results/pytest.xml

cover-html:
	python3 -m pytest tests/ --cov=nextcode/ --disable-warnings --junitxml=test-results/pytest.xml --cov-report=html

build:
	python3 setup.py sdist

bump:
	python3 setup.py bump

release:
	twine upload --repository-url=https://upload.pypi.org/legacy/ dist/${LAST_BUILD} -u '${BUILD_USER}' -p '${BUILD_PASS}'

quickrelease: bump build release

scan:
	python3 -m pylint -E nextcode/
	mypy nextcode/ --ignore-missing-imports

tag:
	git tag ${VERSION}
	git push origin ${VERSION}

black:
	black --exclude="venv|.tox" .

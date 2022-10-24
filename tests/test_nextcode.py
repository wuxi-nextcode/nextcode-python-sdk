import shutil
import unittest
import tempfile
import responses
from asserts import *
from pathlib import Path
from os import environ as env
from nextcode import Nextcode
from unittest.mock import patch
from nextcode.exceptions import InvalidProfile
from nextcode.services.query.exceptions import QueryError
from nextcode.services.phenotype.exceptions import PhenotypeError
from tests import BaseTestCase, REFRESH_TOKEN, AUTH_RESP, AUTH_URL, cfg
from nextcode import config

WORKFLOW_URL = "https://test.wuxinextcode.com/workflow"
PIPELINES_URL = WORKFLOW_URL + '/pipelines'
QUERYSERVER_URL = "https://test.wuxinextcode.com/queryserver"
QUERY_URL = "https://test.wuxinextcode.com/api/query"
PHENOTYPE_URL = "https://test.wuxinextcode.com/api/phenotype-catalog"
QUERIES_URL = QUERYSERVER_URL + '/query'
QUERY_ROOT_RSP = {
    "endpoints": {
        "templates": QUERY_URL + '/templates',
        "queries": QUERY_URL + '/query',
        "wakeup": QUERY_URL + '/wakeup',
        "health": QUERY_URL + '/health'
    },
    "current_user": {"email": "testuser"},
}
QUERYSERVER_ROOT_RSP = {
    'current_user': '{"name":"Logi Leifsson","email":"logi@genuitysci.com"}',
    'build_info': {
        'version': '12.5.0-SNAPSHOT (git SHA 94a04889)',
        'gor_version': '4.4.0 (git SHA f652ee3448ec)'
    },
    'endpoints': {
        'dev': 'https://test.wuxinextcode.com/queryserver/dev',
        'openapi': 'https://test.wuxinextcode.com/queryserver/openapi',
        'query': 'https://test.wuxinextcode.com/queryserver/query',
        'swagger-ui': 'https://test.wuxinextcode.com/queryserver/swagger-ui',
        'health': 'https://test.wuxinextcode.com/queryserver/health',
        'status': 'https://test.wuxinextcode.com/queryserver/status',
        'wakeup': 'https://test.wuxinextcode.com/api/query/wakeup/'
    },
    'service_name': 'QueryServer'
}
WORKFLOW_ROOT_RESP = {
    "endpoints": {
        "health": WORKFLOW_URL + "/health",
        "documentation": WORKFLOW_URL + "/documentation",
        "jobs": WORKFLOW_URL + '/jobs',
        "pipelines": WORKFLOW_URL + '/pipelines',
        "projects": WORKFLOW_URL + '/projects',
    },
    "build_info": {
        "version": "0.0.0-dev"
    },
    "app_info": {
        'db_host': 'localhost',
        'db_name': 'gorkube_workflowservice',
        'db_version': 'ccb966f29862',
        'debug': True,
        'development': True,
        'host': 'dpm-workflow-667f49c84d-jmdjp',
        'nextflow_image': 'nextcode/nextflowexecutor:3.0.0',
        'version': '6.0.0-snapshot.4043c4de'
    },
    "current_user": {"email": "testuser"},
}
PIPELINES_RESP = {
    "pipelines": [
        {
            "description": "Smoketest pipeline which is run without parameters to check if the service and dependencies is valid",
            "links": {
                "self": "https://platform-cluster.wuxinextcodedev.com/workflow/pipelines/smoketest"
            },
            "name": "smoketest",
            "parameters": None,
            "revision": None,
            "script": "https://gitlab.com/wuxi-nextcode/cohort/workflows/workflow-smoketest.git",
            "storage_type": "shared",
        }
    ]
}
TEMPLATES_CATEGORIES_URL = QUERY_URL + "/templates/wxnc/"
TEMPLATES_TEMPLATES_URL = TEMPLATES_CATEGORIES_URL + "system/"
TEMPLATES_ORGANIZATIONS_RESP = {
    "organizations": [{"links": {"self": TEMPLATES_CATEGORIES_URL}}]
}
TEMPLATES_CATEGORIES_RESP = {
    "categories": [{"links": {"self": TEMPLATES_TEMPLATES_URL}}]
}
TEMPLATES_TEMPLATES_RESP = {
    "templates": [{"name": "dummy", "full_name": "wxnc/system/dummy"}]
}
PHENOTYPE_ROOT_RSP = {
    "build_info": {
        "branch": "master",
        "build_timestamp": "2020-03-03 14:26:03 +0000",
        "commit": "cdca2116",
        "version": "1.4.6",
    },
    "endpoints": {
        "root": PHENOTYPE_URL,
        "health": PHENOTYPE_URL + "/health",
        "documentation": PHENOTYPE_URL + "/documentation",
        "projects": PHENOTYPE_URL + '/projects',
        "tags": PHENOTYPE_URL + "/tags",
        "get_phenotype_matrix": PHENOTYPE_URL + "/projects/{project_name}/get_phenotype_matrix"
    },
    "service_name": "phenotype-catalog",
}
PROJECTS_URL = PHENOTYPE_URL + "/projects"
PROJECT_RESP = {
    "name": 'dummy',
    "links": {
        "self": PROJECTS_URL + "/dummy",
        "phenotypes": f"{PROJECTS_URL}/dummy/phenotypes",
        "download": PROJECTS_URL + f"/dummy/phenotypes/download",
        "get_phenotype_matrix": PROJECTS_URL + f"/dummy/get_phenotype_matrix",
    },
}
PROJECTS_RESP = {"projects": [PROJECT_RESP]}
PHENOTYPE_RESP = {
    "project_key": 'dummy',
    "name": "string",
    "description": "string",
    "result_type": "SET",
    "created_at": "2020-03-05T12:35:01.323Z",
    "updated_at": "2020-03-05T12:35:01.323Z",
    "created_by": "string",
    "tag_list": ["string"],
    "versions": [
        {
            "version": 0,
            "count": 0,
            "created_at": "2020-03-05T12:35:01.323Z",
            "created_by": "string",
        }
    ],
    "links": {
        "self": f"{PROJECTS_URL}/dummy/phenotypes/test-pheno",
        "upload": f"{PROJECTS_URL}/dummy/phenotypes/test-pheno/upload",
    },
}

class TestNextcode(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        config.root_config_folder = Path(self.temp_dir)
        self.config = config.Config()
        config._init_config()
        # Remove env variables because you cannot trust
        # other tests to clean up after themselves
        env.pop('GOR_API_KEY', None)
        env.pop('NEXTCODE_PROFILE', None)
        env.pop('NEXTCODE_ACCESS_TOKEN', None)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)


    def test_no_profile_no_api_key(self):
        with assert_raises(InvalidProfile):
            nc = Nextcode()

    def test_profile_not_found(self):
        with assert_raises(InvalidProfile):
            nc = Nextcode(profile='dummy')

    def test_profile(self):
        config.create_profile("dummy", REFRESH_TOKEN)
        nc = Nextcode(profile='dummy')
        assert_equal(nc.client.profile.profile_name, 'dummy')

    def test_default_profile(self):
        config.create_profile("dummy", REFRESH_TOKEN)
        config.set_default_profile("dummy")
        nc = Nextcode()
        assert_equal(nc.client.profile.profile_name, 'dummy')

    def test_profile_from_env_no_profile(self):
        env['NEXTCODE_PROFILE'] = 'dummy'
        with assert_raises(InvalidProfile):
            nc = Nextcode()

    def test_profile_from_env(self):
        env['NEXTCODE_PROFILE'] = 'dummy'
        config.create_profile("dummy", REFRESH_TOKEN)
        nc = Nextcode()

    @responses.activate
    def test_basic(self):
        responses.post(AUTH_URL, json=AUTH_RESP)
        nc = Nextcode(api_key=REFRESH_TOKEN)
        responses.get(
            'https://test.wuxinextcode.com/phenoteke/api/v1',
            status=200,
            json={'root': None}
        )
        phenoteke_status = nc.phenoteke.status()
        assert_equal(phenoteke_status, {'root': None})
        responses.get(
            PHENOTYPE_URL,
            status=200,
            json={'root': None}
        )
        phenotype_status = nc.phenotype.status()
        assert_equal(phenotype_status, {'root': None})
        responses.get(
            'https://test.wuxinextcode.com/pipelines-service',
            status=200,
            json={'root': None}
        )
        pipelines_status = nc.pipelines.status()
        assert_equal(pipelines_status, {'root': None})
        responses.get(
            QUERY_URL, status=200, json={'root': None}
        )
        query_status = nc.query.status()
        assert_equal(query_status, {'root': None})
        responses.get(
            QUERYSERVER_URL,
            status=200,
            json={'root': None}
        )
        queryserver_status = nc.queryserver.status()
        assert_equal(queryserver_status, {'root': None})
        responses.get(
            WORKFLOW_URL,
            status=200,
            json={'root': None}
        )
        workflow_status = nc.workflow.status()
        assert_equal(workflow_status, {'root': None})

    @responses.activate
    def test_phenoteke(self):
        # To be added later... perhaps
        pass

    @responses.activate
    def test_phenotype(self):
        nc = Nextcode(api_key=REFRESH_TOKEN, project='dummy')
        responses.post(AUTH_URL, json=AUTH_RESP)
        responses.get(PHENOTYPE_URL, status=200, json=PHENOTYPE_ROOT_RSP)
        responses.get(PHENOTYPE_URL + '/health', status=200, json={})
        healthy = nc.phenotype.healthy()
        assert_equal(healthy, True)
        responses.get(
            PHENOTYPE_URL + '/projects',
            status=200,
            json=PROJECTS_RESP

        )
        response = {"phenotypes": [PHENOTYPE_RESP]}
        responses.get(
            PHENOTYPE_URL + f"/projects/dummy/phenotypes",
            json=response
        )
        phenotypes = nc.phenotype.get_phenotypes()
        assert_equal(phenotypes[0].data['project_key'], 'dummy')

    @responses.activate
    def test_phenotype_no_project(self):
        nc = Nextcode(api_key=REFRESH_TOKEN)
        responses.post(AUTH_URL, json=AUTH_RESP)
        responses.get(PHENOTYPE_URL, status=200, json=PHENOTYPE_ROOT_RSP)
        with assert_raises(PhenotypeError):
            phenotypes = nc.phenotype.get_phenotypes()

    @responses.activate
    def test_pipelines(self):
        # To be added later... perhaps
        pass

    @responses.activate
    def test_query(self):
        nc = Nextcode(api_key=REFRESH_TOKEN)
        responses.post(AUTH_URL, json=AUTH_RESP)
        responses.get(QUERY_URL, status=200, json=QUERY_ROOT_RSP)
        responses.get(QUERY_URL + '/health', status=200, json={})
        healthy = nc.query.healthy()
        assert_equal(healthy, True)
        responses.get(
            QUERY_URL + '/templates',
            json=TEMPLATES_ORGANIZATIONS_RESP,
        )
        responses.get(
            TEMPLATES_CATEGORIES_URL,
            json=TEMPLATES_CATEGORIES_RESP
        )
        responses.get(
            TEMPLATES_TEMPLATES_URL,
            json=TEMPLATES_TEMPLATES_RESP
        )
        templates = nc.query.get_templates()
        expected_templates = {
            'wxnc/system/dummy': {
                'name': 'dummy',
                'full_name': 'wxnc/system/dummy'
            }
        }
        assert_equal(templates, expected_templates)

    @responses.activate
    def test_queryserver(self):
        nc = Nextcode(api_key=REFRESH_TOKEN, project='dummy')
        responses.post(AUTH_URL, json=AUTH_RESP)
        responses.get(QUERYSERVER_URL, status=200, json=QUERYSERVER_ROOT_RSP)
        responses.get(QUERYSERVER_URL + '/health', status=200, json={})
        healthy = nc.queryserver.healthy()
        assert_equal(healthy, True)
        status = nc.queryserver.status()
        assert_equal(
            status['build_info']['version'],
            '12.5.0-SNAPSHOT (git SHA 94a04889)'
        )
        service_name = nc.queryserver.service_name
        assert_equal(service_name, 'QueryServer')
        ret = 'Chrom\tpos\treference\tallele\trsids\nchr1\t10020\tAA\tA\trs775809821'
        responses.post(QUERIES_URL, body=ret)
        result = nc.queryserver.execute("gor ref/dbsnp.gorz | top 1")
        assert_equal(result.text(), ret)

    @responses.activate
    def test_queryserver_no_project(self):
        nc = Nextcode(api_key=REFRESH_TOKEN)
        responses.post(AUTH_URL, json=AUTH_RESP)
        responses.get(QUERYSERVER_URL, status=200, json=QUERYSERVER_ROOT_RSP)
        responses.get(QUERYSERVER_URL + '/health', status=200, json={})
        responses.post(QUERIES_URL, body='bla')
        with assert_raises(QueryError):
            result = nc.queryserver.execute("gor ref/dbsnp.gorz | top 1")

    @responses.activate
    def test_workflow(self):
        nc = Nextcode(api_key=REFRESH_TOKEN)
        responses.post(AUTH_URL, json=AUTH_RESP)
        responses.get(
            WORKFLOW_URL,
            status=200,
            json=WORKFLOW_ROOT_RESP
        )
        responses.get(WORKFLOW_URL + "/health", status=200, json={})
        responses.get(WORKFLOW_URL + "/documentation", json={})
        assert_equal(nc.workflow.healthy(), True)
        expected_status = {
            'build_info': {
                'version': '0.0.0-dev'
            },
            'root': None
        }
        assert_equal(
            nc.workflow.status()['build_info']['version'],
            '0.0.0-dev'
        )
        assert_equal(nc.workflow.service_name, 'workflow')
        assert_equal(nc.workflow.version, '0.0.0-dev')
        assert_equal(nc.workflow.build_info, {'version': '0.0.0-dev'})
        assert_equal(nc.workflow.app_info, WORKFLOW_ROOT_RESP['app_info'])
        assert_equal(nc.workflow.current_user, {"email": "testuser"})
        assert_equal(nc.workflow.endpoints, WORKFLOW_ROOT_RESP['endpoints'])
        assert_equal(nc.workflow.openapi_spec(), {})
        responses.get(PIPELINES_URL, json=PIPELINES_RESP)
        pipelines = nc.workflow.get_pipelines()
        assert_equal(pipelines, PIPELINES_RESP['pipelines'])

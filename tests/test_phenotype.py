import responses
from unittest import mock
import datetime
from copy import deepcopy

from nextcode import Client
from nextcode.exceptions import ServerError
from nextcode.services.phenotype.exceptions import PhenotypeError
from tests import BaseTestCase, REFRESH_TOKEN, AUTH_RESP, AUTH_URL

dt = datetime.datetime.utcnow().isoformat()

PHENOTYPE_URL = "https://test.wuxinextcode.com/api/phenotype-catalog"
ROOT_RESP = {
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
    },
    "service_name": "phenotype-catalog",
}

PHENOTYPE_RESP = {
    "project_key": "string",
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
}

PROJECT = "test-project"
PHENOTYPE_NAME = "test-pheno"


class PhenotypeTest(BaseTestCase):
    def setUp(self):
        super(PhenotypeTest, self).setUp()
        self.svc = self.get_service()

    @responses.activate
    def get_service(self):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, PHENOTYPE_URL, json=ROOT_RESP)

        client = Client(api_key=REFRESH_TOKEN)
        svc = client.service("phenotype")
        return svc

    @responses.activate
    def test_status(self):
        _ = self.svc.status()

    @responses.activate
    def test_basic(self):
        svc = self.svc
        responses.add(responses.GET, PHENOTYPE_URL + "/documentation", json={})
        ret = svc.openapi_spec()

        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.GET, PHENOTYPE_URL + "/health")
            ret = svc.healthy()
            self.assertTrue(ret)

        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.GET, PHENOTYPE_URL + "/health", status=404)
            ret = svc.healthy()
            self.assertFalse(ret)

    @responses.activate
    def test_get_phenotypes(self):
        ret = {"phenotypes": [PHENOTYPE_RESP]}
        responses.add(
            responses.GET, PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes", json=ret
        )
        phenotypes = self.svc.get_phenotypes(PROJECT)
        self.assertEqual(phenotypes, [PHENOTYPE_RESP])

        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.GET,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}",
            json=ret,
        )
        phenotype = self.svc.get_phenotype(PROJECT, PHENOTYPE_NAME)
        self.assertEqual(phenotype, PHENOTYPE_RESP)

    @responses.activate
    def test_create_phenotype(self):
        result_type = "SET"
        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.POST, PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes", json=ret
        )
        phenotype = self.svc.create_phenotype(PROJECT, PHENOTYPE_NAME, result_type)
        self.assertEqual(phenotype, PHENOTYPE_RESP)

        with self.assertRaises(PhenotypeError) as ctx:
            self.svc.create_phenotype(PROJECT, PHENOTYPE_NAME, "invalid")
        self.assertIn("not supported", repr(ctx.exception))

        # TODO: Add tests for server errors

    @responses.activate
    def test_delete_phenotype(self):
        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.DELETE,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}",
        )
        phenotype = self.svc.delete_phenotype(PROJECT, PHENOTYPE_NAME)

    @responses.activate
    def test_upload(self):
        ret = {"a": "b"}
        responses.add(
            responses.POST,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}/upload",
            json=ret,
        )
        result = self.svc.upload(PROJECT, PHENOTYPE_NAME, ["something"])
        self.assertEqual(ret, result)

    @responses.activate
    def test_download(self):
        phenotypes = ["a", "b"]
        phenotypes_txt = ",".join(phenotypes)
        ret = "a\nb\rc\td"
        responses.add(
            responses.GET,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/download",
            body=ret,
        )
        result = self.svc.download(PROJECT, ["something"])
        self.assertEqual(ret, result)

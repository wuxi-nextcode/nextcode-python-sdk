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
PROJECTS_URL = PHENOTYPE_URL + "/projects"

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
        "projects": PROJECTS_URL,
        "tags": PHENOTYPE_URL + "/tags",
        "get_phenotype_matrix": PROJECTS_URL + "/{project_name}/get_phenotype_matrix"
    },
    "service_name": "phenotype-catalog",
}

PLAYLIST_ID = "1"
PROJECT = "test-project"
PHENOTYPE_NAME = "test-pheno"
PHENOTYPE_RESP = {
    "project_key": PROJECT,
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
        "self": f"{PROJECTS_URL}/{PROJECT}/phenotypes/{PHENOTYPE_NAME}",
        "upload": f"{PROJECTS_URL}/{PROJECT}/phenotypes/{PHENOTYPE_NAME}/upload",
    },
}

AC_RECIPE_PARAMETERS = {
    "freeze": 'mr-freeze',
    "inheritance_model": "Additive",
    "regression_model": "GLM_FIRTH",
    "genome_range": "All",
    "dimension_reduction": "Standardize_variance",
    "hide_covar_specific_results": "Yes",
    "variant_rate_threshold": "0.1",
    "hwe_threshold": "1.0E-50",
    "maf_threshold": "0.01",
    "snp_qc_threshold": "",
    "indel_qc_threshold": "",
    "variant_blacklist_file": "",
    "segment_blacklist_file": "",
    "ref_path": "ref",
    "treat_warnings_as_error": "Yes",
    "max_run_time": "12",
    "project_name": PROJECT,
}
ANALYSIS_CATALOG_RESP = {
    "project_key": "string",
    "name": "string",
    "recipe_name": "string",
    "recipe_parameters": AC_RECIPE_PARAMETERS,
    "analysis_catalog_items": [],
    "excluded_pns": [],
    "runs": [],
    "created_at": "2020-03-05T12:35:01.323Z",
    "updated_at": "2020-03-05T12:35:01.323Z",
    "created_by": "string",
}

ANALYSIS_CATALOG_RUN_RESP = {
    "project_key": "string",
    "name": "string",
    "state": "string",
    "created_at": "2020-03-05T12:35:01.323Z",
    "updated_at": "2020-03-05T12:35:01.323Z",
    "ended_at": "2020-03-05T12:35:01.323Z",
    "links": {
        "self": PROJECTS_URL + f"/{PROJECT}/analysis_catalogs/acname/runs/acrunname",
    },
}

PROJECT_RESP = {
    "name": PROJECT,
    "links": {
        "self": PROJECTS_URL + f"/{PROJECT}",
        "phenotypes": f"{PROJECTS_URL}/{PROJECT}/phenotypes",
        "download": PROJECTS_URL + f"/{PROJECT}/phenotypes/download",
        "get_phenotype_matrix": PROJECTS_URL + f"/{PROJECT}/get_phenotype_matrix",
    },
}

PROJECTS_RESP = {"projects": [PROJECT_RESP]}


class PhenotypeTest(BaseTestCase):
    def setUp(self):
        super(PhenotypeTest, self).setUp()
        self.svc = self.get_service()

    @responses.activate
    def get_service(self):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, PHENOTYPE_URL, json=ROOT_RESP)
        responses.add(responses.GET, PROJECTS_URL, json=PROJECTS_RESP)

        client = Client(api_key=REFRESH_TOKEN)
        svc = client.service("phenotype", project=PROJECT)
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
        phenotypes = self.svc.get_phenotypes()
        self.assertEqual([p.data for p in phenotypes], [PHENOTYPE_RESP])

        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.GET,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}",
            json=ret,
        )
        phenotype = self.svc.get_phenotype(PHENOTYPE_NAME)
        self.assertEqual(phenotype.data, PHENOTYPE_RESP)

        responses.add(
            responses.GET,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/not_exists",
            json={"code": 404},
            status=404,
        )
        with self.assertRaises(PhenotypeError) as ctx:
            _ = self.svc.get_phenotype("not_exists")
        self.assertIn("Phenotype not found", repr(ctx.exception))

    @responses.activate
    def test_create_phenotype(self):
        result_type = "SET"
        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.POST, PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes", json=ret
        )
        phenotype = self.svc.create_phenotype(PHENOTYPE_NAME, result_type)
        self.assertEqual(phenotype.data, PHENOTYPE_RESP)

        with self.assertRaises(PhenotypeError) as ctx:
            self.svc.create_phenotype(PHENOTYPE_NAME, "invalid")
        self.assertIn("not supported", repr(ctx.exception))

        # TODO: Add tests for server errors

    @responses.activate
    def test_update_phenotype(self):
        result_type = "SET"
        
        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.POST, PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes", json=ret
        )
        phenotype = self.svc.create_phenotype(PHENOTYPE_NAME, result_type)

        UPDATED_RESP = PHENOTYPE_RESP
        UPDATED_RESP["description"] = "UPDATED DESCRIPTION"
        ret_updated = {"phenotype": UPDATED_RESP}

        responses.add(
            responses.PATCH,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}"
        )
        responses.add(
            responses.GET,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}",
            json=ret_updated,
        )
        
        phenotype.update(description="UPDATED DESCRIPTION")
        self.assertEqual(phenotype.data, UPDATED_RESP)


    @responses.activate
    def test_delete_phenotype(self):
        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.DELETE,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}",
        )
        result_type = "SET"
        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.POST, PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes", json=ret
        )
        phenotype = self.svc.create_phenotype(PHENOTYPE_NAME, result_type)

        phenotype.delete()

    @responses.activate
    def test_upload(self):
        result_type = "SET"
        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.POST, PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes", json=ret
        )
        phenotype = self.svc.create_phenotype(PHENOTYPE_NAME, result_type)

        ret = {"a": "b"}
        responses.add(
            responses.POST,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}/upload",
            json=ret,
        )
        result = phenotype.upload(["something"])
        self.assertEqual(ret, result)

        with self.assertRaises(TypeError):
            _ = phenotype.upload("invalid")

    @responses.activate
    def test_phenotype_get_data(self):
        result_type = "SET"
        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.POST, PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes", json=ret
        )
        phenotype = self.svc.create_phenotype(PHENOTYPE_NAME, result_type)

        ret = "pn\tblu\nc\td"
        responses.add(
            responses.POST,
            PHENOTYPE_URL + f"/projects/{PROJECT}/get_phenotype_matrix", body=ret,
        )
        df = phenotype.get_data()
        self.assertIn("blu", df.to_string())

    @responses.activate
    def test_attributes(self):
        result_type = "SET"
        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.POST, PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes", json=ret
        )
        phenotype = self.svc.create_phenotype(PHENOTYPE_NAME, result_type)

        for k, v in PHENOTYPE_RESP.items():
            attr_val = getattr(phenotype, k)
            if k.endswith("_at"):
                self.assertTrue(isinstance(attr_val, datetime.datetime))
            else:
                self.assertEqual(v, attr_val)

        with self.assertRaises(AttributeError):
            _ = phenotype.not_exists

        self.assertTrue(repr(phenotype).startswith("<"))

    @responses.activate
    def test_tags(self):
        result_type = "SET"
        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.POST, PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes", json=ret
        )
        phenotype = self.svc.create_phenotype(PHENOTYPE_NAME, result_type)

        responses.add(
            responses.PATCH,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}",
            json=ret,
        )

        ret = {"phenotype": PHENOTYPE_RESP}
        responses.add(
            responses.GET,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}",
            json=ret,
        )

        phenotype.add_tag("test")
        with self.assertRaises(PhenotypeError):
            phenotype.delete_tag("test")
        phenotype.data["tag_list"].append("test")
        phenotype.delete_tag("test")
        phenotype.set_tags(["test", "test2"])

    @responses.activate
    def test_phenotype_matrix(self):
        matrix = self.svc.get_phenotype_matrix(base="test_base")
        matrix.add_phenotype("pheno1", missing_value="missing1", label="label")
        self.assertIn("pheno1", matrix.phenotypes)
        matrix.remove_phenotype("pheno1")
        matrix.remove_phenotype("unknown")
        self.assertEqual(matrix.phenotypes, {})
        matrix.add_phenotypes(["pheno2", "pheno3"], missing_value="missing23")
        self.assertIn("pheno2", matrix.phenotypes)
        self.assertIn("pheno3", matrix.phenotypes)

        ret = "pn\tblu\nc\td"
        responses.add(
            responses.POST,
            PHENOTYPE_URL + f"/projects/{PROJECT}/get_phenotype_matrix",
            body=ret,
        )
        df = matrix.get_data()
        self.assertIn("blu", df.to_string())

    @responses.activate
    def test_create_analysis_catalog(self):
        playlist = PLAYLIST_ID
        name = "acname"
        recipe_name = "plink-regression"
        recipe_parameters = AC_RECIPE_PARAMETERS
        covariate_phenotypes = ["pheno1", "pheno2"]
        ret = {"analysis_catalog": ANALYSIS_CATALOG_RESP}
        responses.add(
            responses.POST,
            PROJECTS_URL + f"/{PROJECT}/playlists/{PLAYLIST_ID}/analysis_catalogs",
            json=ret
        )
        analysis_catalog = self.svc.create_analysis_catalog(
            playlist,
            name,
            recipe_name,
            recipe_parameters,
            covariate_phenotypes
        )
        self.assertEqual(analysis_catalog.data, ANALYSIS_CATALOG_RESP)

    @responses.activate
    def test_get_analysis_catalog_run(self):
        analysis_catalog_name = "acname"
        analysis_catalog_run_name = "acrunname"

        ret = {"analysis_catalog_run": ANALYSIS_CATALOG_RUN_RESP}
        responses.add(
            responses.GET,
            PROJECTS_URL + f"/{PROJECT}/analysis_catalogs/{analysis_catalog_name}/runs/{analysis_catalog_run_name}",
            json=ret
        )
        analysis_catalog_run = self.svc.get_analysis_catalog_run(analysis_catalog_name, analysis_catalog_run_name)
        self.assertEqual(analysis_catalog_run.data, ANALYSIS_CATALOG_RUN_RESP)

    @responses.activate
    def test_get_analysis_catalog_runs(self):
        ret = {"analysis_catalog_runs": [ANALYSIS_CATALOG_RUN_RESP]}

        responses.add(
            responses.GET,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}/analysis_catalog_runs",
            json=ret,
        )
        analysis_catalog_runs = self.svc.get_analysis_catalog_runs(PHENOTYPE_NAME)
        self.assertEqual([ac.data for ac in analysis_catalog_runs], [ANALYSIS_CATALOG_RUN_RESP])

    @responses.activate
    def test_get_analysis_catalogs(self):
        ret = {"analysis_catalogs": [ANALYSIS_CATALOG_RESP]}
        responses.add(
            responses.GET, PROJECTS_URL + f"/{PROJECT}/analysis_catalogs", json=ret
        )
        analysis_catalogs = self.svc.get_analysis_catalogs()
        self.assertEqual([ac.data for ac in analysis_catalogs], [ANALYSIS_CATALOG_RESP])

        responses.add(
            responses.GET,
            PHENOTYPE_URL + f"/projects/{PROJECT}/phenotypes/{PHENOTYPE_NAME}/analysis_catalogs",
            json=ret,
        )
        analysis_catalogs = self.svc.get_analysis_catalogs(PHENOTYPE_NAME)
        self.assertEqual([ac.data for ac in analysis_catalogs], [ANALYSIS_CATALOG_RESP])

    @responses.activate
    def test_get_analysis_catalog(self):
        analysis_catalog_name = "acname"

        ret = {"analysis_catalog": ANALYSIS_CATALOG_RESP}
        responses.add(
            responses.GET, PROJECTS_URL + f"/{PROJECT}/analysis_catalogs/{analysis_catalog_name}", json=ret
        )

        analysis_catalog = self.svc.get_analysis_catalog(analysis_catalog_name)
        self.assertEqual(analysis_catalog.data, ANALYSIS_CATALOG_RESP)

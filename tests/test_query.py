import responses
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
import json
import os
from copy import deepcopy
import tempfile
from urllib3.exceptions import MaxRetryError

from nextcode.exceptions import InvalidToken, InvalidProfile, ServerError
from nextcode.utils import decode_token, jupyter_available
from nextcode.client import Client
from nextcode.services.query.query import _log_download_progress

from tests import BaseTestCase, REFRESH_TOKEN, ACCESS_TOKEN, AUTH_URL, AUTH_RESP
from nextcode.services.query.exceptions import (
    QueryError,
    MissingRelations,
    TemplateError,
)

ROOT_URL = "https://test.wuxinextcode.com/api/query"
WAKEUP_URL = ROOT_URL + "/wakeup/"
QUERIES_URL = ROOT_URL + "/query/"
TEMPLATES_ORGANIZATIONS_URL = ROOT_URL + "/templates/"
TEMPLATES_CATEGORIES_URL = TEMPLATES_ORGANIZATIONS_URL + "wxnc/"
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

ROOT_RESP = {
    "endpoints": {
        "templates": TEMPLATES_ORGANIZATIONS_URL,
        "queries": QUERIES_URL,
        "wakeup": WAKEUP_URL,
    },
    "current_user": {"email": "testuser"},
}

DATA_PATH = Path(os.path.join(os.path.dirname(__file__), "data"))
QUERY_RESPONSE = json.load(Path(DATA_PATH, "query_response.json").open())
TEMPLATE_RESPONSE = json.load(Path(DATA_PATH, "template_response.json").open())
TEMPLATE_FILE_PATH = Path(DATA_PATH, "template.ftl.yml")
EXECUTE_TEMPLATE_RESPONSE = json.load(
    Path(DATA_PATH, "execute_template_response.json").open()
)


class QueryTest(BaseTestCase):
    def setUp(self):
        super(QueryTest, self).setUp()
        self.svc = self.get_service(project="testproject")

    def test_jupyter(self):
        b = jupyter_available()

    @responses.activate
    def get_service(self, project=None):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, ROOT_URL, json=ROOT_RESP)

        client = Client(api_key=REFRESH_TOKEN)
        svc = client.service("query", project=project)
        return svc

    @responses.activate
    def test_query_status(self):
        _ = self.svc.status()

    def test_check_project(self):
        self.svc._check_project()
        svc = self.get_service()
        with self.assertRaises(QueryError):
            svc._check_project()

    @responses.activate
    def test_get_templates(self):
        responses.add(
            responses.GET,
            TEMPLATES_ORGANIZATIONS_URL,
            json=TEMPLATES_ORGANIZATIONS_RESP,
        )
        responses.add(
            responses.GET, TEMPLATES_CATEGORIES_URL, json=TEMPLATES_CATEGORIES_RESP
        )
        responses.add(
            responses.GET, TEMPLATES_TEMPLATES_URL, json=TEMPLATES_TEMPLATES_RESP
        )
        templates = self.svc.get_templates()
        first_template = templates[next(iter(templates))]
        self.assertEqual(
            [t["full_name"] for t in TEMPLATES_TEMPLATES_RESP["templates"]],
            list(templates.keys()),
        )

        templates = self.svc.get_templates(organization="wxnc")
        templates = self.svc.get_templates(organization="wxnc", category="system")
        responses.add(
            responses.GET, TEMPLATES_CATEGORIES_URL + "doesnotexist/", status=404
        )
        templates = self.svc.get_templates(organization="wxnc", category="doesnotexist")

        with responses.RequestsMock() as rsps:
            url = TEMPLATES_ORGANIZATIONS_URL + first_template["full_name"]
            rsps.add(responses.GET, url, json=first_template)
            template = self.svc.get_template(first_template["full_name"])

        with responses.RequestsMock() as rsps:
            url = TEMPLATES_ORGANIZATIONS_URL + first_template["full_name"]
            rsps.add(responses.GET, url, status=404)
            with self.assertRaises(TemplateError):
                template = self.svc.get_template(first_template["full_name"])

    def test_set_project(self):
        self.svc.set_project("dummy")
        self.svc.set_project("dummy", persist=False)

    @responses.activate
    def test_add_template_from_file(self):
        with self.assertRaises(TemplateError):
            self.svc.add_template_from_file(filename="doesnotextist.yml")

        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            with self.assertRaises(TemplateError) as ex:
                self.svc.add_template_from_file(filename=f.name)
            self.assertIn("File contents is not a dictionary", str(ex.exception))

            f.write(
                """---
            invalid:
            yaml
            """
            )
            f.close()
            with self.assertRaises(TemplateError) as ex:
                self.svc.add_template_from_file(filename=f.name)
            self.assertIn("Yaml is invalid", str(ex.exception))

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                TEMPLATES_ORGANIZATIONS_URL,
                json={"full_name": "dummy", "id": 1234},
            )
            self.svc.add_template_from_file(filename=TEMPLATE_FILE_PATH)

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, TEMPLATES_ORGANIZATIONS_URL, status=400)
            with self.assertRaises(TemplateError):
                self.svc.add_template_from_file(filename=TEMPLATE_FILE_PATH)

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                TEMPLATES_ORGANIZATIONS_URL,
                status=409,
                json={
                    "code": 409,
                    "error": {"template_id": 111, "template_url": "dummy"},
                },
            )
            with self.assertRaises(TemplateError):
                self.svc.add_template_from_file(filename=TEMPLATE_FILE_PATH)

        with responses.RequestsMock() as rsps:
            template_url = "https://dummy"
            rsps.add(responses.DELETE, template_url)
            rsps.add(
                responses.POST,
                TEMPLATES_ORGANIZATIONS_URL,
                status=409,
                json={
                    "code": 409,
                    "error": {"template_id": 111, "template_url": template_url},
                },
            )
            with self.assertRaises(TemplateError):
                self.svc.add_template_from_file(
                    filename=TEMPLATE_FILE_PATH, replace=True
                )

    @responses.activate
    def test_delete_template(self):
        name = "org/cat/name/1.0.0"
        template_url = "https://dummy"
        resp = {"links": {"self": template_url}}
        responses.add(responses.GET, TEMPLATES_ORGANIZATIONS_URL + name, json=resp)
        responses.add(responses.DELETE, template_url, json=resp)
        self.svc.delete_template(name)

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, TEMPLATES_ORGANIZATIONS_URL + name, json=resp)
            rsps.add(responses.DELETE, template_url, status=400)
            with self.assertRaises(TemplateError):
                self.svc.delete_template(name)

    @responses.activate
    def test_render_template(self):
        name = "org/cat/name/1.0.0"
        template_url = "https://dummy"
        render_url = "https://dummy/render"
        resp = {"links": {"self": template_url, "render": render_url}}
        responses.add(responses.GET, TEMPLATES_ORGANIZATIONS_URL + name, json=resp)
        responses.add(responses.GET, render_url, body="hello")
        self.svc.render_template(name)

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, TEMPLATES_ORGANIZATIONS_URL + name, json=resp)
            rsps.add(responses.GET, render_url, status=404)
            with self.assertRaises(ServerError):
                self.svc.render_template(name)

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, TEMPLATES_ORGANIZATIONS_URL + name, json=resp)
            rsps.add(responses.GET, render_url, status=400, body="Missing arguments")
            with self.assertRaises(TemplateError):
                self.svc.render_template(name)

    @responses.activate
    def test_basic_execute(self):
        ret = QUERY_RESPONSE
        responses.add(responses.POST, QUERIES_URL, json=ret)
        query = self.svc.execute("gor #dbsnp#;")
        self.assertEqual("DONE", query.status)
        self.assertIn("<GorQuery", repr(query))
        self.assertTrue(query.done)

    @responses.activate
    def test_done(self):
        ret = deepcopy(QUERY_RESPONSE)
        with responses.RequestsMock() as rsps:
            ret["status"] = "RUNNING"
            rsps.add(responses.POST, QUERIES_URL, json=ret)
            rsps.add(responses.GET, QUERIES_URL + "1371", json=ret)
            query = self.svc.execute("gor #dbsnp#;", nowait=True)
            self.assertFalse(query.done)

        with responses.RequestsMock() as rsps:
            ret["status"] = "DONE"
            rsps.add(responses.GET, QUERIES_URL + "1371", json=ret)
            self.assertTrue(query.done)
            self.assertTrue(query.done)

    @responses.activate
    def test_failed(self):
        ret = deepcopy(QUERY_RESPONSE)
        with responses.RequestsMock() as rsps:
            ret["status"] = "RUNNING"
            rsps.add(responses.POST, QUERIES_URL, json=ret)
            rsps.add(responses.GET, QUERIES_URL + "1371", json=ret)
            query = self.svc.execute("gor #dbsnp#;", nowait=True)
            self.assertFalse(query.failed)

        with responses.RequestsMock() as rsps:
            ret["status"] = "FAILED"
            rsps.add(responses.GET, QUERIES_URL + "1371", json=ret)
            self.assertTrue(query.failed)
            self.assertTrue(query.failed)

    @responses.activate
    def test_execute_template(self):
        template_name = "wxnc/system/test_template"

        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(
                responses.GET,
                TEMPLATES_ORGANIZATIONS_URL + template_name,
                json=TEMPLATE_RESPONSE,
            )
            rsps.add(
                responses.GET,
                EXECUTE_TEMPLATE_RESPONSE["links"]["self"],
                json=EXECUTE_TEMPLATE_RESPONSE,
            )
            rsps.add(
                responses.POST,
                TEMPLATE_RESPONSE["links"]["execute"],
                json=EXECUTE_TEMPLATE_RESPONSE,
            )
            query = self.svc.execute_template(template_name)
            self.assertEqual("DONE", query.status)
            self.assertIn("<GorQuery 666", repr(query))

        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(
                responses.GET,
                TEMPLATES_ORGANIZATIONS_URL + template_name,
                json=TEMPLATE_RESPONSE,
            )
            rsps.add(
                responses.GET,
                EXECUTE_TEMPLATE_RESPONSE["links"]["self"],
                json=EXECUTE_TEMPLATE_RESPONSE,
            )
            rsps.add(responses.POST, TEMPLATE_RESPONSE["links"]["execute"], status=404)
            with self.assertRaises(ServerError):
                query = self.svc.execute_template(template_name)

    @responses.activate
    def test_virtual_relations(self):
        ret = QUERY_RESPONSE

        responses.add(responses.POST, QUERIES_URL, json=ret)
        self.svc.execute(
            "gor #dbsnp#;", relations=[{"name": "file", "data": "somedata"}]
        )
        self.svc.execute("gor #dbsnp#;", name="file")

        import pandas as pd

        self.svc.execute(
            "gor #dbsnp#;", relations=[{"name": "file", "data": pd.DataFrame()}]
        )

        with self.assertRaises(QueryError):
            self.svc.execute("gor #dbsnp#;", relations=[{"name": "file", "data": []}])

        with self.assertRaises(QueryError):
            self.svc.execute(
                "gor #dbsnp#;", relations=[{"invalid": "file", "data": []}]
            )

    @responses.activate
    def test_missing_virtual_relations(self):
        responses.add(
            responses.POST,
            QUERIES_URL,
            json={
                "code": 409,
                "error": {"virtual_relations": [{"name": "missingrelation"}]},
            },
            status=409,
        )
        with self.assertRaises(MissingRelations):
            self.svc.execute("gor #dbsnp#;", name="file")

    @responses.activate
    def test_server_error(self):
        responses.add(responses.POST, QUERIES_URL, status=404)
        with self.assertRaises(ServerError):
            self.svc.execute("gor #dbsnp#;", name="file")

    @responses.activate
    def test_get_queries(self):
        responses.add(responses.GET, QUERIES_URL, json={"queries": [QUERY_RESPONSE]})
        queries = self.svc.get_queries()
        self.assertEqual(1, len(queries))
        self.assertEqual(QUERY_RESPONSE["query_id"], queries[0].query_id)

        responses.add(
            responses.GET, QUERY_RESPONSE["links"]["self"], json=QUERY_RESPONSE
        )
        query = self.svc.get_query(QUERY_RESPONSE["query_id"])
        for k in QUERY_RESPONSE.keys():
            self.assertTrue(hasattr(query, k))

        query.refresh()
        with self.assertRaises(AttributeError):
            query.notfound

        responses.add(
            responses.GET, ROOT_URL + "/query/999", json={"code": 404}, status=404
        )
        with self.assertRaises(QueryError):
            query = self.svc.get_query(999)

        responses.add(
            responses.GET, ROOT_URL + "/query/888", json={"code": 500}, status=500
        )
        with self.assertRaises(MaxRetryError):
            query = self.svc.get_query(888)

    @responses.activate
    def test_get_results(self):
        responses.add(responses.GET, QUERIES_URL, json={"queries": [QUERY_RESPONSE]})
        queries = self.svc.get_queries()
        self.assertEqual(1, len(queries))
        self.assertEqual(QUERY_RESPONSE["query_id"], queries[0].query_id)

        responses.add(
            responses.GET, QUERY_RESPONSE["links"]["self"], json=QUERY_RESPONSE
        )
        query = self.svc.get_query(QUERY_RESPONSE["query_id"])
        for k in QUERY_RESPONSE.keys():
            self.assertTrue(hasattr(query, k))

        RESULT_RESPONSE = {"header": ["col1", "col2"], "data": [[1, 2], [3, 4]]}
        responses.add(
            responses.GET, QUERY_RESPONSE["links"]["result"], json=RESULT_RESPONSE
        )
        query.get_results(limit=199)

        setattr(query, "available", False)
        with self.assertRaises(QueryError) as ctx:
            query.get_results()
        self.assertIn("not available", str(ctx.exception))

        setattr(query, "status", "PENDING")
        with self.assertRaises(QueryError) as ctx:
            query.get_results()
        self.assertIn("is PENDING", str(ctx.exception))

    @responses.activate
    def test_wait(self):
        responses.add(
            responses.GET, QUERY_RESPONSE["links"]["self"], json=QUERY_RESPONSE
        )
        query = self.svc.get_query(QUERY_RESPONSE["query_id"])

        def mock_running():
            return True

        time_count = 0

        def mock_time():
            nonlocal time_count
            time_count += 1
            if time_count > 2:
                return 100
            else:
                return 0

        with patch("nextcode.services.query.query.time.sleep"), patch(
            "nextcode.services.query.query.time.time", mock_time
        ), patch(
            "nextcode.services.query.query.Query.running", new_callable=PropertyMock
        ) as mock_running:
            with self.assertRaises(QueryError):
                mock_running.return_value = True
                query.wait(max_seconds=1)

        time_count = 0

        def mock_time():
            nonlocal time_count
            time_count += 1
            if time_count > 3:
                return 100
            else:
                return 0

        def mock_running():
            if time_count > 2:
                return False
            return True

        with patch("nextcode.services.query.query.time.sleep"), patch(
            "nextcode.services.query.query.time.time", mock_time
        ), patch(
            "nextcode.services.query.query.Query.running", new_callable=mock_running
        ):
            with self.assertRaises(QueryError):
                query.wait(max_seconds=1)

        time_count = 0
        setattr(query, "status", "PENDING")
        with patch("nextcode.services.query.query.time.sleep"), patch(
            "nextcode.services.query.query.time.time", mock_time
        ):
            query.wait(max_seconds=1)

    @responses.activate
    def test_cancel(self):
        responses.add(
            responses.GET, QUERY_RESPONSE["links"]["self"], json=QUERY_RESPONSE
        )
        query = self.svc.get_query(QUERY_RESPONSE["query_id"])
        with self.assertRaises(QueryError) as ex:
            query.cancel()
        responses.add(responses.DELETE, QUERY_RESPONSE["links"]["self"])
        setattr(query, "status", "RUNNING")
        query.cancel()

    @responses.activate
    def test_dataframe(self):
        responses.add(
            responses.GET, QUERY_RESPONSE["links"]["self"], json=QUERY_RESPONSE
        )
        query = self.svc.get_query(QUERY_RESPONSE["query_id"])
        RESULT_RESPONSE = {"header": ["col1", "col2"], "data": [[1, 2], [3, 4]]}
        responses.add(
            responses.GET, QUERY_RESPONSE["links"]["result"], json=RESULT_RESPONSE
        )
        df = query.dataframe()
        with patch(
            "nextcode.services.query.query.jupyter_available", return_value=False
        ):
            with self.assertRaises(QueryError) as ctx:
                query.dataframe()
            self.assertIn("Pandas library is not installed", str(ctx.exception))

        def mock_get_results(**kw):
            return []

        setattr(query, "get_results", mock_get_results)
        df = query.dataframe()
        self.assertEqual([], df.index.to_list())

    @responses.activate
    def test_wakeup(self):
        responses.add(responses.POST, WAKEUP_URL, json={"success": True})
        self.svc.wakeup()

    def test_log_download_progress(self):
        _log_download_progress(1000, 2, 3, 4, 5, 6)

    @responses.activate
    def test_perspectives(self):
        responses.add(
            responses.GET, QUERY_RESPONSE["links"]["self"], json=QUERY_RESPONSE
        )
        query = self.svc.get_query(QUERY_RESPONSE["query_id"])
        _ = query.perspectives

    @responses.activate
    def test_download_results(self):
        responses.add(
            responses.GET, QUERY_RESPONSE["links"]["self"], json=QUERY_RESPONSE
        )
        query = self.svc.get_query(QUERY_RESPONSE["query_id"])
        filename = "/tmp/out.tsv"
        del query.links["streamresults"]
        with self.assertRaises(Exception):
            _ = query.download_results(filename)

        query = self.svc.get_query(QUERY_RESPONSE["query_id"])
        filename = "/tmp/out.tsv"
        responses.add(responses.GET, QUERY_RESPONSE["links"]["streamresults"], json={})
        _ = query.download_results(filename)

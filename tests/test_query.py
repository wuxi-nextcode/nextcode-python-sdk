from unittest import TestCase
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
import tempfile
import shutil
import datetime
import json
import os
import time

from nextcode import config, Client
from nextcode.exceptions import InvalidToken, InvalidProfile, ServerError
from nextcode.utils import decode_token
from nextcode.client import Client
from nextcode.services.query import Service
from nextcode.services.query.utils import jupyter_available
from tests import BaseTestCase, REFRESH_TOKEN, ACCESS_TOKEN, AUTH_URL, AUTH_RESP
from nextcode.services.query.exceptions import QueryError, MissingRelations

QUERY_URL = "https://test.wuxinextcode.com/api/query"
QUERY_QUERY_URL = QUERY_URL + "/query/"
TEMPLATES_ORGANIZATIONS_URL = QUERY_URL + "/templates/"
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
    "endpoints": {"templates": TEMPLATES_ORGANIZATIONS_URL, "queries": QUERY_QUERY_URL},
    "current_user": {"email": "testuser"},
}

DATA_PATH = Path(os.path.join(os.path.dirname(__file__), "data"))
QUERY_RESPONSE = json.load(Path(DATA_PATH, "query_response.json").open())
TEMPLATE_RESPONSE = json.load(Path(DATA_PATH, "template_response.json").open())
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
        responses.add(responses.GET, QUERY_URL, json=ROOT_RESP)

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

    @responses.activate
    def test_basic_execute(self):
        ret = QUERY_RESPONSE
        responses.add(responses.POST, QUERY_QUERY_URL, json=ret)
        query = self.svc.execute("gor #dbsnp#;")
        self.assertEqual("DONE", query.status)
        self.assertIn("<GorQuery", repr(query))

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

        responses.add(responses.POST, QUERY_QUERY_URL, json=ret)
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
            QUERY_QUERY_URL,
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
        responses.add(responses.POST, QUERY_QUERY_URL, status=404)
        with self.assertRaises(ServerError):
            self.svc.execute("gor #dbsnp#;", name="file")

    @responses.activate
    def test_get_queries(self):
        responses.add(
            responses.GET, QUERY_QUERY_URL, json={"queries": [QUERY_RESPONSE]}
        )
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
            responses.GET, QUERY_URL + "/query/999", json={"code": 404}, status=404
        )
        with self.assertRaises(QueryError):
            query = self.svc.get_query(999)

        responses.add(
            responses.GET, QUERY_URL + "/query/888", json={"code": 500}, status=500
        )
        with self.assertRaises(QueryError):
            query = self.svc.get_query(888)

    @responses.activate
    def test_get_results(self):
        responses.add(
            responses.GET, QUERY_QUERY_URL, json={"queries": [QUERY_RESPONSE]}
        )
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

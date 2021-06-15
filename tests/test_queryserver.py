import responses
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
import json
import os

from nextcode.exceptions import InvalidToken, InvalidProfile, ServerError
from nextcode.services.queryserver.result import _log_download_progress
from nextcode.utils import decode_token, jupyter_available
from nextcode.client import Client

from tests import BaseTestCase, REFRESH_TOKEN, ACCESS_TOKEN, AUTH_URL, AUTH_RESP
from nextcode.services.query.exceptions import (
    QueryError,
    MissingRelations,
    TemplateError,
)

ROOT_URL = "https://test.wuxinextcode.com/queryserver"
QUERIES_URL = ROOT_URL + "/query/"

ROOT_RESP = {
    "endpoints": {
        "query": QUERIES_URL,
        "status": ROOT_URL + "status"
    },
    "current_user": {"email": "testuser"},
}

DATA_PATH = Path(os.path.join(os.path.dirname(__file__), "data"))

TEMPLATE_RESPONSE = json.load(Path(DATA_PATH, "template_response.json").open())
TEMPLATE_FILE_PATH = Path(DATA_PATH, "template.ftl.yml")
EXECUTE_TEMPLATE_RESPONSE = json.load(
    Path(DATA_PATH, "execute_template_response.json").open()
)


class QueryServerTest(BaseTestCase):
    def setUp(self):
        super(QueryServerTest, self).setUp()
        self.svc = self.get_service(project="testproject")

    def test_jupyter(self):
        b = jupyter_available()

    @responses.activate
    def get_service(self, project=None):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, ROOT_URL, json=ROOT_RESP)

        client = Client(api_key=REFRESH_TOKEN)
        svc = client.service("queryserver", project=project)
        return svc

    @responses.activate
    def test_queryserver_status(self):
        _ = self.svc.status()

    def test_check_project(self):
        self.svc._check_project()
        svc = self.get_service()
        with self.assertRaises(QueryError):
            svc._check_project()

    def test_set_project(self):
        self.svc.set_project("dummy")
        self.svc.set_project("dummy", persist=False)

    @responses.activate
    def test_basic_execute(self):
        ret = 'Chrom\tpos\treference\tallele\trsids\nchr1\t10020\tAA\tA\trs775809821'
        responses.add(responses.POST, QUERIES_URL, body=ret)

        result = self.svc.execute("gor ref/dbsnp.gorz | top 1")
        self.assertEqual(ret, result.text())

        result = self.svc.execute("gor ref/dbsnp.gorz | top 1")
        self.assertEqual(ret, result.lines())

    @responses.activate
    def test_unicode_execute(self):
        ret = 'RowNum\ts\n0\táíþæð\n'
        responses.add(responses.POST, QUERIES_URL, body=ret)
        result = self.svc.execute("norrows 1 | calc s 'áíþæð'")
        self.assertEqual(ret, result.text())

    @responses.activate
    def test_iterator_execute(self):
        ret = 'Chrom\tpos\treference\tallele\trsids\nchr1\t10020\tAA\tA\trs775809821'
        responses.add(responses.POST, QUERIES_URL, body=ret)
        result = self.svc.execute("gor ref/dbsnp.gorz | top 1")
        result_text: str = ""
        for line in result.iter_lines():
            if len(result_text) > 0:
                result_text += '\n'
            result_text += line

        self.assertEqual(1, result.num_lines)
        self.assertEqual(59, result.num_bytes)
        self.assertEqual(ret, result_text)

    @responses.activate
    def test_dataframe(self):
        ret = 'Chrom\tpos\treference\tallele\trsids\nchr1\t10020\tAA\tA\trs775809821'
        responses.add(responses.POST, QUERIES_URL, body=ret)
        result = self.svc.execute("gor ref/dbsnp.gorz | top 1")
        df = result.dataframe()
        self.assertSequenceEqual(ret.rstrip().split('\n')[0].split('\t'), df.columns.array)
        self.assertSequenceEqual(ret.rstrip().split('\n')[1].split('\t'), [str(l) for l in df.values[0]])

        with patch("nextcode.services.queryserver.result.jupyter_available", return_value=False):
            with self.assertRaises(QueryError) as ctx:
                result = self.svc.execute("gor ref/dbsnp.gorz | top 1")
                result.dataframe()
            self.assertIn("Pandas library is not installed", str(ctx.exception))

    @responses.activate
    def test_server_error(self):
        ret = '#> EXCEPTION {"errorType":"GorException", "message":"Error"}'
        responses.add(responses.POST, QUERIES_URL, body=ret, status=400)
        with self.assertRaisesRegex(ServerError, "Error"):
            self.svc.execute("gor x")

    @responses.activate
    def test_server_error_message(self):
        ret = '#> EXCEPTION {"errorType":"GorException", "message":"Error","command":"gor x"}'
        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, QUERIES_URL, body=ret, status=403)

            try:
                self.svc.execute("gor x")
                self.fail("Should throw exception")
            except ServerError as ex:
                self.assertEqual(ex.message, "GorException in command: gor x\nError")

    @responses.activate
    def test_cancel(self):
        ret = 'Chrom\tpos\treference\tallele\trsids\nchr1\t10020\tAA\tA\trs775809821'
        responses.add(responses.POST, QUERIES_URL, body=ret)
        result = self.svc.execute("gor ref/dbsnp.gorz | top 1")
        result.cancel()

    @responses.activate
    def test_virtual_relations(self):
        data = 'Chrom\tpos\treference\tallele\trsids\nchr1\t10020\tAA\tA\trs775809821'

        ret = data

        responses.add(responses.POST, QUERIES_URL, body=ret)
        self.svc.execute("gor [file]]", relations=[{"name": "file", "data": data}])

        import pandas as pd
        self.svc.execute("gor [file]", relations=[{"name": "file", "data": pd.DataFrame()}])

        with self.assertRaises(QueryError):
            self.svc.execute("gor [file]", relations=[{"name": "file", "data": []}])

        with self.assertRaises(QueryError):
            self.svc.execute("gor [file]", relations=[{"invalid": "file", "data": []}])

    @responses.activate
    def test_missing_virtual_relations(self):
        responses.add(
            responses.POST,
            QUERIES_URL,
            body='#> EXCEPTION {"errorType":"GorMissingRelationException", "uri":"[some:relation]","message":"Missing Relation ...."}',
            status=409,
        )
        with self.assertRaises(MissingRelations):
            self.svc.execute("gor [some:relation]", name="file")

    def test_log_download_progress(self):
        _log_download_progress(1000, 2, 3, 4, 5, 6)

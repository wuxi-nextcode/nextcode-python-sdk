import os
from unittest import mock
import responses
from unittest.mock import patch, MagicMock

from nextcode import jupyter
from nextcode.exceptions import InvalidToken, InvalidProfile, ServerError
from nextcode.services.query import jupyter
from nextcode.services.query.exceptions import MissingRelations, QueryError
from tests import BaseTestCase, REFRESH_TOKEN, AUTH_RESP, AUTH_URL
from tests.test_query import QUERY_URL, ROOT_RESP
import pandas as pd


def setup_responses():
    responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
    responses.add(responses.GET, QUERY_URL, json=ROOT_RESP)


class JupyterTest(BaseTestCase):
    @responses.activate
    def setUp(self):
        super(JupyterTest, self).setUp()
        setup_responses()
        self.magics = jupyter.GorMagics()
        self.magics.shell = MagicMock()

    @responses.activate
    def test_basic_gor_magics(self):
        setup_responses()

        m = jupyter.GorMagics()
        m.handle_exception()

        os.environ["NEXTCODE_PROFILE"] = "notfound"
        with self.assertRaises(InvalidProfile):
            jupyter.get_service()

        del os.environ["NEXTCODE_PROFILE"]
        os.environ["GOR_API_KEY"] = REFRESH_TOKEN
        jupyter.get_service()

    @responses.activate
    def test_replace_vars(self):
        setup_responses()
        with self.assertRaises(Exception) as ex:
            self.magics.replace_vars("hello $not_found;")
        self.assertIn("Variable 'not_found' not found", str(ex.exception))
        self.magics.shell.user_ns = {"found": 1}
        string = self.magics.replace_vars("hello $found;")
        self.assertEqual("hello 1;", string)

    @responses.activate
    def test_load_relations(self):
        with self.assertRaises(Exception) as ex:
            _ = self.magics.load_relations(["[not_found]"])
        self.assertIn("Variable 'not_found' not found", str(ex.exception))

        self.magics.shell.user_ns = {"found": 1}
        with self.assertRaises(Exception) as ex:
            string = self.magics.load_relations(["var:found", "var:alsofound"])
        self.assertIn("found must be a pandas DataFrame object", str(ex.exception))

        from pandas import DataFrame

        self.magics.shell.user_ns = {"found": DataFrame(), "alsofound": DataFrame()}
        _ = self.magics.load_relations(["var:found", "var:alsofound"])

    def test_print_error(self):
        jupyter.print_error("test")

    def test_load_extension(self):
        setup_responses()
        m = MagicMock()
        with mock.patch("nextcode.services.query.jupyter.get_service"):
            jupyter.load_ipython_extension(m)

        with mock.patch(
            "nextcode.services.query.jupyter.get_service", side_effect=InvalidToken,
        ):
            jupyter.load_ipython_extension(m)

        with mock.patch(
            "nextcode.services.query.jupyter.get_service",
            side_effect=ServerError("Error"),
        ):
            jupyter.load_ipython_extension(m)


class GorCommandTest(JupyterTest):
    @responses.activate
    def test_singleline(self):
        setup_responses()
        df = self.magics.gor("Hello")
        self.assertTrue(df is None)

        def mock_execute(*args, **kwargs):
            m = MagicMock()
            m.status = "DONE"
            m.line_count = 100
            m.dataframe.return_value = pd.DataFrame()
            m.running.return_value = False
            return m

        m = MagicMock()
        m.execute = mock_execute
        with mock.patch("nextcode.services.query.jupyter.get_service", return_value=m):
            df = self.magics.gor("Hello")
            self.assertTrue(isinstance(df, pd.DataFrame))

    @responses.activate
    def test_not_done(self):
        setup_responses()
        df = self.magics.gor("Hello")
        self.assertTrue(df is None)

        def mock_execute(*args, **kwargs):
            m = MagicMock()
            m.status = "PENDING"
            m.line_count = 100
            m.dataframe.return_value = pd.DataFrame()
            m.error = None
            m.running.return_value = False
            return m

        m = MagicMock()
        m.execute = mock_execute
        with mock.patch("nextcode.services.query.jupyter.get_service", return_value=m):
            df = self.magics.gor("Hello")
            self.assertTrue(df is None)

    @responses.activate
    def test_multiline(self):
        setup_responses()

        def mock_execute(*args, **kwargs):
            m = MagicMock()
            m.status = "DONE"
            m.line_count = 999999999
            m.dataframe.return_value = pd.DataFrame()
            m.running.return_value = False
            return m

        m = MagicMock()
        m.execute = mock_execute
        with mock.patch("nextcode.services.query.jupyter.get_service", return_value=m):
            df = self.magics.gor("Hello", "World\nAnother world")
            self.assertTrue(isinstance(df, pd.DataFrame))

    @responses.activate
    def test_operator(self):
        setup_responses()

        def mock_execute(*args, **kwargs):
            m = MagicMock()
            m.status = "DONE"
            m.line_count = 100
            m.running.return_value = False
            return m

        m = MagicMock()
        m.execute = mock_execute
        with mock.patch("nextcode.services.query.jupyter.get_service", return_value=m):
            df = self.magics.gor("myvar <<", "gor #dbsnp#\nAnother line")
            self.assertTrue(df is None)
            dt = self.magics.gor("user_data/file.gorz <<", "gor #dbsnp#")
            self.assertTrue(df is None)

    @responses.activate
    def test_relations(self):
        setup_responses()
        m = MagicMock()
        with mock.patch("nextcode.services.query.jupyter.get_service", return_value=m):
            df = self.magics.gor("Hello")
        self.assertTrue(df is None)

        def mock_execute(*args, **kwargs):
            m = MagicMock()
            m.status = "PENDING"
            m.line_count = 100
            m.dataframe.return_value = pd.DataFrame()
            m.error = None
            m.running.return_value = False
            return m

        m = MagicMock()
        m.execute.side_effect = MissingRelations(relations=["a", "b"])
        with mock.patch("nextcode.services.query.jupyter.get_service", return_value=m):
            df = self.magics.gor("Hello")
            self.assertTrue(df is None)

    @responses.activate
    def test_keyboard_interrupt(self):
        setup_responses()
        df = self.magics.gor("Hello")
        self.assertTrue(df is None)

        def mock_execute(*args, **kwargs):
            m = MagicMock()
            m.status = "PENDING"
            m.dataframe.return_value = pd.DataFrame()
            m.error = None
            m.wait.side_effect = KeyboardInterrupt
            m.cancel.side_effect = QueryError("")
            m.running.return_value = True
            return m

        m = MagicMock()
        m.execute = mock_execute
        with patch("nextcode.services.query.jupyter.get_service", return_value=m):
            df = self.magics.gor("Hello")
            self.assertTrue(df is None)

    @responses.activate
    def test_gorls(self):
        setup_responses()

        def mock_execute(*args, **kwargs):
            m = MagicMock()
            m.status = "DONE"
            m.line_count = 100
            m.dataframe.return_value = pd.DataFrame()
            m.running.return_value = False
            m.get_results.return_value = {
                "data": [
                    ["folder", "true", 0],
                    ["file", "false", 1234512345],
                    ["file", "false", 1234512345678],
                    ["file", "false", 0],
                ]
            }
            return m

        m = MagicMock()
        m.execute = mock_execute
        with mock.patch("nextcode.services.query.jupyter.get_service", return_value=m):
            _ = self.magics.gorls(". test")

    @responses.activate
    def test_gorfind(self):
        setup_responses()

        def mock_execute(*args, **kwargs):
            m = MagicMock()
            m.status = "DONE"
            m.line_count = 100
            m.dataframe.return_value = pd.DataFrame()
            m.running.return_value = False
            m.get_results.return_value = {
                "data": [
                    ["/project/folder"],
                    ["/project/file"],
                    ["/project/file"],
                    ["/project/file"],
                ]
            }
            return m

        m = MagicMock()
        m.execute = mock_execute
        m.project = "/project/"
        with mock.patch("nextcode.services.query.jupyter.get_service", return_value=m):
            _ = self.magics.gorfind("test")

    def test_print(self):
        jupyter.print_details("dummy")
        os.environ["LOG_QUERY"] = "1"
        jupyter.print_details("dummy")
        os.environ["LOG_QUERY"] = ""

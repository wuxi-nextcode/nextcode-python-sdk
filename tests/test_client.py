from unittest import TestCase
import os
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from nextcode import config, Client
from nextcode.client import get_api_key
from nextcode.session import ServiceSession
from nextcode.exceptions import (
    InvalidToken,
    InvalidProfile,
    ServiceNotFound,
    ServerError,
)
from nextcode.utils import decode_token, check_resp_error
from tests import BaseTestCase, REFRESH_TOKEN, ACCESS_TOKEN, AUTH_URL, AUTH_RESP

cfg = config.Config()


class ClientTest(BaseTestCase):
    def test_client(self):
        with self.assertRaises(InvalidProfile):
            _ = Client(profile="dummy")
        cfg.get("profiles")["dummy"] = {}
        cfg.set({"default_profile": "dummy"})
        client = Client(profile="dummy")

        with self.assertRaises(ServiceNotFound):
            svc = client.service("notfound")

    def test_default_profile(self):
        cfg.get("profiles")["dummy"] = {}
        cfg.set({"default_profile": "dummy"})
        client = Client()

        os.environ["GOR_API_KEY"] = "ble"
        cfg.set({"default_profile": None})
        with self.assertRaises(Exception):
            client = Client()

        with patch("nextcode.client.root_url_from_api_key"):
            client = Client()

        del os.environ["GOR_API_KEY"]
        with self.assertRaises(InvalidProfile):
            client = Client()

    def test_api_key_overrides_default_profile(self):
        cfg.get("profiles")["dummy"] = {"api_key": "the_token"}
        cfg.set({"default_profile": "dummy"})

        with patch("nextcode.client.root_url_from_api_key"):
            client = Client(api_key="another_token")
            self.assertEqual(client.profile.api_key, "another_token")

    @responses.activate
    def test_get_api_key(self):
        auth_url = (
            "https://host/auth/realms/wuxinextcode.com/protocol/openid-connect/token"
        )
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST, auth_url, body="Refresh token has expired", status=400
            )
            with self.assertRaises(InvalidToken) as ctx:
                get_api_key("host", "username", "password")
            self.assertIn("Refresh token has expired", repr(ctx.exception))

        with responses.RequestsMock() as rsps:
            expected_api_key = "the_token"
            rsps.add(responses.POST, auth_url, json={"refresh_token": expected_api_key})
            api_key = get_api_key("host", "username", "password")
            self.assertEqual(expected_api_key, api_key)

            _ = get_api_key("https://host", "username", "password")
            _ = get_api_key("https://host/something", "username", "password")

    @responses.activate
    def test_get_access_token(self):
        cfg.get("profiles")["dummy"] = {"api_key": ACCESS_TOKEN, "root_url": "dummy"}
        client = Client(profile="dummy")
        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, AUTH_URL, json=AUTH_RESP)
            jwt = client.get_access_token()
            self.assertEqual(jwt, ACCESS_TOKEN)
            payload = client.get_access_token(True)
            self.assertTrue(isinstance(payload, dict))
            repr(client)

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, AUTH_URL, body="bla", status=400)
            with self.assertRaises(InvalidToken):
                jwt = client.get_access_token()

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, AUTH_URL, body="Refresh token expired", status=400)
            with self.assertRaises(InvalidToken) as ctx:
                jwt = client.get_access_token()
            self.assertIn("Refresh token has expired", repr(ctx.exception))

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                AUTH_URL,
                json={"error_description": "errordesc"},
                status=400,
            )
            with self.assertRaises(InvalidToken) as ctx:
                jwt = client.get_access_token()
            self.assertIn("errordesc", repr(ctx.exception))

    def test_available_services(self):
        ret = Client.available_services()
        self.assertTrue(isinstance(ret, list))

    def test_check_resp_error(self):
        resp = MagicMock()
        resp.status_code = 500

        def mock_json():
            return {"error": {"description": "errordesc", "errors": ["error"]}}

        resp.raise_for_status.side_effect = Exception("error")
        resp.json = mock_json
        with self.assertRaises(ServerError):
            check_resp_error(resp)

    @responses.activate
    @patch("nextcode.session.load_cache", return_value=None)
    def test_initialize(self, load_cache):
        url_base = "https://test.wuxinextcode/api/query"
        session = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)
        self.assertEqual(session.initialized, False)
        responses.add(responses.GET, url_base, json=AUTH_RESP)
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        session._initialize()
        self.assertEqual(session.initialized, True)

    @responses.activate
    @patch("nextcode.session.load_cache", return_value=None)
    def test_fetch_root_info(self, load_cache):
        url_base = "https://test.wuxinextcode/api/query"

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, AUTH_URL, json=AUTH_RESP)
            with self.assertRaises(ServerError):
                session = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)
                session._initialize()

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, AUTH_URL, json=AUTH_RESP)
            rsps.add(responses.GET, url_base, json=AUTH_RESP)
            session = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)
            session._initialize()

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, AUTH_URL, json=AUTH_RESP)
            rsps.add(responses.GET, url_base, body="text body")
            with self.assertRaises(ServerError):
                session = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)
                session._initialize()

    @responses.activate
    def test_url_from_endpoint(self):
        url_base = "https://test.wuxinextcode/api/query"
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, url_base, json={"endpoints": {"one": "endpoint"}})
        session = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)
        self.assertEqual(session.initialized, False)
        with self.assertRaises(ServerError):
            session.url_from_endpoint("nonexistent")
        self.assertEqual(session.initialized, True)
        session.url_from_endpoint("one")
        ret = session.links({"links": {"a": "b"}})
        self.assertEqual(ret, {"a": "b"})

    @responses.activate
    def test_initialize_before_request(self):
        url_base = "https://test.wuxinextcode/api/query"
        session = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)
        self.assertEqual(session.initialized, False)
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, url_base, json={"endpoints": {"one": "endpoint"}})
        session.get(url_base)
        self.assertEqual(session.initialized, True)

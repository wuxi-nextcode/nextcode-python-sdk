from unittest import TestCase
import os
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from nextcode import config, Client
from nextcode.session import ServiceSession
from nextcode.exceptions import (
    InvalidToken,
    InvalidProfile,
    ServiceNotFound,
    ServerError,
)
from nextcode.utils import decode_token, check_resp_error
from tests import BaseTestCase, REFRESH_TOKEN, ACCESS_TOKEN, AUTH_URL, AUTH_RESP

import logging

logging.basicConfig(level=logging.DEBUG)

cfg = config.Config()


class BasicTest(BaseTestCase):
    def test_decode_token(self):
        with self.assertRaises(InvalidToken):
            decode_token("invalid")
        payload = decode_token(REFRESH_TOKEN)
        self.assertEqual("Offline", payload["typ"])

        payload = decode_token(ACCESS_TOKEN)
        self.assertEqual("test@wuxinextcode.com", payload["preferred_username"])

    def test_profile(self):
        _ = config.create_profile("dummy", REFRESH_TOKEN)
        self.assertEqual(list(cfg.get("profiles").keys()), ["dummy"])

        with self.assertRaises(InvalidProfile):
            _ = config.create_profile("invalid", "invalid")

        _ = config.set_default_profile("dummy")
        with self.assertRaises(InvalidProfile):
            _ = config.set_default_profile("invalid")

        with patch(
            "nextcode.config._load_config",
            return_value={"profiles": {"name": "profile"}},
        ):
            config._init_config()

    def test_cache(self):
        os.environ["NEXTCODE_DISABLE_CACHE"] = "1"
        config.load_cache("name")
        config.save_cache("name", {})
        os.environ["NEXTCODE_DISABLE_CACHE"] = ""


class ClientTest(BaseTestCase):
    def test_client(self):
        with self.assertRaises(InvalidProfile):
            _ = Client(profile="dummy")
        cfg.get("profiles")["dummy"] = {}
        client = Client(profile="dummy")

        with self.assertRaises(ServiceNotFound):
            svc = client.service("notfound")

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
    def test_fetch_root_info(self, load_cache):
        url_base = "https://test.wuxinextcode/api/query"

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, AUTH_URL, json=AUTH_RESP)
            with self.assertRaises(ServerError):
                session = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, AUTH_URL, json=AUTH_RESP)
            rsps.add(responses.GET, url_base, json=AUTH_RESP)
            session = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, AUTH_URL, json=AUTH_RESP)
            rsps.add(responses.GET, url_base, status=404)
            with self.assertRaises(ServerError):
                _ = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, AUTH_URL, json=AUTH_RESP)
            rsps.add(responses.GET, url_base, body="text body")
            with self.assertRaises(ServerError):
                _ = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)

    @responses.activate
    def test_url_from_endpoint(self):
        url_base = "https://test.wuxinextcode/api/query"
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, url_base, json={"endpoints": {"one": "endpoint"}})
        session = ServiceSession(url_base=url_base, api_key=REFRESH_TOKEN)
        with self.assertRaises(ServerError):
            session.url_from_endpoint("nonexistent")
        session.url_from_endpoint("one")
        ret = session.links({"links": {"a": "b"}})
        self.assertEqual(ret, {"a": "b"})

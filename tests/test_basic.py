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
        _ = config.get_config()
        with self.assertRaises(InvalidProfile):
            _ = config.get_profile_config()

    def test_delete_profile(self):
        _ = config.create_profile("dummy", REFRESH_TOKEN)
        _ = config.set_default_profile("dummy")
        default = config.get_default_profile()
        self.assertEqual(default, "dummy")
        config.delete_profile("dummy")
        self.assertEqual(config.get_default_profile(), None)
        with self.assertRaises(InvalidProfile):
            config.delete_profile("dummy")

    def test_cache(self):
        os.environ["NEXTCODE_DISABLE_CACHE"] = "1"
        config.load_cache("name")
        config.save_cache("name", {})
        os.environ["NEXTCODE_DISABLE_CACHE"] = ""

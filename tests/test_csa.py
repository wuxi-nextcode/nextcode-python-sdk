from unittest import TestCase
import os
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from nextcode import config, Client, csa
from nextcode.session import ServiceSession
from nextcode.exceptions import (
    InvalidToken,
    InvalidProfile,
    ServiceNotFound,
    ServerError,
    CSAError,
    AuthServerError,
)
from nextcode.utils import decode_token, check_resp_error
from tests import BaseTestCase, REFRESH_TOKEN, ACCESS_TOKEN, AUTH_URL, AUTH_RESP

import logging

logging.basicConfig(level=logging.DEBUG)

cfg = config.Config()


class CsaTest(BaseTestCase):
    def test_get_csa_error(self):
        resp = MagicMock()
        resp.json.return_value = {"error": {"full_message": ["a", "b"]}}
        csa._get_csa_error(resp)

        resp = MagicMock()
        resp.json.side_effect = Exception
        csa._get_csa_error(resp)

    def test_check_csa_error(self):
        resp = MagicMock()
        resp.json.return_value = {"error": {"full_message": ["a", "b"]}}
        resp.status_code = 420
        with self.assertRaises(CSAError):
            csa._check_csa_error(resp)
        resp.status_code = 200
        csa._check_csa_error(resp)

    @responses.activate
    def test_csa_session_init(self):
        root_url = "https://test.wuxinextcode.com/"
        user_name = "csauser"
        password = "csapass"
        with responses.RequestsMock() as rsp:
            rsp.add(responses.GET, f"{root_url}csa/api/users.json")
            session = csa.CSASession(root_url, user_name, password)

        with responses.RequestsMock() as rsp:
            rsp.add(responses.GET, f"{root_url}csa/api/users.json", status=404)
            rsp.add(
                responses.GET,
                f"{root_url.replace('test', 'test-cluster')}csa/api/users.json",
                status=200,
            )
            session = csa.CSASession(root_url, user_name, password)

        with responses.RequestsMock() as rsp:
            rsp.add(responses.GET, f"{root_url}csa/api/users.json", status=401)
            with self.assertRaises(AuthServerError):
                session = csa.CSASession(root_url, user_name, password)

    @responses.activate
    def test_csa_get_user_key(self):
        root_url = "https://test.wuxinextcode.com/"
        user_name = "csauser"
        password = "csapass"
        test_user = "testuser@test.com"
        user_key = "userkey"
        responses.add(
            responses.GET,
            f"{root_url}csa/api/users.json",
            json={"users": [{"email": test_user, "key": user_key}]},
        )
        session = csa.CSASession(root_url, user_name, password)
        session.get_user_key(test_user)

    @responses.activate
    def test_csa_create_user(self):
        root_url = "https://test.wuxinextcode.com/"
        user_name = "csauser"
        password = "csapass"
        test_user = "testuser@test.com"
        user_key = "userkey"

        with responses.RequestsMock() as rsp:
            rsp.add(
                responses.GET,
                f"{root_url}csa/api/users.json",
                json={"users": [{"email": test_user, "key": user_key}]},
            )
            session = csa.CSASession(root_url, user_name, password)
            with self.assertRaises(CSAError):
                session.create_user(test_user, password)

        with responses.RequestsMock() as rsp:
            rsp.add(responses.GET, f"{root_url}csa/api/users.json", json={"users": []})
            rsp.add(responses.POST, f"{root_url}csa/api/users.json")
            session = csa.CSASession(root_url, user_name, password)
            session.create_user(test_user, password)

    @responses.activate
    def test_csa_add_user_to_project(self):
        root_url = "https://test.wuxinextcode.com/"
        user_name = "csauser"
        password = "csapass"
        test_user = "testuser@test.com"
        user_key = "userkey"

        with responses.RequestsMock() as rsp:
            rsp.add(
                responses.GET,
                f"{root_url}csa/api/users.json",
                json={"users": [{"email": test_user, "key": user_key}]},
            )
            rsp.add(
                responses.POST,
                f"{root_url}csa/api/user_roles.json",
                json={"users": [{"email": test_user, "key": user_key}]},
            )
            session = csa.CSASession(root_url, user_name, password)
            session.add_user_to_project(test_user, "project")

    @responses.activate
    def test_csa_get_project_names(self):
        root_url = "https://test.wuxinextcode.com/"
        user_name = "csauser"
        password = "csapass"
        test_user = "testuser@test.com"
        user_key = "userkey"
        responses.add(
            responses.GET,
            f"{root_url}csa/api/users.json",
            json={"users": [{"email": test_user, "key": user_key}]},
        )
        responses.add(
            responses.GET, f"{root_url}csa/api/projects.json", json={"projects": []}
        )
        session = csa.CSASession(root_url, user_name, password)
        session.get_project_names()

    @responses.activate
    def test_csa_get_project(self):
        root_url = "https://test.wuxinextcode.com/"
        user_name = "csauser"
        password = "csapass"
        test_user = "testuser@test.com"
        user_key = "userkey"
        responses.add(
            responses.GET,
            f"{root_url}csa/api/users.json",
            json={"users": [{"email": test_user, "key": user_key}]},
        )
        responses.add(
            responses.GET,
            f"{root_url}csa/api/projects/testproject.json",
            json={"project": {}},
        )
        session = csa.CSASession(root_url, user_name, password)
        session.get_project("testproject")

    @responses.activate
    def test_csa_create_project(self):
        root_url = "https://test.wuxinextcode.com/"
        user_name = "csauser"
        password = "csapass"
        test_user = "testuser@test.com"
        user_key = "userkey"
        responses.add(
            responses.GET,
            f"{root_url}csa/api/users.json",
            json={"users": [{"email": test_user, "key": user_key}]},
        )
        responses.add(
            responses.GET,
            f"{root_url}csa/api/projects/testproject.json",
            json={"project": {}},
        )
        responses.add(
            responses.POST, f"{root_url}csa/api/projects.json", json={"project": {}}
        )
        session = csa.CSASession(root_url, user_name, password)
        session.create_project("testproject", "testorg")

import os
import responses
from copy import deepcopy
from nextcode import config, Client
from nextcode.services import BaseService
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

SERVICE_URL = "https://test.wuxinextcode.com/service"
ROOT_RESP = {
    "endpoints": {
        "health": SERVICE_URL + "/health",
        "documentation": SERVICE_URL + "/documentation",
    },
    "current_user": {"email": "testuser"},
    "service_name": "myservice",
    "build_info": {"version": "1.0.0"},
}


class ServicesTest(BaseTestCase):
    @responses.activate
    def setUp(self):
        super(ServicesTest, self).setUp()
        self.client = Client(api_key=REFRESH_TOKEN)

    @responses.activate
    def test_base_service(self):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, SERVICE_URL, json=ROOT_RESP)
        svc = BaseService(self.client, service_path="service")
        svc.status()
        svc.status(force=True)
        self.assertEqual(
            "<Service myservice 1.0.0 | https://test.wuxinextcode.com/service>",
            repr(svc),
        )
        _ = svc.build_info
        _ = svc.app_info
        _ = svc.endpoints

    @responses.activate
    def test_localhost(self):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, "http://localhost/", json=ROOT_RESP)
        client = Client(api_key=REFRESH_TOKEN)
        client.profile.root_url = "http://localhost"
        _ = BaseService(client, service_path="service")
        client.profile.root_url = ""
        with self.assertRaises(InvalidProfile):
            _ = BaseService(client, service_path="service")
        client.profile.root_url = "http://localhost"
        client.profile.skip_auth = True
        _ = BaseService(client, service_path="service")

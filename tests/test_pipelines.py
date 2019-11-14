import responses
from unittest import mock
from nextcode import Client
from tests import BaseTestCase, REFRESH_TOKEN, AUTH_RESP, AUTH_URL

PIPELINES_URL = "https://test.wuxinextcode.com/pipelines-service"
JOBS_URL = PIPELINES_URL + "/jobs"
ROOT_RESP = {
    "endpoints": {
        "health": PIPELINES_URL + "/health",
        "documentation": PIPELINES_URL + "/documentation",
        "jobs": JOBS_URL,
    },
    "current_user": {"email": "testuser"},
}

JOBS_RESP = {"jobs": [{"job_id": 666, "links": {}}]}


class PipelinesTest(BaseTestCase):
    def setUp(self):
        super(PipelinesTest, self).setUp()
        self.svc = self.get_service()

    @responses.activate
    def get_service(self):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, PIPELINES_URL, json=ROOT_RESP)

        client = Client(api_key=REFRESH_TOKEN)
        svc = client.service("pipelines")
        return svc

    @responses.activate
    def test_pipelines_status(self):
        _ = self.svc.status()

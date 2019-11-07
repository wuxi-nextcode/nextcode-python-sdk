import responses

from nextcode import Client
from tests import BaseTestCase, REFRESH_TOKEN, AUTH_RESP, AUTH_URL

WORKFLOW_URL = "https://test.wuxinextcode.com/workflow"
ROOT_RESP = {
    "endpoints": {
        "health": "https://test.wuxinextcode.com/workflow/health",
        "documentation": "https://test.wuxinextcode.com/workflow/documentation",
    },
    "current_user": {"email": "testuser"},
}


class BasicTest(BaseTestCase):
    @responses.activate
    def test_workflow(self):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, WORKFLOW_URL, json=ROOT_RESP)

        client = Client(api_key=REFRESH_TOKEN)
        svc = client.service("workflow")
        svc.status()
        svc.status(force=True)
        ret = svc.endpoints

        responses.add(responses.GET, WORKFLOW_URL + "/documentation", json={})
        ret = svc.openapi_spec()

        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.GET, WORKFLOW_URL + "/health")
            ret = svc.healthy()
            self.assertTrue(ret)

        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.GET, WORKFLOW_URL + "/health", status=404)
            ret = svc.healthy()
            self.assertFalse(ret)

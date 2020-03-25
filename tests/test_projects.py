import responses

from nextcode import Client
from tests import BaseTestCase


class ProjectTest(BaseTestCase):
    def setUp(self):
        super(QueryTest, self).setUp()
        self.svc = self.get_service(project="testproject")

    @responses.activate
    def get_service(self, project=None):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, ROOT_URL, json=ROOT_RESP)

        client = Client(api_key=REFRESH_TOKEN)
        svc = client.service("query", project=project)
        return svc

    def test_list_projects(self):
        pass

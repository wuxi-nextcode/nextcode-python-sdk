import responses
from unittest import mock
import datetime
from copy import deepcopy

from nextcode import Client
from nextcode.exceptions import ServerError
from nextcode.services.project.exceptions import ProjectError
from tests import BaseTestCase, REFRESH_TOKEN, AUTH_RESP, AUTH_URL

ROOT_URL = "https://test.wuxinextcode.com/api/project"
PROJECTS_URL = ROOT_URL + "/projects"
PROJECT_URL = PROJECTS_URL + "/35"
PROJECT_USERS_URL = PROJECT_URL + "/users"
USERS_URL = ROOT_URL + "/users"
USER_URL = USERS_URL + "/1"
CREDENTIALS_URL = USER_URL + "/credentials"
ROOT_RESP = {
    "app_info": {"minio_url": "https://platform-projects.wuxinextcodedev.com"},
    "endpoints": {
        "health": ROOT_URL + "/health",
        "documentation": ROOT_URL + "/documentation",
        "users": USERS_URL,
        "projects": PROJECTS_URL,
    },
    "current_user": {"email": "testuser", "link": USER_URL, "admin": True},
    "service_name": "project",
    "build_info": {"version": "1.9.0"},
}
PROJECTS_RESP = [
    {
        "create_date": "2019-08-26T10:49:51.322125",
        "description": "My description",
        "project_name": "testing",
        "links": {"self": PROJECT_URL, "users": PROJECT_USERS_URL},
        "title": "My title",
        "project_id": 35,
    }
]

USER_RESP = {
    "user_id": 1,
    "user_name": "test@wuxinextcode.com",
    "links": {"credentials": CREDENTIALS_URL, "self": USER_URL},
}

CREDENTIALS_RESP = {
    "user_id": 1,
    "user_name": "test@wuxinextcode.com",
    "links": {"credentials": CREDENTIALS_URL, "self": USER_URL},
}


class ProjectTest(BaseTestCase):
    def setUp(self):
        super(ProjectTest, self).setUp()
        self.svc = self.get_service()

    @responses.activate
    def get_service(self):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, ROOT_URL, json=ROOT_RESP)
        responses.add(
            responses.GET, PROJECTS_URL + "?project_name=testing", json=PROJECTS_RESP
        )
        responses.add(responses.GET, USER_URL, json=USER_RESP)
        responses.add(responses.GET, CREDENTIALS_URL, json=CREDENTIALS_RESP)

        client = Client(api_key=REFRESH_TOKEN)
        svc = client.service("project", project="testing")
        return svc

    @responses.activate
    def test_project_status(self):
        _ = self.svc.status()

    @responses.activate
    def test_create_project(self):
        responses.add(responses.POST, PROJECTS_URL, json=PROJECTS_RESP[0])
        responses.add(
            responses.GET, PROJECTS_URL + "?project_name=testing", json=PROJECTS_RESP
        )
        print(PROJECT_USERS_URL)
        responses.add(responses.GET, PROJECT_USERS_URL, json=[])
        _ = self.svc.create_project()
        _ = self.svc.get_users_in_project()
        _ = self.svc.get_user_in_project(
            self.svc.project, user_name="test@wuxinextcode.com"
        )
        with self.assertRaises(ProjectError):
            _ = self.svc.get_my_project_access()

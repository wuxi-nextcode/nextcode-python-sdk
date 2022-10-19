import datetime
import responses
from copy import deepcopy
from unittest import mock
from unittest import skipUnless

from nextcode import Client
from nextcode.exceptions import ServerError
from nextcode.services.project.exceptions import ProjectError
from tests import BaseTestCase, REFRESH_TOKEN, AUTH_RESP, AUTH_URL

try:
    import pandas
    PANDAS_INSTALLED = True
except ModuleNotFoundError:
    PANDAS_INSTALLED = False

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
    "aws_access_key_id": "aws_access_key_id",
    "aws_secret_access_key": "aws_secret_access_key",
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
        responses.add(responses.GET, PROJECT_USERS_URL, json=[])
        _ = self.svc.create_project()
        _ = self.svc.get_users_in_project()
        _ = self.svc.get_user_in_project(
            self.svc.project, user_name="test@wuxinextcode.com"
        )
        with self.assertRaises(ProjectError):
            _ = self.svc.get_my_project_access()

    @responses.activate
    def test_get_all_projects(self):
        responses.add(responses.GET, PROJECTS_URL, json=PROJECTS_RESP)
        self.svc.get_all_projects()

    @responses.activate
    def test_get_project(self):
        responses.add(responses.GET, PROJECTS_URL + "?project_name=blabla", json=[])
        self.svc._get_project("blabla")

    @responses.activate
    def test_credentials(self):
        responses.add(
            responses.GET, USER_URL, json={"links": {"credentials": CREDENTIALS_URL}}
        )
        responses.add(responses.GET, CREDENTIALS_URL, json=CREDENTIALS_RESP)
        responses.add(responses.PUT, CREDENTIALS_URL, json=CREDENTIALS_RESP)
        responses.add(responses.DELETE, CREDENTIALS_URL)

        self.svc.get_credentials()

        self.svc.set_credentials("keykey")

        self.svc.delete_credentials()

        url = "http://test"

        def mock_get_user():
            return {"links": {"credentials": url}}

        self.svc.get_my_user = mock_get_user
        responses.add(responses.GET, url, status=404)
        with self.assertRaises(ProjectError):
            self.svc.get_credentials()

        responses.add(responses.PUT, url, json={})
        self.svc.get_credentials(create=True)

    @responses.activate
    def test_add_user_to_project(self):
        responses.add(
            responses.GET, PROJECTS_URL + "?project_name=testing", json=PROJECTS_RESP
        )
        responses.add(
            responses.GET, USER_URL, json={"links": {"credentials": CREDENTIALS_URL}}
        )
        responses.add(responses.POST, PROJECT_USERS_URL, json={})
        self.svc.add_user_to_project(project_name="testing", user_name="bla")
        responses.add(
            responses.GET,
            PROJECT_USERS_URL,
            json=[{"user_name": "bla", "links": {"self": PROJECT_USERS_URL + "/1"}}],
        )
        responses.add(responses.DELETE, PROJECT_USERS_URL + "/1")
        self.svc.remove_user_from_project(project_name="testing", user_name="bla")

        self.svc.is_admin = lambda: False
        with self.assertRaises(ProjectError):
            self.svc.add_user_to_project(project_name="testing", user_name="bla")

    @responses.activate
    def test_obliterate_user(self):
        username = "user"
        url = "http://test"
        responses.add(responses.GET, USERS_URL, json=[{"links": {"self": url}}])
        responses.add(responses.DELETE, url)
        self.svc.obliterate_user(username)

    @responses.activate
    def test_delete_project(self):
        responses.add(
            responses.GET, PROJECTS_URL + "?project_name=testing", json=PROJECTS_RESP
        )
        responses.add(
            responses.GET,
            PROJECT_USERS_URL,
            json=[
                {
                    "user_name": "bla",
                    "policies": [],
                    "links": {"self": PROJECT_USERS_URL + "/1"},
                }
            ],
        )

        with self.assertRaises(NotImplementedError):
            self.svc.delete_project()

    @responses.activate
    def test_get_project_bucket(self):
        username = "user"
        url = "http://test"
        responses.add(responses.GET, USERS_URL + "/1", json=[{"links": {"self": url}}])
        responses.add(
            responses.GET, PROJECTS_URL + "?project_name=testing", json=PROJECTS_RESP
        )
        responses.add(
            responses.GET,
            PROJECT_USERS_URL,
            json=[
                {
                    "user_name": "bla",
                    "policies": [],
                    "links": {"self": PROJECT_USERS_URL + "/1"},
                }
            ],
        )
        url = "http://test"

        def mock_get_user():
            return {"links": {"credentials": url}}

        self.svc.get_my_user = mock_get_user
        responses.add(
            responses.GET,
            url,
            json={
                "aws_access_key_id": "aws_access_key_id",
                "aws_secret_access_key": "aws_secret_access_key",
            },
        )
        self.svc.get_project_bucket()

    @responses.activate
    def test_s3(self):
        responses.add(
            responses.GET,
            PROJECT_USERS_URL,
            json=[
                {
                    "user_name": "bla",
                    "policies": [],
                    "links": {"self": PROJECT_USERS_URL + "/1"},
                }
            ],
        )
        responses.add(responses.GET, USER_URL, json=USER_RESP)
        responses.add(responses.GET, CREDENTIALS_URL, json=CREDENTIALS_RESP)
        self.svc.get_project_bucket = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_list_objects = mock.MagicMock(
            return_value={
                "CommonPrefixes": [{"Prefix": "/bleeerg"}],
                "Contents": [{"Size": 123456, "Key": "bleeerg/eoee"}],
            }
        )
        mock_bucket.meta.client.list_objects = mock_list_objects
        self.svc.get_project_bucket.return_value = mock_bucket
        self.svc.upload("filename", "test")
        self.svc.download("test")

    @responses.activate
    @skipUnless(PANDAS_INSTALLED, "pandas library is not installed")
    def test_list(self):
        responses.add(
            responses.GET,
            PROJECT_USERS_URL,
            json=[
                {
                    "user_name": "bla",
                    "policies": [],
                    "links": {"self": PROJECT_USERS_URL + "/1"},
                }
            ],
        )
        responses.add(responses.GET, USER_URL, json=USER_RESP)
        responses.add(responses.GET, CREDENTIALS_URL, json=CREDENTIALS_RESP)
        self.svc.get_project_bucket = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_list_objects = mock.MagicMock(
            return_value={
                "CommonPrefixes": [{"Prefix": "/bleeerg"}],
                "Contents": [{"Size": 123456, "Key": "bleeerg/eoee"}],
            }
        )
        mock_bucket.meta.client.list_objects = mock_list_objects
        self.svc.get_project_bucket.return_value = mock_bucket
        self.svc.list()

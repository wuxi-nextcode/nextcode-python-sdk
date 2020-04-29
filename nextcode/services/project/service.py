"""
Service class
------------------
Service object for interfacing with the Project Service API.

"""
import time
import os

from typing import Optional, List, Union, Dict
from ...services import BaseService
from ...client import Client
from ...exceptions import NotFound, ServerError
from .exceptions import ProjectError

import boto3
from botocore.client import Config as BotoConfig

import logging

SERVICE_PATH = "api/project"


log = logging.getLogger(__name__)


class Service(BaseService):
    """
    A connection to the project service API server
    """

    project_name = None
    project = None
    links: dict = {}

    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)
        project_name = (
            kwargs.get("project")
            or os.environ.get("GOR_API_PROJECT")
            or client.profile.project
        )

        self.urls = {
            "projects": self.session.url_from_endpoint("projects"),
            "users": self.session.url_from_endpoint("users"),
        }
        self.minio_url = self.session.root_info["app_info"]["minio_url"]
        if project_name:
            self._init_project(project_name)

    def _init_project(self, project_name):
        """
        Initialize the project from the server
        """
        self.project_name = project_name
        self.project = self.get_project(project_name)
        self.links = self.project.get("links", {})
        log.info(f"Service initialized with project {self.project_name}")

    def _check_project(self):
        """
        Raise an exception if there is no project specified

        :raises: QueryError
        """
        if not self.project:
            raise ProjectError("No project specified")

    def get_all_projects(self) -> List:
        """
        Returns the projects that have been created on the current serv

        :return: List of projects
        """
        resp = self.session.get(self.urls["projects"])
        ret = resp.json()
        return ret

    def get_project(self, project_name):
        data = {"project_name": project_name}
        resp = self.session.get(self.urls["projects"], params=data)
        ret = resp.json()
        if not ret:
            raise NotFound(
                f"Project {project_name} was not found or you do not have access"
            )
        return ret[0]

    def get_my_user(self):
        url = self.urls["users"]
        data = {"user_name": self.current_user.get("email")}
        resp = self.session.get(url, params=data)
        user = resp.json()[0]
        return user

    def get_credentials(self):
        user = self.get_my_user()
        credentials_url = user["links"]["credentials"]
        try:
            resp = self.session.get(credentials_url)
        except ServerError as e:
            raise ProjectError(str(e)) from None
        credentials = resp.json()
        return credentials

    def set_credentials(self, aws_secret_access_key: Optional[str] = None) -> Dict:
        user = self.get_my_user()
        credentials_url = user["links"]["credentials"]
        try:
            resp = self.session.put(
                credentials_url, json={"aws_secret_access_key": aws_secret_access_key}
            )
        except ServerError as e:
            raise ProjectError(str(e)) from None

        credentials = resp.json()
        return credentials

    def delete_credentials(self) -> None:
        user = self.get_my_user()
        credentials_url = user["links"]["credentials"]
        resp = self.session.delete(credentials_url)

    def get_users(self) -> List[Dict]:
        # TODO: admin
        self._check_project()
        users_link = self.links["users"]
        users = self.session.get(users_link)
        return users.json()

    def add_user(self, user_name, policies):
        # TODO: admin
        self._check_project()
        users_link = self.links["users"]
        data = {"user_name": user_name, "policies": policies}
        try:
            users = self.session.post(users_link, json=data)
        except ServerError as se:
            raise ProjectError(str(se)) from None
        return users.json()

    def delete_user(self, user_name):
        # TODO: admin
        self._check_project()
        url = self.urls["users"]
        data = {"user_name": user_name}
        resp = self.session.get(url, params=data)
        user = resp.json()[0]
        if not user:
            raise ProjectError("User not found")
        self.session.delete(user["links"]["self"])

    def delete_project(self):
        self._check_project()
        # TODO: admin
        raise NotImplementedError("Not yet implemented")

    def get_bucket(self):
        self._check_project()
        credentials = self.get_credentials()
        s3 = boto3.resource(
            "s3",
            endpoint_url="https://platform-projects.wuxinextcodedev.com",  #!! TODO
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            config=BotoConfig(signature_version="s3v4"),
        )  # TODO: Region?
        bucket = s3.Bucket(self.project_name)  # pylint: disable=E1101
        return bucket

    def list(self, prefix=""):
        self._check_project()
        bucket = self.get_bucket()
        result = bucket.meta.client.list_objects(
            Bucket=bucket.name, Delimiter="/", Prefix=prefix
        )
        ret = {"folders": [], "files": []}
        if "CommonPrefixes" in result:
            for o in result["CommonPrefixes"]:
                ret["folders"].append(o["Prefix"])
        if "Contents" in result:
            for o in result["Contents"]:
                ret["files"].append(o["Key"])
        return ret

    def download(self, key, path):
        """
        """
        self._check_project()
        bucket = self.get_bucket()
        path = os.path.expanduser(path)
        if path.endswith("/") or os.path.isdir(path):
            filename = key.split("/")[-1]
            path = os.path.join(path, filename)
        log.info(f"Downloading {key} from project {self.project_name} to {path}")
        bucket.download_file(key, path)

    def upload(self, filename, key):
        self._check_project()
        bucket = self.get_bucket()
        path = os.path.expanduser(filename)
        if key.endswith("/"):
            key += os.path.basename(filename)
        log.info(f"Uploading {path} to {key} in project {self.project_name}")
        try:
            bucket.upload_file(path, key)
        except Exception as e:
            raise e from None

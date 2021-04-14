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
from ...utils import jupyter_available

import boto3
from botocore.client import Config as BotoConfig

import logging

SERVICE_PATH = "api/project"
DEFAULT_POLICIES = ["researcher"]

log = logging.getLogger(__name__)


def fmt_size(num, suffix="B"):
    if num == "":
        return ""
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return "%3.0f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.0f%s%s" % (num, "Yi", suffix)


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
        self.credentials = self.get_credentials(create=True)
        if project_name:
            self._init_project(project_name)

    def _init_project(self, project_name):
        """
        Initialize the project from the server
        """
        self.project_name = project_name
        self.project = self._get_project(project_name)
        self.links = {}
        if self.project:
            self.links = self.project.get("links", {})
            log.info(f"Service initialized with project {self.project_name}")

    def is_admin(self):
        """
        Is the current user a project-service admin
        """
        return self.session.root_info.get("current_user", {}).get("admin", False)

    def create_project(self, project_name: Optional[str] = None) -> Dict:
        """
        Create a new project in the project service.

        :param project_name: The name of the project. If omitted, the current project is assumed
        """
        if not self.is_admin():
            raise ProjectError("You lack the required role to create projects")
        if not project_name:
            project_name = self.project_name
        log.info("Creating project {project_name}")
        resp = self.session.post(
            self.urls["projects"], json={"project_name": project_name}
        )
        ret = resp.json()
        self._init_project(project_name)
        return ret

    def _check_project(self, check_admin: Optional[bool] = False) -> List:
        """
        Raise an exception if there is no project specified or if the user
        is not a member of the project

        :param check_admin: Only check if the current user is an admin
        :raises: QueryError
        """
        if not self.project:
            raise ProjectError("No project specified")
        if check_admin:
            if self.is_admin():
                return
        self.get_my_project_access()

    def get_user_in_project(self, project, user_name):
        url = project["links"]["users"]
        data = {"user_name": user_name}
        resp = self.session.get(url, params=data)
        ret = resp.json()
        if not ret:
            return None
        return ret[0]

    def get_my_project_access(self):
        user = self.get_user_in_project(
            self.project, self.current_user.get("user_name")
        )
        if not user:
            raise ProjectError(f"You are not a member of project {self.project_name}")
        ret = user["policies"]
        return ret

    def get_all_projects(self) -> List:
        """
        Returns the projects that have been created on the current serv

        :return: List of projects
        """
        resp = self.session.get(self.urls["projects"])
        ret = resp.json()
        return ret

    def _get_project(self, project_name: str) -> Dict:
        data = {"project_name": project_name}
        resp = self.session.get(self.urls["projects"], params=data)
        ret = resp.json()
        if not ret:
            log.warning(
                f"Project {project_name} was not found or you do not have access"
            )
            return ret
        return ret[0]

    def get_my_user(self) -> Dict:
        url = self.current_user["link"]
        resp = self.session.get(url)
        user = resp.json()
        return user

    def get_credentials(self, create: bool = False) -> Dict:
        user = self.get_my_user()
        credentials_url = user["links"]["credentials"]
        try:
            resp = self.session.get(credentials_url)
            credentials = resp.json()
        except ServerError as e:
            if not create:
                raise ProjectError(str(e)) from None
            else:
                credentials = self.set_credentials()
        return credentials

    def set_credentials(self, minio_access_key: Optional[str] = None) -> Dict:
        user = self.get_my_user()
        credentials_url = user["links"]["credentials"]
        try:
            data: Dict = {}
            if minio_access_key:
                data = {"minio_access_key": minio_access_key}

            resp = self.session.put(credentials_url, json=data)
        except ServerError as e:
            raise ProjectError(str(e)) from None

        credentials = resp.json()
        return credentials

    def delete_credentials(self) -> None:
        user = self.get_my_user()
        credentials_url = user["links"]["credentials"]
        _ = self.session.delete(credentials_url)

    def get_users_in_project(self) -> List[Dict]:
        # TODO: admin
        self._check_project(check_admin=True)
        users_link = self.links["users"]
        users = self.session.get(users_link)
        return users.json()

    def add_user_to_project(
        self,
        project_name: Optional[str] = None,
        user_name: Optional[str] = None,
        policies: List[str] = DEFAULT_POLICIES,
    ):
        if not self.is_admin():
            raise ProjectError("Only user with admin role can add users to project")
        if project_name:
            resp = self.session.get(
                self.urls["projects"], params={"project_name": project_name}
            )
            if resp.json():
                project = resp.json()[0]
            else:
                raise ProjectError(f"Project {project_name} does not exist")
        else:
            self._check_project(check_admin=True)
            project = self.project
        if not user_name:
            user_name = self.current_user["user_name"]
        users_link = project["links"]["users"]
        data = {"user_name": user_name, "policies": policies}
        try:
            users = self.session.post(users_link, json=data)
        except ServerError as se:
            raise ProjectError(str(se)) from None
        return users.json()

    def remove_user_from_project(
        self, project_name: Optional[str] = None, user_name: Optional[str] = None
    ):
        if not self.is_admin():
            raise ProjectError(
                "Only user with admin role can remove users from project"
            )
        if project_name:
            resp = self.session.get(
                self.urls["projects"], params={"project_name": project_name}
            )
            if resp.json():
                project = resp.json()[0]
            else:
                raise ProjectError(f"Project {project_name} does not exist")
        else:
            self._check_project(check_admin=True)
            project = self.project

        user = self.get_user_in_project(project, user_name)
        if not user:
            raise ProjectError(f"User {user_name} not found or you do not have access")
        self.session.delete(user["links"]["self"])

    def obliterate_user(self, user_name):
        if not self.is_admin():
            raise ProjectError("Only user with admin role can delete users")
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

    def get_project_bucket(self):
        self._check_project()
        credentials = self.get_credentials()
        s3 = boto3.resource(
            "s3",
            endpoint_url=self.minio_url,
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            config=BotoConfig(signature_version="s3v4"),
        )  # TODO: Region?
        bucket = s3.Bucket(self.project_name)  # pylint: disable=E1101
        return bucket

    def list(self, prefix: str = "", raw: bool = False) -> Optional[list]:
        self._check_project()
        bucket = self.get_project_bucket()
        result = bucket.meta.client.list_objects(
            Bucket=bucket.name, Delimiter="/", Prefix=prefix
        )
        ret = []
        if "CommonPrefixes" in result:
            for o in result["CommonPrefixes"]:
                ret.append(
                    {"type": "prefix", "size": "", "modified": "", "name": o["Prefix"]}
                )
        if "Contents" in result:
            for o in result["Contents"]:
                ret.append(
                    {
                        "type": "file",
                        "size": o.get("Size"),
                        "modified": o.get("LastModified"),
                        "name": o["Key"],
                    }
                )
        if raw:
            return ret

        if not jupyter_available():
            raise ProjectError(
                "Pandas library is not installed and a dataframe cannot be returned"
            )
        import pandas as pd
        from IPython.display import display

        for r in ret:
            r["size"] = fmt_size(r["size"])
            try:
                r["modified"] = r["modified"].strftime("%b %d %H:%M")
            except Exception:
                pass
            if r["type"] == "file":
                r["name"] = r["name"].split("/")[-1]
            else:
                r["name"] = r["name"].split("/")[-2] + "/"
        df = pd.DataFrame(ret)

        with pd.option_context(
            "display.max_rows",
            None,
            "display.max_colwidth",
            0,
            "display.colheader_justify",
            "left",
        ):
            print(f"Contents of {prefix}:")
            print(df.to_string(index=False))
        return None

    def download(self, key: str, path: Optional[str] = None):
        """"""
        self._check_project()
        bucket = self.get_project_bucket()
        if not path:
            path = "."
        path = os.path.expanduser(path)
        if path.endswith("/") or os.path.isdir(path):
            filename = key.split("/")[-1]
            path = os.path.join(path, filename)
        log_string = f"Downloading {key} from project {self.project_name} to {path}"
        log.info(log_string)
        bucket.download_file(key, path)
        return path

    def upload(self, filename, key):
        self._check_project()
        bucket = self.get_project_bucket()
        path = os.path.expanduser(filename)
        # special case the root folder
        if key in (".", "/"):
            key = ""
        if not key or key.endswith("/"):
            key += os.path.basename(filename)
        if key.startswith("/"):
            key = key[1:]
        # already_exists = not not self.list(key, raw=True)
        # if already_exists and not key.startswith("user_data/"):
        #     raise ProjectError(f"File {key} already exists on server. You can only override files in user_data/")
        log_string = f"Uploading {path} to {key} in project {self.project_name}"
        log.info(log_string)
        try:
            bucket.upload_file(path, key)
        except Exception as e:
            raise e from None
        return key

    def delete(self, key):
        pass

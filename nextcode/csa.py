import os
from urllib.parse import urlsplit
from posixpath import join as urljoin
import requests
from requests import codes
import logging

from .exceptions import ServerError, NotFound, AuthServerError
from .utils import host_from_url

log = logging.getLogger(__name__)


def _get_csa_error(resp):
    try:
        msg = resp.json()["error"]["full_message"][0]
    except Exception:
        msg = str(resp.content)
    return msg


class CSASession:
    def __init__(self, root_url, user_name, password):
        self.root_url = host_from_url(root_url)
        self.session = requests.Session()
        self.session.auth = (user_name, password)
        self.csa_url = urljoin(self.root_url, "csa/api/")

        resp = self.session.get(urljoin(self.csa_url, "users.json"), timeout=2.0)

        if resp.status_code == codes.not_found:
            # ! Temporary hack because services are split between https://[xxx].wuxinextcode.com/
            #   and https://[xxx]-cluster.wuxinextcode.com/
            lst = self.root_url.split(".", 1)
            old_url_base = self.root_url
            if "-cluster" in self.root_url:
                self.root_url = self.root_url.replace("-cluster", "")
            else:
                self.root_url = "{}-cluster.{}".format(lst[0], lst[1])
            log.info(
                "Service not found on server %s. Trying alternative URL %s",
                old_url_base,
                self.root_url,
            )
            self.csa_url = urljoin(self.root_url, "csa/api/")
            resp = self.session.get(urljoin(self.csa_url, "users.json"), timeout=2.0)

        if resp.status_code == codes.unauthorized:
            raise AuthServerError(
                f"User {user_name} could not authenticate with CSA Server"
            )
        resp.raise_for_status()

    def get_user_key(self, user_name):
        users_url = urljoin(self.csa_url, "users.json")
        resp = self.session.get(users_url)

        resp.raise_for_status()
        users = resp.json()["users"]
        for user in users:
            if user["email"] == user_name:
                return user["key"]
        raise AuthServerError(f"User {user_name} not found")

    def create_user(self, user_name, password, exist_ok=False):
        try:
            _ = self.get_user_key(user_name)
        except AuthServerError:
            pass
        else:
            log.info("User '%s' already exists in CSA", user_name)
            if not exist_ok:
                raise AuthServerError(f"User '{user_name}' already exists.")
            else:
                return

        users_url = urljoin(self.csa_url, "users.json")
        payload = {"user": {"email": user_name, "password": password}}
        resp = self.session.post(users_url, json=payload)
        if resp.status_code != codes.created:
            raise AuthServerError(_get_csa_error(resp))
        resp.raise_for_status()
        log.info("Created user '%s' in CSA", user_name)

    def add_user_to_project(
        self, user_name, project, role="researcher", exist_ok=False
    ):
        user_key = self.get_user_key(user_name)
        roles_url = urljoin(self.csa_url, "user_roles.json")
        resp = self.session.post(
            roles_url,
            json={
                "user_role": {
                    "project_key": project,
                    "role": role,
                    "user_key": user_key,
                }
            },
        )
        if resp.status_code == codes.not_found:
            raise AuthServerError(f"Project {project} does not exist")
        elif resp.status_code == codes.bad_request:
            msg = _get_csa_error(resp)
            if "Role has already been taken" in msg and exist_ok:
                log.info(
                    "User '%s' is already a member in project %s", user_name, project
                )
                return
            else:
                raise AuthServerError(msg)
        resp.raise_for_status()
        log.info(
            "User '%s' has been added with role %s to project %s",
            user_name,
            role,
            project,
        )

    def get_projects(self):
        projects_url = urljoin(self.csa_url, "projects.json")
        resp = self.session.get(projects_url)
        resp.raise_for_status()
        projects = resp.json()["projects"]
        return [p["key"] for p in projects]

    def add_credentials(self, owner_key, service, lookup_key, credential_attributes):
        lookup_key = lookup_key.lower()
        cred_url = urljoin(self.csa_url, "auth/v1/credentials.json")

        log.info(
            "Calling '%s' to add '%s' credentials to CSA project '%s'",
            cred_url,
            service,
            owner_key,
        )
        response = self.session.post(
            cred_url,
            json={
                "credential": {
                    "owner_type": "Project",
                    "owner_key": owner_key,
                    "service": service,
                    "lookup_key": lookup_key,
                    "expires": "",
                    "credential_attributes": credential_attributes,
                }
            },
        )
        response.raise_for_status()

        try:
            return response.json()
        except Exception:
            log.exception(
                "could not parse JSON response from server while reserving pipeline step"
            )
            raise

    def add_s3_credentials(self, owner_key, lookup_key, aws_key, aws_secret):
        return self.add_credentials(
            owner_key, "s3", lookup_key, {"key": aws_key, "secret": aws_secret}
        )

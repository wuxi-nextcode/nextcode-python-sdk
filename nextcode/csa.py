"""
csa
~~~~~~~~~~
CSA management features
"""

from posixpath import join as urljoin
import requests
from requests import codes
import logging

from .exceptions import AuthServerError, CSAError
from .utils import host_from_url

log = logging.getLogger(__name__)


def _get_csa_error(resp):
    try:
        msg = resp.json()["error"]["full_message"]
        if isinstance(msg, list):
            msg = ", ".join(msg)
    except Exception:
        msg = str(resp.content)
    return msg


def _check_csa_error(resp):
    if 400 <= resp.status_code < 500:
        raise CSAError(_get_csa_error(resp))
    resp.raise_for_status()


class CSASession:
    def __init__(self, root_url, user_name, password):
        self.root_url = host_from_url(root_url)
        self.session = requests.Session()
        self.session.auth = (user_name, password)
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
                raise CSAError(f"User '{user_name}' already exists.")
            else:
                return

        users_url = urljoin(self.csa_url, "users.json")
        payload = {"user": {"email": user_name, "password": password}}
        resp = self.session.post(users_url, json=payload)
        _check_csa_error(resp)
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
        if not exist_ok:
            _check_csa_error(resp)
        log.info(
            "User '%s' has been added with role %s to project %s",
            user_name,
            role,
            project,
        )

    def get_project_names(self):
        projects_url = urljoin(self.csa_url, "projects.json")
        resp = self.session.get(projects_url)
        resp.raise_for_status()
        projects = resp.json()["projects"]
        return [p["key"] for p in projects]

    def get_project(self, project_name):
        url = urljoin(self.csa_url, f"projects/{project_name}.json")
        resp = self.session.get(url)
        if resp.status_code == codes.not_found:
            return None
        resp.raise_for_status()
        return resp.json()["project"]

    def create_project(
        self, project_name, org_name, ref_version="hg38", exist_ok=False
    ):
        existing_project = self.get_project(project_name)
        if existing_project:
            if not exist_ok:
                raise CSAError("Project already exists")
            else:
                return existing_project

        url = urljoin(self.csa_url, "projects.json")
        data = {
            "project": {
                "key": project_name,
                "name": project_name,
                "organization_key": org_name,
                "reference_version": ref_version,
            }
        }
        resp = self.session.post(url, json=data)
        _check_csa_error(resp)
        return resp.json()["project"]

    def add_credentials(self, owner_key, service, lookup_key, credential_attributes):
        lookup_key = lookup_key.lower()
        url = urljoin(self.csa_url, "auth/v1/credentials.json")
        url = url.replace("/api", "")

        log.info(
            "Calling '%s' to add '%s' credentials to CSA project '%s'",
            url,
            service,
            owner_key,
        )
        resp = self.session.post(
            url,
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
        _check_csa_error(resp)
        return resp.json()

    def add_s3_credentials(self, owner_key, bucket_name, aws_key, aws_secret):
        return self.add_credentials(
            owner_key, "s3", bucket_name, {"key": aws_key, "secret": aws_secret}
        )

    def add_s3_credentials_to_project(
        self, project_name, bucket_name, aws_key, aws_secret
    ):
        return self.add_s3_credentials(project_name, bucket_name, aws_key, aws_secret)

    def get_s3_credentials_for_project(self, project_name):
        url = urljoin(
            self.csa_url,
            f"auth/v1/credentials.json?find[service]=s3&find[project_key]={project_name}",
        )
        url = url.replace("/api", "")
        resp = self.session.get(url)
        resp.raise_for_status()
        creds = resp.json()["credentials"]
        ret = {}
        for cred in creds:
            ret[cred["lookup_key"]] = {
                "aws_access_key_id": cred["credential_attributes"]["key"],
                "aws_secret_access_key": cred["credential_attributes"]["secret"],
                "project_name": cred["owner_key"],
            }
        return ret

    def import_sample(self, sample_data):
        url = urljoin(self.csa_url, "sample_data_sets.json")
        json_data = {"sample_data_set": sample_data}
        log.info("Importing sample into CSA")
        log.debug("Calling '%s' to import sample: %s", url, json_data)
        resp = self.session.post(url, json=json_data)
        _check_csa_error(resp)
        log.debug("Import sample returned content '%s'", resp.content)
        return resp.json()

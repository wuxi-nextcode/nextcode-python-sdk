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


def login_keycloak_user(root_url, realm, client_id, user_name, password):
    # try logging in with the new user
    url = urljoin(root_url, "auth", "realms", realm, "protocol/openid-connect/token")
    body = {
        "grant_type": "password",
        "client_id": client_id,
        "password": password,
        "username": user_name,
        "scope": "offline_access",
    }
    url = url.replace("admin/", "")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    log.debug("Calling POST %s with headers %s and body %s", url, headers, body)
    resp = requests.post(url, headers=headers, data=body)
    try:
        resp.raise_for_status()
        return resp.json()["refresh_token"]
    except Exception as ex:
        raise AuthServerError(f"User {user_name} was unable to log in: {ex}")


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
        user_id = None
        try:
            user = self.get_user_key(user_name)
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


def _get_admin_keycloak_session(auth_server, username, password):
    log.info("Managing users on keycloak server %s...", auth_server)

    # log the admin into the master realm
    url = urljoin(auth_server, "realms/master/protocol/openid-connect/token")
    headers_form = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(
        url,
        data=f"username={username}&password={password}&grant_type=password&client_id=admin-cli",
        headers=headers_form,
    )
    if resp.status_code != 200:
        desc = resp.json()["error_description"]
        raise AuthServerError(
            f"Could not authenticate {username} user against {url}: {desc}"
        )
    access_token = resp.json()["access_token"]
    headers = {
        "Authorization": "Bearer %s" % access_token,
        "Content-Type": "application/json",
    }
    session = requests.Session()
    session.headers = headers
    return session


class KeycloakSession:
    def __init__(
        self,
        root_url,
        username="admin",
        password=None,
        realm="wuxinextcode.com",
        client_id="api-key-client",
    ):
        password = password or os.environ.get("KEYCLOAK_PASSWORD")
        if not password:
            raise AuthServerError(f"User {username} needs an admin password")
        self.root_url = host_from_url(root_url)
        self.realm = realm
        self.auth_server = self._get_auth_server()
        self.session = _get_admin_keycloak_session(self.auth_server, username, password)
        self.realm_url = urljoin(self.auth_server, "admin/realms", realm)
        self.master_url = urljoin(self.auth_server, "admin/realms", "master")
        self.client_id = client_id

    def _get_auth_server(self):
        auth_server = urljoin(self.root_url, "auth")
        r = requests.get(auth_server)
        # ! temporary hack because services are split between xxx.wuxi and xxx-cluster.wuxi
        if r.status_code == codes.not_found:
            if "-cluster" not in auth_server:
                lst = self.root_url.split(".", 1)
                auth_server = lst[0] + "-cluster" + lst[1]
            else:
                auth_server = auth_server.replace("-cluster", "")

        # test if realm is available
        realm_url = urljoin(auth_server, "realms", self.realm)
        try:
            resp = requests.get(realm_url)
        except requests.exceptions.ConnectionError:
            raise ServerError(f"Keycloak server {auth_server} is not reachable")
        if resp.status_code == requests.codes.not_found:
            raise AuthServerError(
                f"Realm '{self.realm}' was not found on keycloak server {auth_server}"
            )

        return auth_server

    def get_user(self, user_name):
        users_url = urljoin(self.realm_url, f"users?username={user_name}")
        resp = self.session.get(users_url)
        resp.raise_for_status()
        if not resp.json():
            raise AuthServerError(f"User '{user_name}' not found.")

        user = resp.json()[0]
        return user

    def get_users(self):
        users_url = urljoin(self.realm_url, "users")
        resp = self.session.get(users_url)
        resp.raise_for_status()
        if not resp.json():
            return []
        users = resp.json()
        return users

    def remove_user(self, user_name):
        user_id = self.get_user(user_name)["id"]

        url = urljoin(self.realm_url, "users", user_id)
        resp = self.session.delete(url)
        resp.raise_for_status()
        log.info("User '%s' has been deleted from realm '%s'", user_name, self.realm)

    def get_user_roles(self, user_name):
        """
        Get the realm roles for this user, ignoring client-specific roles
        """
        user_id = self.get_user(user_name)["id"]
        url = urljoin(self.realm_url, "users", str(user_id), "role-mappings")
        resp = self.session.get(url)
        resp.raise_for_status()
        roles = resp.json()
        role_names = [r["name"] for r in roles.get("realmMappings", [])]
        return role_names

    def create_user(self, user_name, new_password, exist_ok=False):
        user_id = None
        try:
            user = self.get_user(user_name)
        except AuthServerError:
            pass
        else:
            if not exist_ok:
                raise AuthServerError(f"User '{user_name}' already exists.")
            else:
                user_id = user["id"]

        if not user_id:
            url = urljoin(self.realm_url, "users")
            data = {
                "username": user_name,
                "firstName": "None",
                "lastName": "None",
                "email": user_name,
                "enabled": True,
                "emailVerified": True,
            }
            resp = self.session.post(url, json=data)
            resp.raise_for_status()
            user_id = self.get_user(user_name)["id"]

        self.set_user_password(user_name, new_password)
        log.info("User '%s' has been created in realm '%s'.", user_name, self.realm)

    def delete_user(self, user_name):
        user_id = self.get_user(user_name)["id"]

        url = urljoin(self.realm_url, "users", str(user_id))
        resp = self.session.delete(url)
        resp.raise_for_status()
        log.info("User '%s' has been deleted from realm '%s'" % (user_name, self.realm))

    def add_role_to_user(self, user_name, role_name, exist_ok=False):
        user_id = self.get_user(user_name)["id"]
        role_name = role_name.lower()
        user_roles = self.get_user_roles(user_name)
        if role_name in user_roles:
            if exist_ok:
                return
            raise AuthServerError(f"User '{user_name}' already has role '{role_name}'")

        url = urljoin(self.realm_url, f"users/{user_id}/role-mappings/realm/available")
        resp = self.session.get(url)
        resp.raise_for_status()
        available_roles = resp.json()
        role = None
        for r in available_roles:
            if r["name"].lower() == role_name:
                role = r
                break
        if not role:
            raise AuthServerError(
                f"Role '{role_name}' is not available for user '{user_name}'"
            )

        url = urljoin(self.realm_url, f"users/{user_id}/role-mappings/realm")
        resp = self.session.post(url, json=[role])
        resp.raise_for_status()
        log.info(
            "Role '%s' has been added to user '%s' in realm '%s'",
            role_name,
            user_name,
            self.realm,
        )

    def remove_role_from_user(self, user_name, role_name):
        user_id = self.get_user(user_name)["id"]
        role_name = role_name.lower()

        url = urljoin(self.realm_url, f"users/{user_id}/role-mappings")
        resp = self.session.get(url)
        resp.raise_for_status()
        roles = resp.json()["realmMappings"]
        role = None
        for r in roles:
            if r["name"].lower() == role_name:
                role = r
                break
        if not role:
            raise AuthServerError(f"User '{user_id}' does not have role '{role_name}'")

        url = urljoin(self.realm_url, "users/%s/role-mappings/realm" % (user_id))
        resp = self.session.delete(url, json=[role])
        resp.raise_for_status()
        log.info(
            "Role '%s' has been removed from user '%s' in realm '%s'",
            role_name,
            user_name,
            self.realm,
        )

    def login_user(self, user_name, password):
        try:
            return login_keycloak_user(
                self.root_url, self.realm, self.client_id, user_name, password
            )
        except AuthServerError:
            log.exception("Unable to log in")
            return None

    def set_user_password(self, user_name, new_password):
        user_id = self.get_user(user_name)["id"]

        url = urljoin(self.realm_url, f"users/{user_id}/reset-password")
        data = {"type": "password", "temporary": False, "value": new_password}
        resp = self.session.put(url, json=data)
        resp.raise_for_status()
        api_key = self.login_user(user_name, new_password)
        if not api_key:
            raise Exception("Changed password but could not log in!")

    def get_available_roles_for_user(self, user_name):
        user_id = self.get_user(user_name)["id"]
        url = urljoin(self.realm_url, f"users/{user_id}/role-mappings/realm/available")
        resp = self.session.get(url)
        resp.raise_for_status()
        available_roles = resp.json()
        return [r["name"] for r in available_roles]

    def create_role(self, role_name, description="N/A", exist_ok=False):
        url = urljoin(self.realm_url, "roles")
        data = {
            "name": role_name,
            "description": description,
        }
        resp = self.session.post(url, json=data)
        if resp.status_code == codes.conflict:
            if exist_ok:
                return
            raise AuthServerError(f"Role '{role_name}' already exists")
        resp.raise_for_status()

    def get_roles(self):
        url = urljoin(self.realm_url, "roles")
        resp = self.session.get(url)
        resp.raise_for_status()
        roles = resp.json()
        ret = {}
        for r in roles:
            ret[r["name"]] = r
        return ret

    def delete_role(self, role_name):
        role = self.get_roles().get(role_name)
        if not role:
            raise AuthServerError(f"Role '{role_name}' does not exist")
        url = urljoin(self.realm_url, f"roles-by-id/{role['id']}")
        resp = self.session.delete(url)
        resp.raise_for_status()

"""
keycloak
~~~~~~~~~~
Keycloak login helpers and management features
"""

import os
from posixpath import join as urljoin
import requests
from requests import codes
import logging
import webbrowser
from typing import Optional, Dict, List, Any

from .exceptions import ServerError, AuthServerError
from .utils import host_from_url

log = logging.getLogger(__name__)

DEFAULT_REALM = "wuxinextcode.com"
DEFAULT_CLIENT_ID = "api-key-client"


def login_keycloak_user(
    root_url: str,
    user_name: str,
    password: str,
    realm: str = DEFAULT_REALM,
    client_id: str = DEFAULT_CLIENT_ID,
) -> str:
    """
    :param root_url: The root url of the service. e.g. www.myhost.com
    :param user_name: Local keycloak username
    :param password: Password of the user
    :param realm: Realm to authenticate against. Default: wuxinextcode.com
    :param client_id: Client to log in as. Default: api-key-client

    :raises: `AuthServerError`

    Logs into the keycloak server using a username and password. Returns the api key.
    """
    # try logging in with the new user
    root_url = host_from_url(root_url)
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


def auth_popup(root_url: str) -> None:
    """
    Opens a web browser on the login page for the specified server

    The user can log in using OAuth2 flow and aquire an API Key
    """
    root_url = host_from_url(root_url)
    url = urljoin(root_url, "api-key-service")
    webbrowser.open(url)


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
    """
    A session object on a keycloak server intended to provide high-level interfaces
    for managing users and roles on the server.

    The user that is passed into the constructor is assumed to be a keycloak admin.

    :param root_url: The URL of the instance where keycloak is running. e.g. www.myhost.com
    :param username: Username of the keycloak admin. Default: admin
    :param passwrod: Admin password
    :param realm: Keycloak realm to manage. Default: wuxinextcode.com
    :param client_id: Client to log admin into. Default: api-key-client
    """

    def __init__(
        self,
        root_url: str,
        username: str = "admin",
        password: Optional[str] = None,
        realm: str = DEFAULT_REALM,
        client_id: str = DEFAULT_CLIENT_ID,
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

        # test if realm is available
        realm_url = urljoin(auth_server, "realms", self.realm)
        try:
            resp = requests.get(realm_url)
        except requests.exceptions.ConnectionError:
            raise ServerError(f"Keycloak server {realm_url} is not reachable")
        if resp.status_code == requests.codes.not_found:
            raise AuthServerError(
                f"Realm '{self.realm}' was not found on keycloak server {auth_server}"
            )

        return auth_server

    def get_user(self, user_name: str) -> Dict:
        users_url = urljoin(self.realm_url, f"users?username={user_name}")
        resp = self.session.get(users_url)
        resp.raise_for_status()
        users = [u for u in resp.json() if u.get("username") == user_name]
        if not users:
            raise AuthServerError(f"User '{user_name}' not found.")
        return users[0]

    def get_users(self) -> List:
        users_url = urljoin(self.realm_url, "users")
        resp = self.session.get(users_url)
        resp.raise_for_status()
        if not resp.json():
            return []
        users = resp.json()
        return users

    def remove_user(self, user_name: str) -> None:
        user_id = self.get_user(user_name)["id"]

        url = urljoin(self.realm_url, "users", user_id)
        resp = self.session.delete(url)
        resp.raise_for_status()
        log.info("User '%s' has been deleted from realm '%s'", user_name, self.realm)

    def get_user_roles(self, user_name: str) -> List[str]:
        """
        Get the effective realm roles for this user, ignoring client-specific roles
        """
        user_id = self.get_user(user_name)["id"]
        url = urljoin(self.realm_url, f"users/{user_id}/role-mappings/realm/composite")
        resp = self.session.get(url)
        resp.raise_for_status()
        roles = resp.json()
        role_names = [r["name"] for r in roles]
        return role_names

    def create_user(
        self, user_name: str, new_password: str, exist_ok: bool = False
    ) -> None:
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
            if resp.status_code != codes.created:
                msg = resp.text
                try:
                    msg = resp.json()["errorMessage"]
                except Exception:
                    pass
                raise AuthServerError(msg)
            resp.raise_for_status()
            user_id = self.get_user(user_name)["id"]

        self.set_user_password(user_name, new_password)
        log.info("User '%s' has been created in realm '%s'.", user_name, self.realm)

    def delete_user(self, user_name: str) -> None:
        user_id = self.get_user(user_name)["id"]

        url = urljoin(self.realm_url, "users", str(user_id))
        resp = self.session.delete(url)
        resp.raise_for_status()
        log.info("User '%s' has been deleted from realm '%s'" % (user_name, self.realm))

    def add_role_to_user(
        self, user_name: str, role_name: str, exist_ok: bool = False
    ) -> None:
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

    def remove_role_from_user(self, user_name: str, role_name: str) -> None:
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

    def get_user_client_roles(self, user_name: str, client_name: str) -> List[str]:
        """
        Get the specified client roles for this user
        """
        user_id = self.get_user(user_name)["id"]
        client_id = self.get_client(client_name)["id"]
        url = urljoin(self.realm_url, "users", str(user_id), "role-mappings","clients",client_id)
        resp = self.session.get(url)
        resp.raise_for_status()
        roles = resp.json()
        role_names = [r["name"] for r in roles]
        return role_names

    def add_client_role_to_user(
            self, user_name: str, client_name: str, role_name: str, exist_ok: bool = False
    ) -> None:
        user_id = self.get_user(user_name)["id"]
        user_client_roles = self.get_user_client_roles(user_name,client_name)
        if role_name in user_client_roles:
            if exist_ok:
                return
            raise AuthServerError(f"User '{user_name}' already has role '{role_name}' for client '{client_name}'")

        client_id = self.get_client(client_name)["id"]
        url = urljoin(self.realm_url, f"users/{user_id}/role-mappings/clients/{client_id}/available")
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
                f"Role '{role_name}' for client '{client_name}' is not available for user '{user_name}'"
            )

        url = urljoin(self.realm_url, f"users/{user_id}/role-mappings/clients",client_id)
        resp = self.session.post(url, json=[role])
        resp.raise_for_status()
        log.info(
            "Role '%s' for client '%s' has been added to user '%s' in realm '%s'",
            role_name,
            client_name,
            user_name,
            self.realm,
        )

    def get_client(self, client_name: str) -> Dict:
        url = urljoin(self.realm_url, f"clients?clientId={client_name}")
        resp = self.session.get(url)
        resp.raise_for_status()
        for c in resp.json():
            if c.get("clientId") == client_name:
                return c
        raise AuthServerError(f"Client '{client_name}' not found.")

    def login_user(self, user_name: str, password: str) -> Optional[str]:
        try:
            return login_keycloak_user(
                self.root_url, user_name, password, self.realm, self.client_id
            )
        except AuthServerError:
            log.exception("Unable to log in")
            return None

    def set_user_password(self, user_name: str, new_password: str) -> None:
        user_id = self.get_user(user_name)["id"]

        url = urljoin(self.realm_url, f"users/{user_id}/reset-password")
        data = {"type": "password", "temporary": False, "value": new_password}
        resp = self.session.put(url, json=data)
        resp.raise_for_status()
        api_key = self.login_user(user_name, new_password)
        if not api_key:
            raise Exception("Changed password but could not log in!")

    def get_available_roles_for_user(self, user_name: str) -> List[str]:
        user_id = self.get_user(user_name)["id"]
        url = urljoin(self.realm_url, f"users/{user_id}/role-mappings/realm/available")
        resp = self.session.get(url)
        resp.raise_for_status()
        available_roles = resp.json()
        return [r["name"] for r in available_roles]

    def create_role(
        self, role_name: str, description: str = "N/A", exist_ok: bool = False
    ) -> None:
        url = urljoin(self.realm_url, "roles")
        data = {"name": role_name, "description": description}
        resp = self.session.post(url, json=data)
        if resp.status_code == codes.conflict:
            if exist_ok:
                return
            raise AuthServerError(f"Role '{role_name}' already exists")
        resp.raise_for_status()

    def get_roles(self) -> Dict[str, Any]:
        url = urljoin(self.realm_url, "roles")
        resp = self.session.get(url)
        resp.raise_for_status()
        roles = resp.json()
        ret = {}
        for r in roles:
            ret[r["name"]] = r
        return ret

    def delete_role(self, role_name: str) -> None:
        role = self.get_roles().get(role_name)
        if not role:
            raise AuthServerError(f"Role '{role_name}' does not exist")
        url = urljoin(self.realm_url, f"roles-by-id/{role['id']}")
        resp = self.session.delete(url)
        resp.raise_for_status()

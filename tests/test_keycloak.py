import responses
import json
from unittest.mock import patch, MagicMock
from nextcode import Client
from tests import BaseTestCase, REFRESH_TOKEN, AUTH_RESP, AUTH_URL
from nextcode.keycloak import (
    login_keycloak_user,
    DEFAULT_REALM,
    auth_popup,
    KeycloakSession,
)
from nextcode.exceptions import AuthServerError, ServerError

ROOT_URL = "keycloak"
REFRESH_TOKEN = "refresh_token"
ACCESS_TOKEN = "access_token"


class KeycloakTest(BaseTestCase):
    def setUp(self):
        super(KeycloakTest, self).setUp()

    @responses.activate
    def test_login_keycloak_user(self):
        user_name = "user_name"
        password = "password"
        auth_response = {
            "refresh_token": REFRESH_TOKEN,
            "access_token": ACCESS_TOKEN,
        }
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                f"https://{ROOT_URL}/auth/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
                json.dumps(auth_response),
            )
            ret = login_keycloak_user(ROOT_URL, user_name, password)
            self.assertEqual(ret, REFRESH_TOKEN)

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                f"https://{ROOT_URL}/auth/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
                status=401,
            )
            with self.assertRaises(AuthServerError):
                ret = login_keycloak_user(ROOT_URL, user_name, password)

    def test_auth_popup(self):
        with patch("nextcode.keycloak.webbrowser"):
            auth_popup("root")

    @responses.activate
    def test_keycloak_session(self):
        ROOT_URL = "keycloak"
        responses.add(
            responses.GET,
            f"https://{ROOT_URL}/auth",
        )
        responses.add(
            responses.GET,
            f"https://{ROOT_URL}/auth/realms/{DEFAULT_REALM}",
        )
        responses.add(
            responses.POST,
            f"https://{ROOT_URL}/auth/realms/{DEFAULT_REALM}/protocol/openid-connect/token",
        )

        auth_response = {
            "refresh_token": REFRESH_TOKEN,
            "access_token": ACCESS_TOKEN,
        }
        responses.add(
            responses.POST,
            f"https://{ROOT_URL}/auth/realms/master/protocol/openid-connect/token",
            json.dumps(auth_response),
        )

        session = KeycloakSession(ROOT_URL, password="password")

        user_name = "user_name"
        user_id = "123"
        users_response = [{"username": user_name, "id": user_id}]

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users?username={user_name}",
                json.dumps(users_response),
            )
            session.get_user(user_name)

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users",
                json.dumps(users_response),
            )
            session.get_users()

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users",
                json.dumps(users_response),
            )
            rsps.add(
                responses.DELETE,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users/{user_id}",
                json.dumps(users_response),
            )
            session.remove_user(user_name)

        with responses.RequestsMock() as rsps:
            roles_response = [{"name": "bla"}]
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users?username={user_name}",
                json.dumps(users_response),
            )
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users/{user_id}/role-mappings/realm/composite",
                json.dumps(roles_response),
            )
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users/{user_id}/role-mappings",
                json.dumps({"realmMappings": roles_response}),
            )

            rsps.add(
                responses.DELETE,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users/{user_id}/role-mappings/realm",
                json.dumps([{"name": "bla"}]),
            )
            session.get_user_roles(user_name)
            session.add_role_to_user(user_name, "bla", exist_ok=True)
            session.remove_role_from_user(user_name, "bla")

        with responses.RequestsMock() as rsps:
            roles_response = []
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users?username={user_name}",
                json.dumps(users_response),
            )
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users/{user_id}/role-mappings/realm/available",
                json.dumps([{"name": "bla"}]),
            )
            rsps.add(
                responses.POST,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users/{user_id}/role-mappings/realm",
                json.dumps([{"name": "bla"}]),
            )
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users/{user_id}/role-mappings/realm/composite",
                json.dumps(roles_response),
            )
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users/{user_id}/role-mappings",
                json.dumps({"realmMappings": roles_response}),
            )
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users?username=user_name",
                json.dumps(users_response),
            )
            session.add_role_to_user(user_name, "bla", exist_ok=True)
            session.get_available_roles_for_user("user_name")

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "https://keycloak/auth/admin/realms/wuxinextcode.com/users?username=user_name",
                "{}",
            )
            rsps.add(
                responses.POST,
                "https://keycloak/auth/admin/realms/wuxinextcode.com/users",
                "{}",
            )
            with self.assertRaises(AuthServerError):
                session.create_user(user_name, "password")

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "https://keycloak/auth/admin/realms/wuxinextcode.com/users?username=user_name",
                json.dumps([{"username": "user_name", "id": 1}]),
            )
            rsps.add(
                responses.DELETE,
                "https://keycloak/auth/admin/realms/wuxinextcode.com/users/1",
                json.dumps([{"username": "user_name", "id": 1}]),
            )
            session.delete_user(user_name)

    @responses.activate
    def test_get_auth_server(self):
        ROOT_URL = "keycloak.wuxi.com"
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"https://{ROOT_URL}/auth", status=404)
            with self.assertRaises(ServerError):
                session = KeycloakSession(ROOT_URL, password="password")

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"https://{ROOT_URL}/auth", status=200)
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/realms/wuxinextcode.com",
                status=200,
            )
            auth_response = {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN,
            }
            rsps.add(
                responses.POST,
                f"https://{ROOT_URL}/auth/realms/master/protocol/openid-connect/token",
                json.dumps(auth_response),
            )
            rsps.add(
                responses.POST,
                f"https://{ROOT_URL}/auth/realms/wuxinextcode.com/protocol/openid-connect/token",
                json.dumps(auth_response),
            )
            users_response = [{"username": "user", "id": 1}]

            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users?username=user",
                json.dumps(users_response),
            )
            rsps.add(
                responses.PUT,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users/1/reset-password",
                json.dumps(users_response),
            )
            session = KeycloakSession(ROOT_URL, password="password")

            session.login_user("user", "pass")
            session.set_user_password("user", "pass")

    @responses.activate
    def test_roles(self):
        ROOT_URL = "keycloak.wuxi.com"
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"https://{ROOT_URL}/auth", status=200)
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/realms/wuxinextcode.com",
                status=200,
            )
            auth_response = {
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN,
            }
            rsps.add(
                responses.POST,
                f"https://{ROOT_URL}/auth/realms/master/protocol/openid-connect/token",
                json.dumps(auth_response),
            )
            rsps.add(
                responses.POST,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/roles",
                "{}",
            )
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/roles",
                "{}",
            )
            session = KeycloakSession(ROOT_URL, password="password")

            session.create_role("role")
            session.get_roles()
            with self.assertRaises(AuthServerError):
                session.delete_role("role")

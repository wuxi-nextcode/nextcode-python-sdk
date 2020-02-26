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
from nextcode.exceptions import AuthServerError

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
            responses.GET, f"https://{ROOT_URL}/auth",
        )
        responses.add(
            responses.GET, f"https://{ROOT_URL}/auth/realms/{DEFAULT_REALM}",
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
            roles_response = {"realmMappings": []}
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users?username={user_name}",
                json.dumps(users_response),
            )
            rsps.add(
                responses.GET,
                f"https://{ROOT_URL}/auth/admin/realms/{DEFAULT_REALM}/users/{user_id}/role-mappings",
                json.dumps(roles_response),
            )
            session.get_user_roles(user_name)

"""
utils
~~~~~~~~~~
Various utilities for nextcode-sdk functionality.
"""

import jwt
import logging
from urllib.parse import urlsplit
import requests
from requests import codes
import binascii
import os
from importlib.util import find_spec

from .exceptions import ServerError, InvalidToken

log = logging.getLogger(__name__)


def decode_token(token):
    try:
        decoded_token = jwt.decode(token, algorithms=["RS256"], verify=False)
        return decoded_token
    except (KeyError, jwt.InvalidTokenError) as ex:
        raise InvalidToken(f"Token could not be decoded ({ex}): {token}")


def check_resp_error(resp):
    response_json = None
    try:
        resp.raise_for_status()
    except Exception:
        desc = resp.text
        try:
            response_json = resp.json()
            desc = response_json["error"]["description"]
            log.info(response_json)
            if "errors" in response_json["error"]:
                desc += " (%s)" % (response_json["error"]["errors"])
        except Exception:
            pass
        if not desc:
            desc = "Status code %s received (%s)" % (resp.status_code, resp.text)
        else:
            desc += " (code %s)" % resp.status_code
        if resp.status_code >= 500:
            desc = "Server error in call to %s" % resp.url
            desc += " - Response headers: %s" % resp.headers
            desc += " - Response body: %s" % resp.text
            log.error(desc)
        else:
            log.info("Server error in call to %s", resp.url)

        error = ServerError(desc, url=resp.url, response=response_json)
        raise error from None


def root_url_from_api_key(api_key):
    payload = decode_token(api_key)
    parts = urlsplit(payload["iss"])
    root_url = "{scheme}://{netloc}".format(scheme=parts.scheme, netloc=parts.netloc)
    return root_url


def get_access_token(api_key):
    """"""
    payload = decode_token(api_key)
    client_id = payload["azp"]
    body = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": api_key,
        "username": "dummy_user",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_endpoint = "{}/protocol/openid-connect/token".format(payload["iss"])

    # Call the auth server
    log.info("Authenticating with %s", token_endpoint)
    response = requests.post(token_endpoint, data=body, headers=headers, timeout=5.0)
    if (
        response.status_code == codes.bad_request
        and "Refresh token expired" in response.text
    ):
        raise InvalidToken("Refresh token has expired")
    elif response.status_code >= codes.bad_request:
        try:
            if response.json():
                raise InvalidToken(response.json().get("error_description"))
        except Exception:
            pass

    try:
        response.raise_for_status()
    except Exception:
        log.error("Body: %s" % body)
        raise InvalidToken(
            "Error authenticating with %s: %s" % (token_endpoint, response.text)
        )

    return response.json()["access_token"]


def host_from_url(host):
    """
    Gets the raw URI host of a url with trailing slash, no matter how it is formatted.

    For example, www.server.com/something -> https://www.server.com/
                 http://www.server.com -> http://www.server.com/
                 http://localhost:8080/something -> http://localhost:8080/

    """
    if "://" not in host:
        host = f"https://{host}"
    parts = urlsplit(host)
    return "{}://{}/".format(parts.scheme, parts.netloc)


def random_string(num: int = 8) -> str:
    return binascii.hexlify(os.urandom(100)).decode("ascii")[:num]


def jupyter_available() -> bool:
    """
    Check if jupyter dependencies are available without importing these heavy libraries.
    """
    pandas_spec = find_spec("pandas")
    ipython_spec = find_spec("IPython")
    if pandas_spec is not None and ipython_spec is not None:
        return True
    return False


def strtobool(s):
    if isinstance(s, bool):
        return s
    if s and s.lower() in ("true", "t", "yes", "y", "on", "1"):
        return True
    else:
        return False

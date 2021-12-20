"""
client
~~~~~~~~~~

This is the basic entrypoint to interact with services.
"""

import os
import pkgutil
from importlib import import_module
from pathlib import Path
import logging
from typing import Optional, Union, Dict, List
from urllib.parse import urlsplit
from posixpath import join as urljoin
import requests
import json

from .exceptions import ServiceNotFound, InvalidProfile, InvalidToken
from .config import Config, save_config
from .utils import root_url_from_api_key, get_access_token, decode_token, host_from_url

SERVICES_PATH = Path(__file__).parent.joinpath("services")
SERVICES = ["query", "queryserver"]
DEFAULT_CLIENT_ID = "api-key-client"

log = logging.getLogger()

cfg = Config()


def get_api_key(
    host: str, username: str, password: str, realm: str = "wuxinextcode.com"
) -> str:
    """
    Authenticate with keycloak server and return an API key.

    Assumes client api-key-client.

    :param host: The URI of the service. e.g. host.wuxinextcode.com
    :param username: Username of the keycloak user which is authenticating
    :param password: Password
    :param realm: The realm with which to authenticate (optional)
    :returns: API Key which can be used in subsequent calls to Client()
    :raises: InvalidToken
    """
    body = {
        "grant_type": "password",
        "client_id": DEFAULT_CLIENT_ID,
        "password": password,
        "username": username,
        "scope": "offline_access",
    }
    host = host_from_url(host)
    url = urljoin(host, "auth", "realms", realm, "protocol/openid-connect/token")
    log.info("Using auth server '%s'", url)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    log.debug("Calling POST %s with headers %s and body %s", url, headers, body)
    resp = requests.post(url, headers=headers, data=body)
    log.debug("Response (%s): %s", resp.status_code, resp.text)
    if resp.status_code != 200:
        try:
            description = resp.json()["error_description"]
        except Exception:
            description = resp.text
        raise InvalidToken(f"Error logging in: {description}") from None

    api_key = resp.json()["refresh_token"]
    return api_key


def get_service(
    service_name: str,
    api_key: Optional[str] = None,
    profile: Optional[str] = None,
    **kw,
):
    """
    Helper method which returns a service handle and creates a client object automatically

    :param api_key: api key to use for this client
    :param profile: name of a saved profile to use with this client
    :raises: InvalidProfile, ServiceNotFound
    """
    client = Client(api_key, profile)
    return client.service(service_name, **kw)


class Profile:

    profile_name = None
    content = None

    def __init__(
        self, profile_name: Optional[str] = None, content: Optional[Dict] = None
    ) -> None:
        if profile_name:
            self.profile_name = profile_name
            self.content = cfg.get("profiles")[self.profile_name]
        else:
            self.profile_name = None
            self.content = content

    def __getattr__(self, name):
        if name in self.content:
            return self.content[name]
        return None

    def __setattr__(self, name, value):
        if name in ("profile_name", "content"):
            super(Profile, self).__setattr__(name, value)
        else:
            self.content[name] = value
            if self.profile_name:
                save_config()


class Client:
    """A base client object from which to access various services

    :param api_key: api key to use for this client
    :param profile: name of a saved profile to use with this client
    :param root_url: override the URL of the server root. e.g. https://server.wuxinextcode.com
    :raises: InvalidProfile

    Order of precedence:
    1) passed in 'profile'
    2) passed in 'api_key'
    3) NEXTCODE_PROFILE from environment
    3) GOR_API_KEY from environment"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        profile: Optional[str] = None,
        root_url: Optional[str] = None,
    ) -> None:
        # if no named profile or api key is passed in
        if not profile and not api_key:
            # find the default profile, if any
            if os.environ.get("NEXTCODE_PROFILE"):
                profile = os.environ["NEXTCODE_PROFILE"]
                log.info("Using profile '%s' from environment", profile)
            else:
                profile = cfg.get("default_profile")
                if profile:
                    log.info("Using default profile '%s' from config", profile)

        self.profile_name = profile

        # if we have a profile we will load it from the config
        if self.profile_name:
            log.info(
                "Initializing client with profile '%s'. Available profiles: %s",
                self.profile_name,
                self.available_profiles(),
            )
            if self.profile_name not in cfg.get("profiles"):
                raise InvalidProfile(
                    "The config profile (%s) could not be found" % profile
                )
            self.profile = Profile(self.profile_name)
        else:
            # if there is no profile there needs to be configuration set in the
            # environment, in which case we create an ephemeral profile, not
            # backed up by disk.
            api_key = api_key or os.environ.get("GOR_API_KEY")
            #if not api_key:
            #    raise InvalidProfile(
            #        "No profile specified and GOR_API_KEY not set in environment"
            #    )
            root_url = root_url or os.environ.get("NEXTCODE_ROOT_URL")
            if not root_url:
                root_url = root_url_from_api_key(api_key)
            self.profile = Profile(content={"api_key": api_key, "root_url": root_url})

    def service(self, service_name: str, **kw):
        """
        Retrieve an instance to a service.

        :param service_name: The name of the service

        Available services can be listed by calling class method `available_services`.
        """
        for (_, name, _) in pkgutil.iter_modules([str(SERVICES_PATH)]):
            if name == service_name:
                log.debug("Importing service %s", name)
                module = import_module("..services.{}".format(name), __name__)
                svc = module.Service(client=self, **kw)  # type: ignore
                return svc
        raise ServiceNotFound()

    def get_access_token(self, decode: bool = False) -> Union[Dict, str]:
        """Retrieve the JWT access token that is generated from the current api key.

        :param decode: Decode the token and return a dictionary instead of the raw string
        :raises: InvalidToken

        Example usage:

        >>> client = nextcode.Client(api_key="xxx.yyy.zzz")
        >>> print(client.get_access_token())
        "iii.jjj.kkk"

        >>> client = nextcode.Client(api_key="xxx.yyy.zzz")
        >>> print(client.get_access_token(decode=True))
        {"jti": "...", ...}

        """
        token = os.environ.get('NEXTCODE_ACCESS_TOKEN') or get_access_token(self.profile.api_key)
        if decode:
            return decode_token(token)
        else:
            return token

    @classmethod
    def available_services(cls) -> List[str]:
        """List services that can be intantiated via an client object client.service(`service`)"""
        ret = []
        for (_, name, _) in pkgutil.iter_modules([str(SERVICES_PATH)]):
            ret.append(name)
        return ret

    @classmethod
    def available_profiles(cls) -> List[str]:
        """List profiles that that are installed into the system and can be used
        with the constructor client.Client()
        """
        return list(cfg.get("profiles"))

    def __repr__(self) -> str:
        return "<Client {} | {}>".format(self.profile_name, self.profile.root_url)

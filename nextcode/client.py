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

from .exceptions import ServiceNotFound, InvalidProfile
from .config import Config
from .utils import root_url_from_api_key, get_access_token, decode_token

SERVICES_PATH = Path(__file__).parent.joinpath("services")
SERVICES = ["query"]

log = logging.getLogger()

cfg = Config()


def get_service(
    service_name: str,
    api_key: Optional[str] = None,
    profile: Optional[str] = None,
    **kw
):
    """
    Helper method which returns a service handle and creates a client object automatically

    :param api_key: api key to use for this client
    :param profile: name of a saved profile to use with this client
    :raises: InvalidProfile, ServiceNotFound
    """
    client = Client(api_key, profile)
    return client.service(service_name, **kw)


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
    ):
        # if no named profile or api key is passed in
        if not profile and not api_key:
            # find the default profile, if any
            if os.environ.get("NEXTCODE_PROFILE"):
                profile = os.environ["NEXTCODE_PROFILE"]
            else:
                profile = cfg.get("default_profile")

        self.profile_name = profile

        # if there is no profile we need to have configuration information in env
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
            self.profile = cfg.get("profiles")[self.profile_name]
        else:
            api_key = api_key or os.environ.get("GOR_API_KEY")
            if not api_key:
                raise InvalidProfile(
                    "No profile specified and GOR_API_KEY not set in environment"
                )
            root_url = root_url or os.environ.get("NEXTCODE_ROOT_URL")
            if not root_url:
                root_url = root_url_from_api_key(api_key)
            self.profile = {"api_key": api_key, "root_url": root_url}

    def service(self, service_name: str, **kw):
        """
        Retrieve an instance to a service.

        :param service_name: The name of the service

        Available services can be listed by calling class method `available_services`.
        """
        for (_, name, _) in pkgutil.iter_modules([str(SERVICES_PATH)]):
            if name == service_name:
                module = import_module("..services.{}".format(name), __name__)
                svc = module.Service(client=self, **kw)  # type: ignore
                return svc
        else:
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
        token = get_access_token(self.profile["api_key"])
        if decode:
            return decode_token(token)
        else:
            return token

    @classmethod
    def available_services(self) -> List[str]:
        """List services that can be intantiated via an client object client.service(`service`)
        """
        ret = []
        for (_, name, _) in pkgutil.iter_modules([str(SERVICES_PATH)]):
            ret.append(name)
        return ret

    @classmethod
    def available_profiles(self) -> List[str]:
        """List profiles that that are installed into the system and can be used
        with the constructor client.Client()
        """
        return list(cfg.get("profiles"))

    def __repr__(self) -> str:
        return "<Client {} | {}>".format(self.profile_name, self.profile["root_url"])

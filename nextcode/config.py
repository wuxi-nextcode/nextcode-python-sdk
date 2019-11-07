"""
config
~~~~~~~~~~
Configuration, caching and profile management for nextcode sdk.

"""

import os
import logging
import yaml
import json
import copy
from pathlib import Path
from typing import Dict, Tuple, Sequence, Optional

from .utils import root_url_from_api_key
from .exceptions import InvalidProfile

root_config_folder = Path(os.path.expanduser("~/.nextcode"))

log = logging.getLogger(__name__)

DEFAULT_PROFILE_NAME = "default"


def load_cache(name: str) -> Optional[Dict]:
    if os.environ.get("NEXTCODE_DISABLE_CACHE"):
        return None
    cache_file = root_config_folder.joinpath("cache", name + ".cache")
    try:
        contents = json.load(cache_file.open("r"))
        log.info("Loaded contents from cache %s", cache_file)
        return contents
    except FileNotFoundError:
        pass
    except Exception:
        log.exception("Could not load from cache %s" % cache_file)
    return None


def save_cache(name: str, contents: Dict) -> None:
    if os.environ.get("NEXTCODE_DISABLE_CACHE"):
        return
    try:
        cache_folder = root_config_folder.joinpath("cache")
        os.makedirs(cache_folder, exist_ok=True)
        cache_file = root_config_folder.joinpath(cache_folder, name + ".cache")
        json.dump(contents, cache_file.open("w"))
        log.info("Dumped contents into cache %s", cache_file)
    except Exception:
        log.exception("Could not save cache %s" % cache_file)


class Config:
    """
    Borg pattern Config class see:
    http://code.activestate.com/recipes/66531-singleton-we-dont-need-no-stinkin-singleton-the-bo/

    Example usage:

    >>> config = Config({'my': 'config'})
    """

    shared_state: Dict = {}
    data: Dict = {}

    def __init__(self, data: Optional[Dict] = None):
        self.__dict__ = self.shared_state
        self.set(data)

    def dict(self) -> Dict:
        return self.data

    def set(self, data: Optional[Dict]) -> None:
        if data is None:
            data = {}
        self.data.update(data)

    def get(self, key: str, default=None):
        return self.data.get(key, default)


def _load_config() -> Dict:
    config_file = root_config_folder.joinpath("config.yaml")
    try:
        content = yaml.safe_load(config_file.open())
        if not isinstance(content, dict):
            raise Exception("Invalid config")
        return content
    except Exception:
        log.info("Config file not found or invalid")
    return {}


def save_config() -> None:
    config = Config()
    config_file = root_config_folder.joinpath("config.yaml")
    log.debug(
        "Saving config with %s profiles to %s", len(config.get("profiles")), config_file
    )
    os.makedirs(root_config_folder, exist_ok=True)
    yaml.safe_dump(config.dict(), config_file.open("w"))


def _init_config() -> None:
    config = Config()
    config.set({"default_profile": None, "profiles": []})
    content = _load_config()
    if "profiles" not in content:
        content["profiles"] = {}
    for name, profile in content["profiles"].copy().items():
        profile = _prepare_profile(profile)
        if not profile:
            log.info("Profile '%s' is invalid and will be ignored", name)
            del content["profiles"][name]

    config.set(content)


def _prepare_profile(profile):
    ret = {}
    try:
        ret["api_key"] = profile.get("api_key")
        ret["root_url"] = root_url_from_api_key(ret["api_key"])
        if profile.get("root_url"):
            ret["root_url"] = profile["root_url"]
    except Exception:
        return None
    return ret


def create_profile(name: str, api_key: str, root_url: Optional[str] = None) -> None:
    """
    Create a new profile from api key and persist to disk

    :param name: Unique name of the profile for referencing later
    :param api_key: API Key from keycloak for the server
    :param root_url: root url of the server. If not set, the url from the api key is used
    :raises: InvalidProfile

    """
    profile = _prepare_profile({"api_key": api_key, "root_url": root_url})
    if not profile:
        raise InvalidProfile("Profile does not contain a valid api_key")
    config = Config()
    profiles = config.get("profiles")
    profiles[name] = profile
    config.set({"profiles": profiles})
    save_config()


def set_default_profile(name: str) -> None:
    """
    Set a named profile as the default one if no profile is specified or GOR_API_KEY is not set

    :param name: Name of the profile
    :raises: InvalidProfile
    """
    config = Config()
    if name not in config.get("profiles"):
        raise InvalidProfile("Profile does not exist")
    config.set({"default_profile": name})
    save_config()


_init_config()

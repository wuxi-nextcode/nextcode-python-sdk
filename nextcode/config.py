"""
config
~~~~~~~~~~
Configuration, caching and profile management for nextcode sdk.

"""

import os
import logging
import yaml
import json
import time
from pathlib import Path
from typing import Dict, Tuple, Sequence, Optional
import shutil

from .utils import root_url_from_api_key
from .exceptions import InvalidProfile

root_config_folder = Path(os.path.expanduser("~/.nextcode"))

log = logging.getLogger(__name__)

DEFAULT_PROFILE_NAME = "default"
CACHE_SECONDS = 600


def load_cache(name: str) -> Optional[Dict]:
    """
    Load a dictionary from disk cache by name.

    The file is found in ~/.nextcode/cache/[name].cache and is assumed to be a
    dictionary in json format.

    If NEXTCODE_DISABLE_CACHE environment variable is non-zero this method does nothing
    """
    if os.environ.get("NEXTCODE_DISABLE_CACHE"):
        return None
    cache_file = root_config_folder.joinpath("cache", name + ".cache")
    try:
        file_age = time.time() - os.path.getmtime(cache_file)
        if file_age > CACHE_SECONDS:
            log.info("Cache is too old, removing it.")
            os.remove(cache_file)
            raise FileNotFoundError

        contents = json.load(cache_file.open("r"))
        log.info("Loaded contents from cache %s", cache_file)
        return contents
    except FileNotFoundError:
        pass
    except Exception:
        log.exception("Could not load from cache %s", cache_file)
    return None


def save_cache(name: str, contents: Dict) -> None:
    if os.environ.get("NEXTCODE_DISABLE_CACHE"):
        return
    try:
        cache_folder = root_config_folder.joinpath("cache")
        os.makedirs(cache_folder, exist_ok=True)
        cache_file = root_config_folder.joinpath(cache_folder, name + ".cache")
        json.dump(contents, cache_file.open("w"), default=str)
        log.info("Dumped contents into cache %s", cache_file)
    except Exception:
        log.exception("Could not save cache %s", cache_file)


def clear_cache() -> None:
    cache_folder = root_config_folder.joinpath("cache")
    try:
        shutil.rmtree(cache_folder)
    except FileNotFoundError:
        pass


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
    except Exception as ex:
        log.info("Config file not found or invalid: %s", ex)
    return {}


def save_config() -> None:
    config = Config()
    config_filename = root_config_folder.joinpath("config.yaml")
    os.makedirs(root_config_folder, exist_ok=True)
    with config_filename.open("w") as conf_file:
        yaml.safe_dump(config.dict(), conf_file)


def _init_config() -> None:
    config = Config()
    config.set({"default_profile": None, "profiles": []})
    content = _load_config()
    if "profiles" not in content:
        content["profiles"] = {}
    for name, profile in content["profiles"].copy().items():
        profile = _prepare_profile(profile)
        if not profile:
            log.warning("Profile '%s' is invalid and will be ignored", name)
            del content["profiles"][name]

    config.set(content)


def _prepare_profile(profile):
    ret = {}
    try:
        ret["api_key"] = profile.get("api_key")
        if profile.get("skip_auth"):
            ret["skip_auth"] = profile.get("skip_auth")
        if profile.get("root_url"):
            ret["root_url"] = profile["root_url"]
        else:
            ret["root_url"] = root_url_from_api_key(ret["api_key"])
    except Exception:
        return None
    return ret


def create_profile(
    name: str, api_key: str, root_url: Optional[str] = None, skip_auth: bool = False
) -> None:
    """
    Create a new profile from api key and persist to disk

    :param name: Unique name of the profile for referencing later
    :param api_key: API Key from keycloak for the server
    :param root_url: root url of the server. If not set, the url from the api key is used
    :param skip_auth: Do not use authentication (local development)
    :raises: InvalidProfile

    """
    contents: Dict = {"api_key": api_key, "root_url": root_url}
    if skip_auth:
        contents["skip_auth"] = True
    profile = _prepare_profile(contents)
    if not profile:
        raise InvalidProfile("Profile does not contain a valid api_key")
    config = Config()
    profiles = config.get("profiles")
    profiles[name] = profile
    config.set({"profiles": profiles})
    save_config()


def delete_profile(name: str) -> None:
    config = Config()
    profiles = get_profiles()
    if name not in profiles:
        raise InvalidProfile("Profile does not exist")
    if config.get("default_profile") == name:
        config.set({"default_profile": None})
    del profiles[name]
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


def get_profiles() -> Dict:
    config = Config()
    return config.get("profiles")


def get_default_profile() -> Optional[str]:
    config = Config()
    return os.environ.get("NEXTCODE_PROFILE") or config.get("default_profile")


def get_config() -> Dict:
    config = Config()
    return config.data


def get_profile_config() -> Dict:
    config = Config()
    try:
        return config.data["profiles"][get_default_profile()]
    except KeyError:
        raise InvalidProfile("No current profile found")


_init_config()

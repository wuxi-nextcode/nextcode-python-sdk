"""
session
~~~~~~~~~~
Service Session, low-level object for communicating with RESTFul services.
"""

import requests
import requests.utils
from requests import codes
from os import environ
import copy
import json
import platform
import time
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry  # pylint: disable=E0401
from hashlib import sha1
from typing import Dict

from . import __version__
from .exceptions import ServerError
from .utils import check_resp_error, get_access_token
from .config import Config, load_cache, save_cache

log = logging.getLogger(__name__)

config = Config()


class ServiceSession(requests.Session):
    """
    A wrapped requests session object with base_url and exported endpoints
    from nextcode service api's
    """

    def __init__(self, api_name, url_base, api_key, *args, **kwargs):
        super(ServiceSession, self).__init__(*args, **kwargs)
        # retry idempotent methods up to 5 times
        if not environ.get("NEXTCODE_DISABLE_RETRY"):
            retries = 5
            backoff_factor = 0.5
            status_forcelist = (500, 502, 503, 504)
            retry = Retry(
                total=retries,
                read=retries,
                connect=retries,
                backoff_factor=backoff_factor,
                status_forcelist=status_forcelist,
            )
            adapter = HTTPAdapter(max_retries=retry)
            self.mount("http://", adapter)
            self.mount("https://", adapter)

        self.root_info = {}
        self.endpoints = {}
        self.token = None
        self.api_name = api_name
        self.url_base = url_base
        self.api_key = api_key

        if environ.get("GOR_API_KEY"):
            log.info("Overriding api key from environment")
            self.api_key = environ["GOR_API_KEY"]

        self.cache_name = sha1(
            (self.api_name + self.url_base + self.api_key).encode()
        ).hexdigest()
        self.user_agent = "Nextcode-SDK/%s Python/%s %s/%s" % (
            __version__,
            platform.python_version(),
            platform.system(),
            platform.release(),
        )

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

        if not self._load():
            self._initialize()

        self.endpoints = self.root_info.get("endpoints")

    def _initialize(self) -> None:
        self.token = get_access_token(self.api_key)
        self.headers["Authorization"] = "Bearer {}".format(self.token)
        self.root_info = self.fetch_root_info()
        self._save()

    def _save(self) -> None:
        contents = {"token": self.token, "root_info": self.root_info}
        save_cache(self.cache_name, contents)

    def _load(self) -> bool:
        contents = load_cache(self.cache_name)
        if not contents:
            return False
        self.token = contents["token"]
        self.root_info = contents["root_info"]
        self.headers["Authorization"] = "Bearer {}".format(self.token)
        return True

    def _do_request(self, method, retry=True, *args, **kwargs):

        # method: GET
        old_content_type = self.headers["Content-Type"]

        if method == "get":
            # ! Temporary hack: Remove the application/json content-type header for GET's
            del self.headers["Content-Type"]

        try:
            st = time.time()
            response = getattr(super(ServiceSession, self), method)(*args, **kwargs)
            diff = time.time() - st
        finally:
            self.headers["Content-Type"] = old_content_type

        # Manage response from the server
        log.info(
            "%s %s returned %s in %.3f sec"
            % (method.upper(), args[0], response.status_code, diff)
        )
        if response.status_code == codes.unauthorized:
            if retry:
                log.debug("Status code %s, retrying once..." % response.status_code)
                self._initialize()
                log.info(
                    "Tokens have been updated. Now calling _do_request one more..."
                )
                return self._do_request(method, False, *args, **kwargs)
            else:
                log.error("Received unauthorized in retry: %s", response.text)

        check_resp_error(response)
        return response

    def get(self, *args, **kw):
        return self._do_request("get", True, *args, **kw)

    def put(self, *args, **kw):
        return self._do_request("put", True, *args, **kw)

    def post(self, *args, **kw):
        return self._do_request("post", True, *args, **kw)

    def delete(self, *args, **kw):
        return self._do_request("delete", True, *args, **kw)

    def fetch_root_info(self) -> Dict:
        log.debug(
            "fetch_root_info(): url_base: {0}, headers: {1}".format(
                self.url_base, self.headers
            )
        )

        try:
            r = self.get(self.url_base)
        except requests.exceptions.ConnectionError:
            raise ServerError("Could not reach server %s" % self.url_base) from None

        if r.headers["Content-Type"] != "application/json":
            raise ServerError(
                "Unexpected response: %s" % r.text, url=self.url_base
            ) from None

        return r.json()

    def url_from_endpoint(self, endpoint: str) -> str:
        try:
            return self.endpoints[endpoint]
        except KeyError:
            raise ServerError(
                "Endpoint '%s' is not exported by '%s'.\nAvailable endpoints are %s"
                % (endpoint, self.url_base, ", ".join(self.endpoints.keys()))
            )

    def request(self, method, url, **kwargs):
        log.debug("Calling %s %s", method, url)
        stripped_headers = copy.copy(self.headers)
        stripped_headers["Authorization"] = "Bearer ***"
        log.debug("Headers: %s" % json.dumps(stripped_headers))
        if "json" in kwargs:
            log.debug("Payload:\n%s" % json.dumps(kwargs["json"], indent=4))
        return super(ServiceSession, self).request(method, url, **kwargs)

    def links(self, resp: Dict) -> Dict:
        return resp.get("links", {})

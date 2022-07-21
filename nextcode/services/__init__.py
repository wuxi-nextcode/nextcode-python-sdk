"""
Base Service
------------------
Common service functionality

"""
import os
from urllib.parse import urljoin
from typing import Optional, Dict
import logging
from ..session import ServiceSession
from ..exceptions import InvalidProfile, ServerError

log = logging.getLogger(__file__)


class BaseService:
    """
    Common functionality between all services
    """

    def __init__(self, client, service_path, *args, **kwargs):
        self.client = client

        service_path = os.environ.get("NEXTCODE_SERVICE_PATH", service_path)
        root_url = client.profile.root_url
        if not root_url:
            raise InvalidProfile("Profile is not configured")

        # ! explicit temporary hack
        if os.environ.get("SERVICE_IN_ROOT"):
            service_path = "/"

        self.service_path = service_path
        self.base_url = urljoin(root_url, service_path)
        api_key = client.profile.api_key
        if client.profile.skip_auth:
            api_key = None
        self.session = ServiceSession(self.base_url, api_key)

    def __repr__(self):
        return f"<Service {self.service_name} {self.version} | {self.base_url}>"

    def healthy(self) -> bool:
        """
        Is the service healthy?
        """
        try:
            self.session.get(self.session.endpoints["health"])
            return True
        except ServerError:
            return False

    def status(self, force: Optional[bool] = False) -> Dict:
        """
        Service information from the root endpoint
        """
        if force:
            self.session.fetch_root_info()
        ret = {
            k: v
            for k, v in self.session.root_info.items()
            if k in ("build_info", "app_info", "service_name")
        }
        # include the root endpoint for good measure
        ret["root"] = self.session.root_info.get("endpoints", {}).get("root")
        return ret

    @property
    def service_name(self) -> str:
        return self.session.root_info["service_name"]

    @property
    def version(self) -> str:
        return self.session.root_info["build_info"]["version"]

    @property
    def build_info(self) -> str:
        return self.session.root_info["build_info"]

    @property
    def app_info(self) -> Dict:
        return self.session.root_info.get("app_info")

    @property
    def current_user(self) -> Dict:
        """
        User JWT decoded by the service
        """
        return self.session.root_info.get("current_user") or {}

    @property
    def endpoints(self) -> Dict:
        """
        Dictionary of name: endpoint url for exposed endpoints in the service
        """
        return self.session.endpoints

    def openapi_spec(self) -> Dict:
        """
        Raw openapi spec for the service
        """
        return self.session.get(self.session.url_from_endpoint("documentation")).json()

"""
Base Service
------------------
Common service functionality

"""

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
        root_url = client.profile.get("root_url")
        if not root_url:
            raise InvalidProfile("Profile is not configured")
        self.base_url = urljoin(root_url, service_path)
        self.session = ServiceSession(
            "queryapi", self.base_url, client.profile["api_key"]
        )

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
    def current_user(self) -> Dict:
        """
        User JWT decoded by the service
        """
        return self.session.root_info.get("current_user")

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

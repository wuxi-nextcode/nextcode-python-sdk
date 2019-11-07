"""
Workflow Service
------------------
Service object for interfacing with the Workflow service API

"""

from urllib.parse import urljoin
import logging
import os
from typing import Dict, Tuple, Sequence

from ...client import Client
from ...services import BaseService
from ...session import ServiceSession
from ...exceptions import InvalidProfile, ServerError

SERVICE_PATH = "/workflow"

log = logging.getLogger(__file__)


class Service(BaseService):
    def __init__(self, client: Client, *args, **kwargs) -> None:
        path = os.environ.get("NEXTCODE_SERVICE_PATH", SERVICE_PATH)
        # ! temporary hack
        if "localhost" in client.profile["root_url"]:
            path = "/"
        super(Service, self).__init__(client, path, *args, **kwargs)

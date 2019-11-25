"""
Workflow Service
------------------
Service object for interfacing with the Workflow service API

"""

import logging

from ...client import Client
from ...services import BaseService

SERVICE_PATH = "pipelines-service"

log = logging.getLogger(__file__)


class Service(BaseService):
    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)

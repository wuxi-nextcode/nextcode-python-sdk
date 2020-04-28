"""
Service class
------------------
Service object for interfacing with the Pipelines service API

"""

import logging

from ...client import Client
from ...services import BaseService

RUNNING_STATUSES = ["QUEUED", "LAUNCHING", "INITIALIZING", "RUNNING"]
FAILED_STATUSES = ["FAILED", "TERMINATED"]
FINISHED_STATUSES = ["FINISHED", "CANCELLED"]
ALL_STATUSES = RUNNING_STATUSES + FAILED_STATUSES + FINISHED_STATUSES + ["ALL"]

SERVICE_PATH = "pipelines-service"

log = logging.getLogger(__file__)


class Service(BaseService):
    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)

"""
Phenotype
------------------

Representation of a serverside phenotype
"""

import json
import datetime
import dateutil
import time
import logging
from typing import Callable, Union, Optional, Dict, List

from .exceptions import PhenotypeError
from ...exceptions import ServerError
from ...session import ServiceSession

log = logging.getLogger(__name__)


class Phenotype:
    def __init__(self, session: ServiceSession, data: Dict):
        self.session = session
        self.data = data
        # deep_dateparse(self.data)
        self.links = data["links"]

    def __getattr__(self, name):
        try:
            val = self.data[name]
        except KeyError:
            raise AttributeError

        try:
            val = dateutil.parser.parse(val)
        except Exception:
            pass

        return val

    def __repr__(self) -> str:
        return f"<Phenotype {self.name} in project {self.project_key}>"

    def delete(self):
        """
        Delete a phenotype, including all data from a project

        :raises: ServerError
        """
        _ = self.session.delete(self.links["self"])

    def upload(self, data: List):
        """
        Upload phenotype data

        :raises: ServerError
        """
        if not isinstance(data, list):
            raise TypeError("data must be a list")
        url = self.links["upload"]

        content = {"data": data}
        resp = self.session.post(url, json=content)
        return resp.json()

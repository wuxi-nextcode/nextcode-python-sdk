"""
Phenotype
------------------

Representation of a serverside phenotype.


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
    """
    A local object representing a phenotype response from the phenotype
    catalog service.

    Note that most of the attributes come directly from the phenotype
    serverside response and are therefore not documented directly here.
    Please refer to the API Documentation for the phenotype catalog service.

    To intraspect the data you can also call `phenotype.data.keys()`. Each key
    in the `data` dict is exposed as an attribute with intelligent type casting.
    """

    def __init__(self, session: ServiceSession, data: Dict):
        self.session = session
        self.data = data
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

        :raises: `ServerError` if the phenotype could not be deleted
        """
        _ = self.session.delete(self.links["self"])

    def upload(self, data: List):
        """
        Upload phenotype data

        The data is expected to be a list of lists.
        e.g. `phenotype.upload([['a'], ['b']]).
        The `result_type` of the phenotype dictates
        if each sublist should contain one or two items.

        :raises: `ServerError` if there was a problem uploading
        """
        if not isinstance(data, list):
            raise TypeError("data must be a list")
        url = self.links["upload"]

        content = {"data": data}
        resp = self.session.post(url, json=content)
        return resp.json()

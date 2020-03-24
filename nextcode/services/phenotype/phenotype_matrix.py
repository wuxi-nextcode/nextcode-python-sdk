"""
Phenotype Matrix
------------------

A builder that allows the user to set up a
request for a phenotype matrix.

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
from .. import BaseService

log = logging.getLogger(__name__)


class PhenotypeMatrix:
    """

    """

    def __init__(self, service: BaseService, base: str):
        self.service = service
        self.base = base
        self.phenotypes: Dict[str, Dict[str, Optional[str]]] = {}

    def add_phenotype(
        self,
        name: str,
        missing_value: Optional[str] = None,
        label: Optional[str] = None,
    ) -> None:
        self.phenotypes[name] = {
            "name": name,
            "missing_value": missing_value,
            "label": label,
        }

    def add_phenotypes(
        self, names: List[str], missing_value: Optional[str] = None
    ) -> None:
        for name in names:
            self.add_phenotype(name, missing_value=missing_value)

    def remove_phenotype(self, name: str) -> None:
        try:
            del self.phenotypes[name]
        except KeyError:
            pass

    def get_data(self):
        if not self.base or not self.phenotypes:
            raise PhenotypeError(
                "Matrix request has not been initialized. Use add_phenotype(s) to begin."
            )
        phenotypes_list = list(self.phenotypes.values())
        content = {
            "base": self.base,
            "phenotypes": phenotypes_list,
        }
        url = self.service.links["get_phenotype_matrix"]
        resp = self.service.session.post(url, json=content)
        resp.raise_for_status()
        print(resp.text)

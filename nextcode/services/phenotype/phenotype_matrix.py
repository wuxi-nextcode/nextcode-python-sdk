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
from io import StringIO

from .exceptions import PhenotypeError
from ...exceptions import ServerError
from ...session import ServiceSession

log = logging.getLogger(__name__)


class PhenotypeMatrix:
    """
    A builder to create a phenotype matrix request.

    You start by using add_phenotype() or add_phenotypes()
    to add a list of phenotypes and then call get_data()
    to retrieve the phenotype matrix from the server.
    """

    def __init__(self, session: ServiceSession, base: str = None, project_name: str = None):
        self.session = session
        self.base = base
        self.phenotypes: Dict[str, Dict[str, Optional[str]]] = {}
        self.project_name = project_name

    def add_phenotype(
        self,
        name: str,
        missing_value: Optional[str] = None,
        label: Optional[str] = None,
    ) -> None:
        """
        Add a new phenotype to the matrix request.

        :param name: Phenotype name
        :param missing_value: The string to substitute for a missing value in the data
        :param label: Optional label to apply to the phenotype
        """
        self.phenotypes[name] = {
            "name": name,
            "missing_value": missing_value,
            "label": label,
        }

    def add_phenotypes(
        self, names: List[str], missing_value: Optional[str] = None
    ) -> None:
        """
        Add a list of phenotypes to the matrix request.

        :param names: List of phenotype names
        :param missing_value: The string to substitute for a missing value in the data
        """
        for name in names:
            self.add_phenotype(name, missing_value=missing_value)

    def remove_phenotype(self, name: str) -> None:
        """
        Remove a phenotype from the matrix request.

        Does not fail if the phenotype is not present.

        :param name: Phenotype name
        """
        try:
            del self.phenotypes[name]
        except KeyError:
            pass

    def get_data(self, dataframe: bool = True) -> object:
        """
        Retrieve a phenotype matrix from the server.

        Can be called after phenotypes have been added to the request.

        :param dataframe: If set, return results as a pandas dataframe (default True)
        :raises: `PhenotypeError` if the request is not ready or pandas is not installed.
        :raises: `ServerError` if phenotypes are not found on the server
        """
        if not self.phenotypes:
            raise PhenotypeError(
                "Matrix request has not been initialized. Use add_phenotype(s) to begin."
            )
        phenotypes_list = list(self.phenotypes.values())
        content = {
            "base": self.base,
            "phenotypes": phenotypes_list,
        }
        url = self.session.url_from_endpoint("get_phenotype_matrix").format(project_name = self.project_name)
        resp = self.session.post(url, json=content)
        resp.raise_for_status()
        tsv_data = resp.text
        if not dataframe:
            return tsv_data

        try:
            import pandas as pd
        except ModuleNotFoundError:
            raise PhenotypeError("Pandas library is not installed")

        if not tsv_data:
            return pd.DataFrame()
        df = pd.read_csv(StringIO(tsv_data), delimiter="\t")  # type: ignore
        return df

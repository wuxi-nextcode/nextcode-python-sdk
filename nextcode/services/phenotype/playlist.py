"""
Playlist
------------------

A playlist is a collection of phenotypes that have 
been grouped together by a user in the Phenotype Catalog.


"""

import json
import datetime
import dateutil
import time
import logging
from posixpath import join as urljoin
from typing import Callable, Union, Optional, Dict, List

from .exceptions import PhenotypeError
from .phenotype_matrix import PhenotypeMatrix
from ...exceptions import ServerError
from ...session import ServiceSession

log = logging.getLogger(__name__)


class Playlist:
    """
    A local object representing a playlist response from the phenotype
    catalog service.

    Please refer to the API Documentation for the phenotype catalog service.

    In addition to the ones documented here, this object has at least these attributes:

    * name - Playlist name
    * description - Textual description of this phenotype
    * created_at - Timestamp when the playlist was first created
    * updated_at - Timestamp when the playlist was last updated
    * created_by - Username who created the phenotype
    * versions - List of data versions available in this phenotype

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
        return f"<Playlist {self.name} in project {self.project_key}>"

    def delete(self):
        """
        Delete a playlist from a project

        :raises: `ServerError` if the phenotype could not be deleted
        """
        _ = self.session.delete(self.links["self"])
        self.refresh()

    def refresh(self):
        """
        Refresh local playlist object from server
        """
        resp = self.session.get(self.links["self"])
        data = resp.json()["playlist"]
        self.data = data
        self.links = data["links"]

    def add_phenotype(self, name: str):
        """
        Add a phenotype to a playlist

        :param name: Unique (lowercase) phenotype name in the project
        """
        url = urljoin(self.links["self"], "phenotypes")
        content = {"name": name}
        _ = self.session.post(url, json=content)
        self.refresh()
        self.get_info()

    def add_phenotypes(self, name: Union[str,List[str]]):
        """
        Add phenotypes to a playlist

        :param name: A list of unique (lowercase) phenotype name in the project
        """
        name = [name] if isinstance(name, str) else name
        for pheno in name:
            self.add_phenotype(pheno)
        self.get_info()

    def delete_phenotype(self, name: str):
        """
        Delete a phenotype from a playlist

        :raises: `ServerError` if the phenotype could not be deleted
        """
        url = urljoin(self.links["self"], "phenotypes", name)
        _ = self.session.delete(url)
        self.refresh()
        self.get_info()

    def get_info(self):
        """
        Get playlist info
        """
        return self.data

    def list_phenotypes(self):
        """
        List phenotypes in playlist
        """
        return [phenotype['name'] for phenotype in self.get_info()['phenotypes']]

    def get_data(self, missing_value=None):
        """
        Retrieve phenotype data from the server.
        """
        matrix = PhenotypeMatrix(self.session, project_name = self.data["project_key"])
        matrix.add_phenotypes(names=self.list_phenotypes(), missing_value=missing_value)
        self.df = matrix.get_data()
        return self.df

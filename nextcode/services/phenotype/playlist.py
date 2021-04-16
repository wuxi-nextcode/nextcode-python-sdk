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

    def add_phenotype(self, name: str):
        """
        Add a phenotype to a playlist
        """
        url = url = urljoin(self.links["self"], "phenotypes")
        content = {"name": name}
        _ = self.session.post(url, json=content)

        self.get_data()

    def get_data(self):
        return self.data

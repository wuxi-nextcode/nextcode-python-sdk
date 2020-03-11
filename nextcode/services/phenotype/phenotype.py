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

    In addition to the ones documented here, this object has at least these attributes:

    * name - Phenotype name
    * description - Textual description of this phenotype
    * result_type - Type of result. Cannot be changed. One of SET, QT, CATEGORY
    * created_at - Timestamp when the phenotype was first created
    * updated_at - Timestamp when the phenotype was last updated
    * created_by - Username who created the phenotype
    * versions - List of data versions available in this phenotype

    To intraspect the data you can call `phenotype.data.keys()`. Each key
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

    def refresh(self):
        """
        Refresh the local cache
        """
        resp = self.session.get(self.links["self"])
        data = resp.json()
        self.data = data["phenotype"]

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
        e.g. `phenotype.upload([['a'], ['b']])`.
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

    def update_description(self, description: str):
        """
        Update the phenotype with a new description
        """
        url = self.links["self"]
        content = {"description": description}
        _ = self.session.patch(url, json=content)
        self.refresh()

    def set_tags(self, tags: List[str]):
        """
        Set the tag list for this phenotype, overriding all previous tags
        """
        url = self.links["self"]
        content = {"tag_list": tags}
        self.session.patch(url, json=content)
        self.refresh()

    def get_tags(self):
        """
        Retrieve all tags for this phenotype
        """
        return self.tag_list

    def add_tag(self, tag: str):
        """
        Add a new tag to this phenotype.

        :raises: `PhenotypeError` if the tag is already set on this phenotype
        """
        url = self.links["self"]
        tags = set(self.tag_list)
        if tag in tags:
            raise PhenotypeError(f"Tag {tag} already exists on this phenotype")

        tags.add(tag)

        content = {"tag_list": list(tags)}
        self.session.patch(url, json=content)
        self.refresh()

    def delete_tag(self, tag: str):
        """
        Delete a tag from the phenotype.

        :raises: `PhenotypeError` if the tag does not exist
        """
        url = self.links["self"]
        tags = set(self.tag_list)
        try:
            tags.remove(tag)
        except KeyError:
            raise PhenotypeError(f"Tag {tag} does not exist on this phenotype")

        content = {"tag_list": list(tags)}
        self.session.patch(url, json=content)
        self.refresh()

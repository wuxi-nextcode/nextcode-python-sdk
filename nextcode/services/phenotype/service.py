"""
Service class
------------------
Service object for interfacing with the Phenotype Archive API

"""

import logging
from posixpath import join as urljoin
from requests import codes
from typing import Optional, List, Union, Dict

from ...client import Client
from ...services import BaseService
from ...exceptions import ServerError
from .exceptions import PhenotypeError
from .phenotype import Phenotype

SERVICE_PATH = "api/phenotype-catalog"

log = logging.getLogger(__file__)

SUPPORTED_RESULT_TYPES = ["SET", "QT", "CATEGORY"]


class Service(BaseService):
    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)
        resp = self.session.get(self.session.url_from_endpoint("projects"))
        self.projects: Dict = {}
        for project in resp.json()["projects"]:
            self.projects[project["name"].lower()] = project

    def get_project_links(self, project: str) -> Dict:
        """
        Return all the links exported for a project

        :raises: PhenotypeError if the project does not exist
        """
        if project not in self.projects:
            raise PhenotypeError(f"Project {project} not found")
        return self.projects[project]["links"]

    def get_tags(self) -> List:
        """
        A list of all tags available in the system

        TODO: How can a new tag be added?

        """
        resp = self.session.get(self.session.url_from_endpoint("tags"))
        return resp.json()["tags"]

    def get_phenotypes(self, project: str) -> List:
        """
        A list of all the phenotypes in a project.

        :param project: Project to find phenotypes for
        :return: List of phenotypes as per api spec
        :raises: ServerError
        """
        # TODO: if project is not found a 500 error is raised instead of 404
        # TODO: project name is case sensitive on the server
        url = self.get_project_links(project)["phenotypes"]
        resp = self.session.get(url)

        data = resp.json()["phenotypes"]
        phenotypes = []
        for item in data:
            phenotypes.append(Phenotype(self.session, item))
        return phenotypes

    def get_phenotype(self, project: str, name: str) -> Phenotype:
        """
        Get a specific phenotype in a project

        :param project: Project to find phenotypes for
        :param name: Unique (lowercase) phenotype name in the project
        :return: List of phenotypes as per api spec
        :raises: ServerError
        """
        # TODO: if project is not found a 500 error is raised instead of 404
        # TODO: project name is case sensitive on the server
        url = urljoin(self.get_project_links(project)["phenotypes"], name)
        resp = self.session.get(url)

        data = resp.json()["phenotype"]
        return Phenotype(self.session, data)

    def create_phenotype(self, project: str, name: str, result_type: str) -> Phenotype:
        """
        Create a new phenotype in a project

        :param project: Project in which to create phenotype
        :param name: Unique (lowercase) phenotype name in the project
        :raises: PhenotypeError, ServerError
        """
        url = self.get_project_links(project)["phenotypes"]
        result_type = result_type.upper()
        if result_type not in SUPPORTED_RESULT_TYPES:
            raise PhenotypeError(
                f"Result type {result_type} not supported. Use one of {', '.join(SUPPORTED_RESULT_TYPES)}"
            )
        payload = {"name": name, "result_type": result_type}
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return Phenotype(self.session, data["phenotype"])

    def download(self, project: str, phenotypes: List) -> List:
        """
        Download phenotype data for the project

        Download phenotype data as TSV table (Mime type text/tab-separated-values).
        First column contains PNs, other columns are values for the phenotypes

        :param project: Project in which to delete the phenotype
        :param name: Unique (lowercase) phenotype name in the project
        :raises: ServerError
        """
        if isinstance(phenotypes, str):
            phenotypes = [phenotypes]
        url = self.get_project_links(project)["download"]

        resp = self.session.get(
            url, data={"phenotypes": ",".join([str(p) for p in phenotypes])}
        )
        return resp.content.decode()

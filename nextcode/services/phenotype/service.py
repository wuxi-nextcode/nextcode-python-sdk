"""
Service class
------------------
Service object for interfacing with the Phenotype Archive API

"""

import os
import logging
from posixpath import join as urljoin
from requests import codes
from typing import Optional, List, Union, Dict

from ...client import Client
from ...services import BaseService
from ...exceptions import ServerError
from .exceptions import PhenotypeError
from .phenotype import Phenotype
from .phenotype_matrix import PhenotypeMatrix

SERVICE_PATH = "api/phenotype-catalog"

log = logging.getLogger(__file__)

SUPPORTED_RESULT_TYPES = ["SET", "QT", "CATEGORY"]


class Service(BaseService):
    """
    A connection to the phenotype catalog service for a specific.

    The project can be passed in e.g. `nextcode.get_service("phenotype", project=myproject)`
    If it is not, the GOR_API_PROJECT environment variable or current profile config will be used.
    A project must be set when the service is instantiated.

    If the project does not already exist in the phenotype catalog only the `create_phenotype`
    method will work and the project will be created implicitly.

    To view available projects use the `svc.all_projects` dict
    """

    project_name: str = ""
    project: Dict = {}
    links: Dict = {}
    all_projects: Dict = {}

    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)
        project_name = (
            kwargs.get("project")
            or os.environ.get("GOR_API_PROJECT")
            or client.profile.project
        )
        if not project_name:
            raise PhenotypeError("Please specify a project")

        self._init_project(project_name)

    def _init_project(self, project_name):
        """
        Initialize the project from the server
        """
        self.project_name = project_name
        resp = self.session.get(self.session.url_from_endpoint("projects"))
        self.all_projects = {}
        for project in resp.json()["projects"]:
            self.all_projects[project["name"].lower()] = project

        self.project = self.all_projects.get(self.project_name, {})
        self.links = self.project.get("links", {})
        if self.project:
            log.info(f"Service initialized with project {self.project_name}")
        else:
            log.warning(f"Project {self.project_name} not found")

    def create_phenotype(
        self, name: str, result_type: str, description: Optional[str] = None
    ) -> Phenotype:
        """
        Create a new phenotype in the current project

        :param name: Unique (lowercase) phenotype name in the project
        :raises: PhenotypeError, ServerError
        """
        #! TODO: Get link from root
        url = urljoin(
            self.session.url_from_endpoint("projects"), self.project_name, "phenotypes"
        )
        result_type = result_type.upper()
        if result_type not in SUPPORTED_RESULT_TYPES:
            raise PhenotypeError(
                f"Result type {result_type} not supported. Use one of {', '.join(SUPPORTED_RESULT_TYPES)}"
            )
        payload = {"name": name, "result_type": result_type, "description": description}
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # if the project did not already exist, initialize the service
        if not self.project:
            self._init_project(self.project_name)
        return Phenotype(self.session, data["phenotype"])

    def get_tags(self) -> List:
        """
        A list of all tags available in the system
        """
        resp = self.session.get(self.session.url_from_endpoint("tags"))
        return resp.json()["tags"]

    def get_phenotypes(self, tags: List[str] = [], limit: int = 100) -> List[Phenotype]:
        """
        A list of all the phenotypes in the current project.

        :param tags: Optional list of tags to filter for
        :param limit: Maximum number of results (default: 100)
        :return: List of phenotypes
        :raises: `PhenotypeError` if the project does not exist
        :raises: ServerError
        """
        # TODO: project name is case sensitive on the server

        if not self.project:
            raise PhenotypeError("Project does not exist.")
        url = self.links["phenotypes"]
        content = {"with_all_tags": tags, "limit": limit}
        resp = self.session.get(url, data=content)

        data = resp.json()["phenotypes"]
        phenotypes = []
        for item in data:
            phenotypes.append(Phenotype(self.session, item))
        return phenotypes

    def get_phenotype(self, name: str) -> Phenotype:
        """
        Get a specific phenotype in the current project

        :param name: Unique (lowercase) phenotype name in the project
        :return: List of phenotypes as per api spec
        :raises: `PhenotypeError` if the project does not exist
        :raises: `ServerError`
        """
        # TODO: project name is case sensitive on the server
        if not self.project:
            raise PhenotypeError("Project does not exist.")

        url = urljoin(self.links["phenotypes"], name)
        try:
            resp = self.session.get(url)
        except ServerError as ex:
            if ex.response and ex.response["code"] == codes.not_found:
                raise PhenotypeError("Phenotype not found") from None
            else:
                raise

        data = resp.json()["phenotype"]
        return Phenotype(self.session, data)

    def get_phenotype_matrix(self, base: Optional[str] = None) -> PhenotypeMatrix:
        """
        Get a phenotype matrix object.

        :param base: Optional name of base set
        :return: PhenotypeMatrix builder object
        :raises: `PhenotypeError` if the project does not exist
        :raises: `ServerError`
        """
        return PhenotypeMatrix(self, base)

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

SERVICE_PATH = "api/phenotype-catalog"

log = logging.getLogger(__file__)

SUPPORTED_RESULT_TYPES = ["SET", "QT", "CATEGORY"]


class Service(BaseService):
    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)

    def get_project_url(self, project: str) -> str:
        # TODO: This url should come from the service
        url = urljoin(
            self.session.url_from_endpoint("root"), "projects", project, "phenotypes"
        )
        return url

    def get_phenotypes(self, project: str) -> List:
        """
        A list of all the phenotypes in a project.

        :param project: Project to find phenotypes for
        :return: List of phenotypes as per api spec
        :raises: ServerError
        """
        # TODO: if project is not found a 500 error is raised instead of 404
        # TODO: project name is case sensitive on the server
        url = self.get_project_url(project)
        try:
            resp = self.session.get(url)
        except ServerError as ex:
            raise ServerError(ex.response["message"]) from None

        # TODO: api spec is incorrect and does not specify this extra 'phenotypes' key
        phenotypes = resp.json()["phenotypes"]
        return phenotypes

    def get_phenotype(self, project: str, name: str) -> Dict:
        """
        Get a specific phenotype in a project

        :param project: Project to find phenotypes for
        :param name: Unique (lowercase) phenotype name in the project
        :return: List of phenotypes as per api spec
        :raises: ServerError
        """
        # TODO: if project is not found a 500 error is raised instead of 404
        # TODO: project name is case sensitive on the server
        url = urljoin(self.get_project_url(project), name)
        try:
            resp = self.session.get(url)
        except ServerError as ex:
            raise ServerError(ex.response["message"]) from None

        # TODO: api spec is incorrect and does not specify this extra 'phenotypes' key
        phenotypes = resp.json()["phenotype"]
        return phenotypes

    def create_phenotype(self, project: str, name: str, result_type: str) -> Dict:
        """
        Create a new phenotype in a project

        :param project: Project in which to create phenotype
        :param name: Unique (lowercase) phenotype name in the project
        :raises: PhenotypeError, ServerError
        """
        url = self.get_project_url(project)
        result_type = result_type.upper()
        if result_type not in SUPPORTED_RESULT_TYPES:
            raise PhenotypeError(
                f"Result type {result_type} not supported. Use one of {', '.join(SUPPORTED_RESULT_TYPES)}"
            )
        data = {"name": name, "result_type": result_type}
        try:
            resp = self.session.post(url, json=data)
        except ServerError as ex:
            # TODO: sdk expects errors to be formatted like so:
            # {
            #     "code": <response code, e.g. 404>,
            #     "message": <response message, e.g. 'Not Found'>,
            #     "error": {
            #         "request_id": <uuid, found in logs>,
            #         "type": "generic_error" (user) /"server_error" (500),
            #         "description": <for humans>
            #     }
            # }
            # That way the session automatically raises a pretty ServerError(<description>) for non-500 errors
            raise ServerError(ex.response["message"]) from None
        resp.raise_for_status()
        # TODO: Server raises 500 if phenotype already exists
        return resp.json()["phenotype"]

    def delete_phenotype(self, project: str, name: str) -> None:
        """
        Delete a phenotype, including all data from a project

        :param project: Project in which to delete the phenotype
        :param name: Unique (lowercase) phenotype name in the project
        :raises: ServerError
        """
        url = urljoin(self.get_project_url(project), name)
        try:
            _ = self.session.delete(url)
        except ServerError as ex:
            raise ServerError(ex.response["message"]) from None

    def upload(self, project: str, name: str, data: List):
        """
        Upload phenotype data

        :param project: Project in which to delete the phenotype
        :param name: Unique (lowercase) phenotype name in the project
        :raises: ServerError
        """
        if not isinstance(data, list):
            raise TypeError("data must be a list")
        url = urljoin(self.get_project_url(project), name, "upload")

        # TODO: each element must be a list with a single element??
        content = {"data": [[d] for d in data]}
        resp = self.session.post(url, json=content)
        return resp.json()

    def download(self, project: str, phenotypes: List) -> List:
        """
        Download phenotype data for the project

        Download phenotype data as TSV table (Mime type text/tab-separated-values).
        First column contains PNs, other columns are values for the phenotypes

        :param project: Project in which to delete the phenotype
        :param name: Unique (lowercase) phenotype name in the project
        :raises: ServerError
        """
        url = urljoin(self.get_project_url(project), "download")

        resp = self.session.get(
            url, data={"phenotypes": ",".join([str(p) for p in phenotypes])}
        )
        # TODO: 500 error is phenotype is not found
        # TODO: content-type is text/html, not text/tab-separated-values
        return resp.content.decode()

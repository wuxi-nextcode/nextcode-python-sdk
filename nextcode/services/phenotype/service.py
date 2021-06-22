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
from .playlist import Playlist
from .phenotype_matrix import PhenotypeMatrix

SERVICE_PATH = "api/phenotype-catalog"

log = logging.getLogger(__file__)

SUPPORTED_RESULT_TYPES = ["SET", "QT", "CATEGORY"]

def _get_paginated_results(method, limit):
    offset = 0
    combined_data = []
    # Loop to fetch the entire results, combining the paginated results
    while True:
        data = method(offset)
        results = len(data)
        combined_data += data
        offset += results

        if results < limit:
            break
    return combined_data


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
        self,
        name: str,
        result_type: str,
        description: Optional[str] = None,
        url: Optional[str] = None,
        category: Optional[str] = None,
        query: Optional[str] = None,
        tags: Optional[List[str]] = [],
    ) -> Phenotype:
        """
        Create a new phenotype in the current project

        :param name: Unique (lowercase) phenotype name in the project
        :param result_type: Must be one of SET, QT or CATEGORY
        :param description: Free text description of the phenotype (optional)
        :param url: Reference URL for the phenotype (to dataset or other reference)
        :param category: Enter the category for the phenotype (must be defined in the project - see get_categories) (optional)
        :param query: NOR query that defines this phenotype (optional)
        :param tags: comma separated list of tags to add to this phenotype (optional) e.g. ['tag1','tag2']
        :raises: PhenotypeError, ServerError
        """
        uri = urljoin(
            self.session.url_from_endpoint("root"),
            "projects",
            self.project_name,
            "phenotypes",
        )
        result_type = result_type.upper()
        if result_type not in SUPPORTED_RESULT_TYPES:
            raise PhenotypeError(
                f"Result type {result_type} not supported. Use one of {', '.join(SUPPORTED_RESULT_TYPES)}"
            )
        payload = {
            "name": name,
            "result_type": result_type,
            "description": description,
            "url": url,
            "category": category,
            "query": query,
            "tag_list": tags,
        }
        resp = self.session.post(uri, json=payload)
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

    def get_phenotypes(
            self,
            all_tags: List[str] = [],
            any_tags: List[str] = [],
            categories: List[str] = [],
            limit: int = 100,
            states: List[str] = [],
            search: str = None,
            playlist: int = None,
            updated_at: str = None,
            result_types: List[str] = [],
        ) -> List[Phenotype]:
        """
        Get all phenotypes in the current project as a list of Phenotypes.

        :param all_tags: Only fetch phenotypes that have all tags in the given list of tags
        :param any_tags: Fetch phenotypes that have any of the tags in the given list of tags
        :param categories: Only fetch phenotypes in the given list of categories
        :param limit: Maximum number of results (default: 100)
        :param states: Only fetch phenotypes in the given list of states
        :param search: String of keywords to search for in phenotypes, such as name, categories and tags
        :param playlist: Fetch a specific playlist of phenotypes by the playlist id
        :param updated_at: Only fetch phenotypes that match the given dates. Example: >=2017-04-01 ┃ <=2012-07-04 ┃ 2016-04-30..2016-07-04
        :param result_types: Only fetch phenotypes in the given list of result types
        :return: List of Phenotype
        :raises: `PhenotypeError` if the project does not exist
        :raises: ServerError
        """
        combined_data = self._get_phenotypes(
            all_tags,
            any_tags,
            categories,
            limit,
            states,
            search,
            playlist,
            updated_at,
            result_types
        )
        phenotypes = []
        for item in combined_data:
            phenotypes.append(Phenotype(self.session, item))
        return phenotypes

    def get_phenotypes_matrix(
            self,
            all_tags: List[str] = [],
            any_tags: List[str] = [],
            categories: List[str] = [],
            limit: int = 100,
            states: List[str] = [],
            search: str = None,
            playlist: int = None,
            updated_at: str = None,
            result_types: List[str] = [],
        ) -> List[Phenotype]:
        """
        Get all phenotypes in the current project as a PhenotypeMatrix.

        :param all_tags: Only fetch phenotypes that have all tags in the given list of tags
        :param any_tags: Fetch phenotypes that have any of the tags in the given list of tags
        :param categories: Only fetch phenotypes in the given list of categories
        :param limit: Maximum number of results (default: 100)
        :param states: Only fetch phenotypes in the given list of states
        :param search: String of keywords to search for in phenotypes, such as name, categories and tags
        :param playlist: Fetch a specific playlist of phenotypes by the playlist id
        :param updated_at: Only fetch phenotypes that match the given dates. Example: >=2017-04-01 ┃ <=2012-07-04 ┃ 2016-04-30..2016-07-04
        :param result_types: Only fetch phenotypes in the given list of result types
        :return: Phenotypes as PhenotypeMatrix
        :raises: `PhenotypeError` if the project does not exist
        :raises: ServerError
        """
        combined_data = self._get_phenotypes(
            all_tags,
            any_tags,
            categories,
            limit,
            states,
            search,
            playlist,
            updated_at,
            result_types
        )
        matrix = PhenotypeMatrix(self)
        for item in combined_data:
            matrix.add_phenotype(Phenotype(self.session, item))
        return matrix

    def get_phenotypes_dataframe(
            self,
            all_tags: List[str] = [],
            any_tags: List[str] = [],
            categories: List[str] = [],
            limit: int = 100,
            states: List[str] = [],
            search: str = None,
            playlist: int = None,
            updated_at: str = None,
            result_types: List[str] = []
        ) -> List[Phenotype]:
        """
        Get all phenotypes in the current project as a pandas DataFrame.

        :param all_tags: Only fetch phenotypes that have all tags in the given list of tags
        :param any_tags: Fetch phenotypes that have any of the tags in the given list of tags
        :param categories: Only fetch phenotypes in the given list of categories
        :param limit: Maximum number of results (default: 100)
        :param states: Only fetch phenotypes in the given list of states
        :param search: String of keywords to search for in phenotypes, such as name, categories and tags
        :param playlist: Fetch a specific playlist of phenotypes by the playlist id
        :param updated_at: Only fetch phenotypes that match the given dates. Example: >=2017-04-01 ┃ <=2012-07-04 ┃ 2016-04-30..2016-07-04
        :param result_types: Only fetch phenotypes in the given list of result types
        :return: Phenotypes as pandas dataframe
        :raises: `PhenotypeError` if the project does not exist
        :raises: ServerError
        """
        combined_data = self._get_phenotypes(
            all_tags,
            any_tags,
            categories,
            limit,
            states,
            search,
            playlist,
            updated_at,
            result_types
        )
        import pandas
        dataframe = pandas.DataFrame(combined_data)
        return dataframe

    def _get_phenotypes(
            self,
            all_tags: List[str] = [],
            any_tags: List[str] = [],
            categories: List[str] = [],
            limit: int = 100,
            states: List[str] = [],
            search: str = None,
            playlist: int = None,
            updated_at: str = None,
            result_types: List[str] = []
        ) -> List[Phenotype]:
        """
        Internal method to be called by `get_phenotypes`, `get_phenotypes_matrix` and `get_phenotypes_dataframe`
        See documentation of those methods for more details

        :param all_tags: Only fetch phenotypes that have all tags in the given list of tags
        :param any_tags: Fetch phenotypes that have any of the tags in the given list of tags
        :param categories: Only fetch phenotypes in the given list of categories
        :param limit: Maximum number of results (default: 100)
        :param states: Only fetch phenotypes in the given list of states
        :param search: String of keywords to search for in phenotypes, such as name, categories and tags
        :param playlist: Fetch a specific playlist of phenotypes by the playlist id
        :param updated_at: Only fetch phenotypes that match the given dates. Example: >=2017-04-01 ┃ <=2012-07-04 ┃ 2016-04-30..2016-07-04
        :param result_types: Only fetch phenotypes in the given list of result types
        :return: List of phenotypes
        :raises: `PhenotypeError` if the project does not exist
        :raises: ServerError
        """
        # TODO: project name is case sensitive on the server

        if not self.project:
            raise PhenotypeError("Project does not exist.")

        url = self.links["phenotypes"]
        if playlist:
            url = urljoin(self.links["self"], "playlists", str(playlist))

        if all_tags:
            all_tags = ','.join(all_tags)

        if any_tags:
            any_tags = ','.join(any_tags)

        if categories:
            categories = ','.join(categories)

        if result_types:
            result_types = ','.join(result_types)

        if states:
            states = ','.join(states)

        def do_get(offset=0):
            # This local method fetches paginated results from `offset` to limit
            content = {
                "with_all_tags": all_tags,
                "with_any_tags": any_tags,
                "limit": limit,
                "offset": offset,
                "category": categories,
                "search": search,
                "state": states,
                "updated_at": updated_at,
                "result_type": result_types
            }
            resp = self.session.get(url, data=content)

            if playlist:
                data = resp.json()["playlist"]["phenotypes"]
            else:
                data = resp.json()["phenotypes"]
            return data

        combined_data = _get_paginated_results(do_get, limit)
        return combined_data

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

    def get_categories(self) -> List:
        """
        A list of all categories available in the system
        """
        resp = self.session.get(
            urljoin(
                self.session.url_from_endpoint("root"),
                "projects",
                self.project_name,
                "categories",
            )
        )
        data = resp.json()["categories"]
        categories = []
        for item in data:
            categories.append(item)

        return categories

    def create_category(self, name: str):
        """
        Add a new category to this project.

        :param name: Name of the category
        :raises: `PhenotypeError` if the project does not exist
        """
        url = urljoin(
            self.session.url_from_endpoint("root"),
            "projects",
            self.project_name,
            "categories",
        )
        payload = {"name": name}
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # if the project did not already exist, initialize the service
        if not self.project:
            self._init_project(self.project_name)

        return payload

    def create_playlist(self, name: str, description: Optional[str] = None) -> Playlist:
        """
        Create a new playlist in the current project

        :param name: Unique (lowercase) phenotype name in the project
        :param description: Free text description of the playlist (optional)
        :param phenotypes: comma separated list of phenotypes to add (optional) e.g. ['tag1','tag2']
        """

        url = urljoin(
            self.session.url_from_endpoint("projects"), self.project_name, "playlists"
        )
        payload = {"name": name, "description": description}
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # if the project did not already exist, initialize the service
        if not self.project:
            self._init_project(self.project_name)
        return Playlist(self.session, data["playlist"])

    def get_playlists(self, limit: int = 100) -> List[Playlist]:
        """
        A list of all the playlists in the current project.

        :param limit: Maximum number of results (default: 100)
        :return: List of playlists
        :raises: `PhenotypeError` if the project does not exist
        :raises: ServerError
        """

        if not self.project:
            raise PhenotypeError("Project does not exist.")
        url = urljoin(
            self.session.url_from_endpoint("projects"), self.project_name, "playlists"
        )
        content = {"limit": limit}
        resp = self.session.get(url, data=content)

        data = resp.json()["playlists"]
        playlists = []
        for item in data:
            playlists.append(Playlist(self.session, item))
        return playlists

    def get_playlist(self, id: int = None, name: str = None) -> Playlist:
        """
        A list a single playlist in the current project based on the id.

        :param id: Specify the playlist to get by its id
        :param name: Retrieve a playlist by its unique name within project
        :return: A single playlist
        :raises: `PhenotypeError` if the project does not exist
        :raises: ServerError
        """

        if name and id:
            raise TypeError("id and name cannot both be supplied")
        if not self.project:
            raise PhenotypeError("Project does not exist.")
        url = urljoin(
            self.session.url_from_endpoint("projects"),
            self.project_name,
            "playlists",
            str(id),
        )

        if name:
            url = urljoin(
                self.session.url_from_endpoint('projects'),
                self.project_name,
                'playlists'
            )

        try:
            resp = self.session.get(url, data={'name': name})
        except ServerError as ex:
            if ex.response and ex.response["code"] == codes.not_found:
                raise PhenotypeError("Playlist not found") from None
            else:
                raise

        if name:
            data = resp.json()['playlists'][0]
        else:
            data = resp.json()["playlist"]
        return Playlist(self.session, data)

    def get_covariates(self, limit=100):
        """
        Get all covariates in current project
        """
        url = urljoin(self.links['self'], 'covariates')
        def do_get(offset=0):
            content = {'limit': limit, 'offset': offset}
            resp = self.session.get(url, data=content)
            data = resp.json()['covariates']
            return data

        combined_data = _get_paginated_results(do_get, limit)

        return combined_data

    def get_covariate(self, id):
        """
        Get a single covariate by its id
        """
        url = urljoin(self.links['self'], 'covariates', str(id))
        try:
            resp = self.session.get(url)
        except ServerError as ex:
            if ex.response and ex.response['code'] == codes.not_found:
                raise PhenotypeError(f"Covariate not found") from None
            else:
                raise ex
        data = resp.json()['covariate']
        return data

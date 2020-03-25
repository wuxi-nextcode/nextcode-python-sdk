"""
Service class
------------------
Service object for interfacing with the Project-Service API

"""

import logging
from typing import Optional, List, Union, Dict
from ...client import Client
from ...services import BaseService

SERVICE_PATH = "api/project"

log = logging.getLogger(__file__)


class Service(BaseService):
    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)

    def list_projects(self) -> List:
        """
        Returns the projects that have been created on the current server

        Refer to the API documentation for the Project service to see formatting of data.

        :return: List of projects
        """
        return [x['links']['self'] for x in self.__get_all_projects()]

    def get_project_by_id(self, project_id: int) -> Dict:
        """
        Returns the projects that have been created on the current server

        Refer to the API documentation for the Project service to see formatting of data.

        :return: A single project
        """
        projects = self.__get_all_projects()
        project_url = [x['links']['self'] for x in projects if x["project_id"] == project_id][0]
        resp = self.session.get(project_url)
        project_info = resp.json()
        return project_info

    def __get_all_projects(self) -> List:
        """
        Returns the projects that have been created on the current server

        :return: List of projects
        """
        project_url = self.session.url_from_endpoint("projects")
        return self.session.get(project_url).json()




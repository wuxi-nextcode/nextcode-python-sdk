"""
Service class
------------------
Service object for interfacing with the GOR Query Server.

This class instance is used to communicate with a RESTFul service. Use the `execute`
methods to get started.

"""
import json
import logging
import os
from typing import Dict, Tuple, Sequence, List, Optional, Union, Any

from .result import Result
from .result import throw_error_from_line
from ...services import BaseService
from ...exceptions import ServerError
from ...client import Client
from ..query.exceptions import QueryError

from ..query.utils import extract_virtual_relations
import nextcode

SERVICE_PATH = "queryserver"

log = logging.getLogger(__name__)


class Service(BaseService):
    """
    A connection to the query server
    """

    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)
        self.metadata = {"client": f"nextcode-python-sdk/{nextcode.__version__}"}
        self.project = (
            kwargs.get("project")
            or os.environ.get("GOR_API_PROJECT")
            or client.profile.project
        )

    def _check_project(self):
        """
        Raise an exception if there is no project specified

        :raises: QueryError
        """
        if not self.project:
            raise QueryError("No project specified")

    def set_project(self, project: str, persist: bool = True) -> None:
        """
        Set the current project for all subsequent queries.

        :project: The project name
        :persist: Persist the project name into the current profile

        """
        self.project = project
        if persist:
            self.client.profile.project = self.project

    def execute(
        self,
        query: str,
        relations: Optional[List[Dict]] = None,
        job_type: Optional[str] = None,
        gzip: Optional[bool] = False,
        **kw,
    ):  # -> SynchronousQuery:
        """
        Execute a gor statement on the server synchronously.

        :param query: gor query string
        :param relations: virtual relations to include with the query
        :param job_type: Optional job type for routing purposes
        :param gzip:Optional if result should be gzipped.

        :raises: :exc:`~exceptions.ServerError`, :exc:`~exceptions.MissingRelations`

        Optional keyword arguments in the form `name=data` (where data is a tsv string) are converted into virtual relations if relations
        is not explicitly passed in and added to the relations set by the relations parameter. If the relations parameter is set it
        should be a list of dictionaries with {"name": "relation-name", "data": "<tsv string>"}
        """
        self._check_project()

        payload_relations = extract_virtual_relations(kw, relations)

        payload: Dict[str, Optional[Union[int, str, List[Any], Dict]]] = {
            "project": self.project,
            "query": query,
            "user": "python-sdk",
            "virtualRelations": payload_relations,
            "routingKey": job_type or "default",
            "useGzip": str(gzip).lower(),
            "sendTerm": True,
            "sendProgress": True,
            "sendAlive": True
        }

        url = self.session.url_from_endpoint("query")

        try:
            resp = self.session.post(url,
                                     json=payload,
                                     stream=True,
                                     headers={"Content-Type": "application/json",
                                              "Accept-Encoding": "chunked",
                                              "Accept": "application/octet-stream"})
            resp.raise_for_status()
        except ServerError as ex:
            throw_error_from_line(ex.message)

        return Result(resp, gzip)

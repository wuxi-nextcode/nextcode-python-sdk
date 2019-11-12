"""
Query-API Service
------------------
Service object for interfacing with the GOR Query API

"""

import logging
import os
from typing import Dict, Tuple, Sequence, List, Optional, Union, Any
from requests import codes

from ...services import BaseService
from ...exceptions import ServerError
from ...client import Client
from .exceptions import QueryError, MissingRelations
from .query import Query
from .utils import get_fingerprint
import nextcode

SERVICE_PATH = "/api/query"

RUNNING_STATUSES = ("PENDING", "RUNNING", "CANCELLING")
RESULTS_PAGE_SIZE = 200000
QUERY_WAIT_SECONDS = 2
DEFAULT_EXTENSION = ".tsv"

log = logging.getLogger(__name__)


class Service(BaseService):
    """
    A connection to the query api
    """

    def __init__(self, client: Client, *args, **kwargs) -> None:
        path = os.environ.get("NEXTCODE_SERVICE_PATH", SERVICE_PATH)
        # ! temporary hack
        if "localhost" in client.profile.root_url:
            path = "/"
        super(Service, self).__init__(client, path, *args, **kwargs)
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

    def get_template(self, name: str) -> Dict:
        url = self.session.endpoints["templates"] + name
        return self.session.get(url).json()

    def get_templates(
        self, organization: str = None, category: str = None, name: str = None
    ) -> Dict[str, Dict]:
        """
        Return a list of all templates in the system or filtered.

        Returns a list of full template names in the format [organization]/[category]/[name]/[version]

        :param organization: Filter results by organization
        :param category: Filter results by category
        :param name: Filter results by template name
        :raises: ServerError
        """
        if organization:
            links = [self.session.endpoints["templates"] + organization + "/"]
        else:
            orgs = self.session.get(self.session.endpoints["templates"]).json()[
                "organizations"
            ]
            links = [o["links"]["self"] for o in orgs]
        ret = {}
        for link in links:
            if category:
                category_links = [link + category + "/"]
            else:
                category_links = [
                    c["links"]["self"]
                    for c in self.session.get(link).json()["categories"]
                ]
            for link in category_links:
                try:
                    resp = self.session.get(link)
                except ServerError:
                    continue
                for template in resp.json()["templates"]:
                    if not name or template["name"] == name:
                        ret[template["full_name"]] = template
        return ret

    def execute(
        self,
        query: str,
        nowait: bool = False,
        persist: Optional[str] = None,
        relations: Optional[List[Dict]] = None,
        job_type: Optional[str] = None,
        **kw,
    ) -> Query:
        """
        Execute a gor statement on the server.

        :param query: gor query string
        :param nowait: if True, return a Query object with PENDING status instead of waiting for query to finish
        :param relations: virtual relations to include with the query
        :param persist: File path in the project tree to persist the results to (must start with `user_data/`)
        :param job_type: Optional job type for routing purposes

        :raises: :exc:`~exceptions.ServerError`, :exc:`~exceptions.MissingRelations`

        Optional keyword arguments in the form `name=data` are converted into virtual relations if relations
        is not explicitly passed in.

        Whether nowait is set or not, the serverside method will wait for a maximum of 2 seconds for the query
        to transition to a completed status. Therefore, most small queries will return in DONE status.
        """
        self._check_project()
        url = self.session.endpoints["queries"]
        _relations: List[Dict] = []
        if relations:
            _relations = relations
        else:
            for k, v in kw.items():
                _relations.append({"name": f"[{k}]", "data": v})

        payload_relations: List[Dict] = []
        for r in _relations:
            if "data" not in r or "name" not in r:
                raise QueryError("Virtual relations must have name and data fields")
            name = r["name"]
            data = r["data"]

            if hasattr(data, "to_csv"):
                data = data.to_csv(index=False, sep="\t")
            if not isinstance(data, str):
                raise QueryError(f"Virtual relation data for {name} must be a string")

            if not data.startswith("#"):
                data = "#" + data

            fingerprint = r.get("fingerprint") or get_fingerprint(data)
            extension = r.get("extension") or DEFAULT_EXTENSION
            payload_relations.append(
                {
                    "name": name,
                    "fingerprint": fingerprint,
                    "extension": extension,
                    "data": data,
                }
            )
        payload: Dict[str, Optional[Union[int, str, List[Any], Dict]]] = {
            "project": self.project,
            "query": query,
            "relations": payload_relations,
            "persist": persist,
            "wait": QUERY_WAIT_SECONDS,
            "metadata": self.metadata,
            "type": job_type,
        }
        try:
            resp = self.session.post(url, json=payload)
        except ServerError as ex:
            if ex.response and ex.response["code"] == codes.conflict:
                raise MissingRelations(
                    [r["name"] for r in ex.response["error"]["virtual_relations"]]
                )
            else:
                raise
        gor_query = Query(self, resp.json())
        log.info(
            "Query %s has been created and has status %s",
            gor_query.query_id,
            gor_query.status,
        )
        if not nowait:
            gor_query.wait()
        return gor_query

    def execute_template(self, template_name: str, nowait: bool = False, **kw) -> Query:
        """
        Execute a gor template on the server.

        :param template_name: Full template name in the form [org]/[category]/[query]/[version]
        :param nowait: if True, return a Query object with PENDING status instead of waiting for query to finish
        :raises: :exc:`~exceptions.ServerError`

        Optional keyword arguments are used for arguments into the template.
        """
        self._check_project()
        url = self.session.endpoints["templates"]
        template_url = url + template_name
        try:
            template = self.session.get(template_url).json()
        except ServerError as ex:
            if ex.response and ex.response["code"] == codes.not_found:
                raise QueryError("Template {} not found".format(template_name))
            else:
                raise

        execute_url = template["links"]["execute"]
        args = []
        for k, v in kw.items():
            args.append({k: v})
        payload = {
            "project": self.project,
            "args": args,
            "wait": QUERY_WAIT_SECONDS,
            "metadata": self.metadata,
        }
        resp = self.session.post(execute_url, json=payload)

        gor_query = Query(self, resp.json())
        log.info(
            "Template Query %s has been created and has status %s",
            gor_query.query_id,
            gor_query.status,
        )
        if not nowait:
            gor_query.wait()
        return gor_query

    def get_query(self, query_id: int) -> Query:
        """
        Get a query object for a query by id

        :param query_id: The ID of a query that has been previously executed
        :raises: QueryError

        """
        self._check_project()
        url = self.session.endpoints["queries"]
        try:
            resp = self.session.get(f"{url}{query_id}")
        except ServerError as ex:
            if ex.response["code"] == codes.not_found:
                raise QueryError(f"Query {query_id} not found") from None
            raise QueryError(repr(ex), query_id=query_id) from None
        return Query(self, resp.json())

    def get_queries(self, status=None, limit=100) -> Sequence[Query]:
        """
        Get all queries that have been run by the current user in the current project, optionally filtered by status.

        Results are returned in reverse chronological order so latest queries are first.

        Note that queries are returned in `partial` state which means they might not be up to date. `query.refresh()`
        can be called to force a refresh.

        :param status: Filter queries by status. e.g. `DONE` `RUNNING` `FAILED`
        :param limit: Limit the number of queries returned.
        """
        self._check_project()
        data = {
            "project": self.project,
            "user_name": self.current_user["email"],
            "limit": limit,
            "status": status,
        }
        rsp = self.session.get(self.session.endpoints["queries"], json=data)
        queries = []
        for payload in rsp.json()["queries"]:
            queries.append(Query(self, payload))
        return queries

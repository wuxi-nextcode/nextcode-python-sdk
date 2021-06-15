"""
Service class
------------------
Service object for interfacing with the GOR Query API.

This class instance is used to communicate with a RESTFul service. Use the `execute` and `execute_template`
methods to get started. To view past queries you can use the `get_queries` and `get_query` methods which return
`Query` objects.

"""

import logging
import os
from typing import Dict, Tuple, Sequence, List, Optional, Union, Any
from requests import codes
from pathlib import Path
import yaml
from urllib.parse import urlencode

from ...services import BaseService
from ...exceptions import ServerError
from ...client import Client
from .exceptions import QueryError, MissingRelations, TemplateError
from .query import Query
from .utils import extract_virtual_relations
import nextcode

SERVICE_PATH = "api/query"

RUNNING_STATUSES = ("PENDING", "RUNNING", "CANCELLING")
RESULTS_PAGE_SIZE = 200000
QUERY_WAIT_SECONDS = 2

log = logging.getLogger(__name__)


class Service(BaseService):
    """
    A connection to the query api
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

    def get_template(self, name: str) -> Dict:
        """
        Get a specific template from the server based on full name.

        The template name is in the format [organization]/[category]/[name]/[version]

        :param name: Full template name
        :raises TemplateError: if the template was not found
        :return: Template dict, see Query API Spec for details
        """
        url = self.session.endpoints["templates"] + name
        try:
            return self.session.get(url).json()
        except ServerError:
            raise TemplateError(f"Template {name} not found")

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

    def add_template_from_file(
        self,
        filename: str,
        package_version: Optional[str] = None,
        replace: bool = False,
    ) -> str:
        """
        Add a new template from yaml file.

        If the template already exists a TemplateError is raised. If replace is True
        the template is replaced silently

        :param filename: Full path to a yaml file containing template
        :param package_version: Version of CLA Query Package that contained the Template
        :param replace: Replace an existing template
        :returns: Full name of the new template
        :raises: TemplateError if the file is not found, the template is invalid or if there is a server error.
        """
        p = Path(filename)
        if not p.exists():
            raise TemplateError(f"File '{filename}' not found")
        with p.open() as f:
            yaml_string = f.read()
        try:
            contents = yaml.safe_load(yaml_string)
            if not isinstance(contents, dict):
                raise TemplateError("File contents is not a dictionary")
        except Exception as ex:
            raise TemplateError(f"Yaml is invalid: {ex}")
        name = next(iter(contents))
        url = self.session.url_from_endpoint("templates")
        log.info("Uploading template '%s' to %s...", name, url)
        try:
            resp = self.session.post(
                url, json={"yaml": yaml_string, "package_version": package_version}
            )
        except ServerError as se:
            if se.response and se.response.get("code") == 409:
                if replace:
                    err = se.response["error"]
                    log.info(
                        "Template already exists with ID %s. Replacing...",
                        err["template_id"],
                    )
                    try:
                        resp = self.session.delete(err["template_url"])
                        resp = self.session.post(
                            url,
                            json={
                                "yaml": yaml_string,
                                "package_version": package_version,
                            },
                        )
                    except ServerError as ex:
                        raise TemplateError(str(ex))
                else:
                    raise TemplateError(f"Template '{name}' already exists")
            else:
                raise TemplateError(str(se))

        full_name = resp.json()["full_name"]
        log.info(
            "Template '%s' (%s) has been successfully added",
            full_name,
            resp.json()["id"],
        )
        return full_name

    def delete_template(self, name: str) -> None:
        """
        Deletes a template on the server by full name, e.g. /[org]/[cat]/[name]/[version]

        :param name: Full unique name of the template
        :raises: :exc:`TemplateError`, if the template is not found or if we cannot delete it.
        """
        template = self.get_template(name)
        try:
            _ = self.session.delete(template["links"]["self"])
        except ServerError as e:
            raise TemplateError(f"Could not delete template: {e}")

    def render_template(self, name: str, params: Optional[Dict] = None) -> str:
        """
        Render a template using the supplied arguments and return the full GOR query string.

        :name: Full unique name of the template
        :params: List of arguments to supply to the template
        :raises: :exc:`TemplateError`
        :returns: String containing a fully rendered template
        """
        template = self.get_template(name)

        render_url = template["links"]["render"]
        log.info("Calling render endpoint %s", render_url)
        try:
            resp = self.session.get(
                render_url, params=params, headers={"Accept": "text/plain"}
            )
        except ServerError as ex:
            if "Missing arguments" in str(ex):
                raise TemplateError(str(ex))
            else:
                raise
        return resp.text

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

        Optional keyword arguments in the form `name=data` (where data is a tsv string) are converted into virtual relations if relations
        is not explicitly passed in and added to the relations set by the relations parameter. If the relations parameter is set it
        should be a list of dictionaries with {"name": "relation-name", "data": "<tsv string>"}

        Whether nowait is set or not, the serverside method will wait for a maximum of 2 seconds for the query
        to transition to a completed status. Therefore, most small queries will return in DONE status.
        """
        self._check_project()

        payload_relations = extract_virtual_relations(kw, relations)

        payload: Dict[str, Optional[Union[int, str, List[Any], Dict]]] = {
            "project": self.project,
            "query": query,
            "relations": payload_relations,
            "persist": persist,
            "wait": QUERY_WAIT_SECONDS,
            "metadata": self.metadata,
            "type": job_type or "default",
        }

        url = self.session.endpoints["queries"]
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

    def execute_template(
        self,
        template_name: str,
        nowait: bool = False,
        persist: Optional[str] = None,
        job_type: Optional[str] = None,
        **kw,
    ) -> Query:
        """
        Execute a gor template on the server.

        :param template_name: Full template name in the form [org]/[category]/[query]/[version]
        :param nowait: if True, return a Query object with PENDING status instead of waiting for query to finish
        :param persist: File path in the project tree to persist the results to (must start with `user_data/`)
        :param job_type: Optional job type for routing purposes
        :raises: :exc:`~ServerError`

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
        args = {}
        for k, v in kw.items():
            args[k] = v
        payload: Dict[str, Union[str, Any]] = {
            "project": self.project,
            "args": args,
            "wait": QUERY_WAIT_SECONDS,
            "metadata": self.metadata,
            "persist": persist,
            "type": job_type or "default",
        }
        try:
            resp = self.session.post(execute_url, json=payload)
        except ServerError as ex:
            if "Missing arguments" in repr(ex):
                raise TemplateError(str(ex))
            else:
                raise

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
        Get a query object for a query by id, does not require project to be set

        :param query_id: The ID of a query that has been previously executed
        :raises: :exc:`~QueryError`

        """
        url = self.session.endpoints["queries"]
        try:
            resp = self.session.get(f"{url}{query_id}")
        except ServerError as ex:
            if ex.response["code"] == codes.not_found:
                raise QueryError(f"Query {query_id} not found") from None
            raise QueryError(repr(ex), query_id=query_id) from None
        return Query(self, resp.json())

    def get_queries(
        self,
        status: Optional[str] = None,
        user_name: Optional[str] = None,
        limit: int = 100,
        all: Optional[bool] = False,
    ) -> Sequence[Query]:
        """
        Get all queries that have been run by the current user in the current project, optionally filtered by status.

        Results are returned in reverse chronological order so latest queries are first.

        Note that queries are returned in `partial` state which means they might not be up to date. `query.refresh()`
        can be called to force a refresh.

        :param status: Filter queries by status. e.g. `DONE` `RUNNING` `FAILED`.
        :param user_name: Show queries for another user (only available to admin).
        :param limit: Limit the number of queries returned.
        :param all: Fetch all queries in all projects (only available to admin).
        """
        if all:
            user_name = None
            project = None
        else:
            user_name = user_name or self.current_user.get("email")
            project = self.project
        data: Dict[str, Union[str, Any]] = {
            "project": project,
            "user_name": user_name,
            "limit": limit,
            "status": status,
        }
        rsp = self.session.get(self.session.endpoints["queries"], json=data)
        queries = []
        for payload in rsp.json()["queries"]:
            q = Query(self, payload)
            if q.running:
                pass
            queries.append(q)
        return queries

    def wakeup(
        self, job_type: Optional[str] = "default", user: Optional[str] = None
    ) -> bool:
        """
        Wake up the server.

        Inform the query service that we are about to perform some queries.

        This gives the query service a chance to spawn some workers and be prepared for
        queries in order to reduce wait times.
        :param job_type: Optional job type for routing purposes
        :param user: Optional user for tracking purposes (requires admin role)
        :returns success: Was the request successful
        """
        data = {
            "type": job_type,
            "user": user,
        }
        resp = self.session.post(self.session.endpoints["wakeup"], json=data)
        return resp.json()["success"]

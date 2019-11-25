import time

from typing import Optional, List, Union, Dict
from ...services import BaseService
from ...client import Client
from ...exceptions import NotFound
from .job import WorkflowJob

import logging

SERVICE_PATH = "workflow"

log = logging.getLogger(__name__)


class Service(BaseService):
    """
    A connection to the workflow service API server
    """

    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)

    def get_pipelines(self) -> List:
        """
        Returns the pipelines available on the current server
        
        Refer to the API documentation for the Workflow service to see formatting of data.

        :return: List of pipelines
        """
        resp = self.session.get(self.session.url_from_endpoint("pipelines"))
        pipelines = resp.json()["pipelines"]
        return pipelines

    def get_projects(self) -> List:
        """
        Returns the projects that have been created on the current server

        Refer to the API documentation for the Workflow service to see formatting of data.

        :return: List of projects
        """
        resp = self.session.get(self.session.url_from_endpoint("projects"))
        projects = resp.json()["projects"]
        return projects

    def find_job(self, job_id: Union[int, str]) -> WorkflowJob:
        """
        Return a job proxy object
        """
        jobs_endpoint = self.session.url_from_endpoint("jobs")

        data: Dict = {"limit": 1}
        if job_id == "latest":
            data["user_name"] = self.current_user.get("email")
        else:
            try:
                data["job_id"] = int(job_id)
            except ValueError:
                raise NotFound(
                    "job_id must be an integer or 'latest', not '%s'" % job_id
                )
        resp = self.session.get(jobs_endpoint, json=data)
        jobs = resp.json()["jobs"]
        if not jobs:
            raise NotFound("Job not found")

        job = jobs[0]
        return WorkflowJob(self.session, job["job_id"], job)

    def get_jobs(
        self, user_name: Optional[str], status: Optional[str], limit: Optional[int]
    ) -> List[WorkflowJob]:
        """
        Get a list of jobs satisfying the supplied criteria

        :param user_name: The user who created the job
        :param status: Current status of jobs
        :param limit: Maximum number of jobs to return
        """
        data: Dict = {"limit": limit}
        if user_name:
            data["user_name"] = user_name
        if status:
            data["status"] = status

        st = time.time()
        resp = self.session.get(self.session.url_from_endpoint("jobs"), json=data)
        jobs = resp.json()["jobs"]
        log.info("Retrieved %s jobs in %.2f sec", len(jobs), time.time() - st)
        ret = []
        for job in jobs:
            ret.append(WorkflowJob(self.session, job["job_id"], job))
        return ret

    def post_job(
        self,
        pipeline_name: Optional[str],
        project_name: str,
        params: Optional[List],
        script: Optional[str],
        revision: Optional[str],
        build_source: Optional[str],
        build_context: Optional[str],
        profile: Optional[str] = None,
        trace: bool = False,
    ):
        """
        Run a workflow job

        :param pipeline_name: Name of the pipeline to run
        :param project_name: Name of the project to run this job on
        :param params: List of parameters to forward to the job
        :param script: Git repository url to run (only when server is in development mode)
        :param revision: Git revision or tag (only when server is in development mode)
        :param build_source: Source type of the nextflow build (builtin, git, url)
        :param build_context: Context for build_source, depends on the type.
        :param profile: Nextflow profile name to use.
        :param trace: Instruct the job to run nextflow trace flags for debugging.

        """
        log.debug(
            "post_job called with pipeline_name=%s, project_name=%s, params=%s, script=%s, revision=%s, build_source=%s, build_context=%s, profile=%s",
            pipeline_name,
            project_name,
            params,
            script,
            revision,
            build_source,
            build_context,
            profile,
        )
        data = {
            "pipeline_name": pipeline_name,
            "project_name": project_name,
            "parameters": params,
            "script": script,
            "revision": revision or None,
            "build_source": build_source,
            "build_context": build_context,
            "profile": profile,
        }

        if trace:
            data["env"] = {"NXF_DEBUG": "3", "NXF_TRACE": "nextflow"}  # type: ignore

        endpoint = self.session.url_from_endpoint("jobs")

        resp = self.session.post(endpoint, json=data)
        job = resp.json()
        return WorkflowJob(self.session, job["job_id"], job=job)

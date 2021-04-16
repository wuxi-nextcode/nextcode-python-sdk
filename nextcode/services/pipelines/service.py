"""
Service class
------------------
Service object for interfacing with the Pipelines Service API.

This class instance is used to communicate with a RESTFul service. The `post_job` method
creates a new job on the server and `find_job` and `get_jobs` allow you to inspect running
and past workflow jobs.

Note: This service has not been fully integrated into the SDK and access is still quite raw. 

"""
import time
import os

from typing import Optional, List, Union, Dict
from ...services import BaseService
from ...client import Client
from ...exceptions import NotFound
from .job import PipelineJob
from .exceptions import JobError
from ...packagelocal import package_and_upload

import logging

SERVICE_PATH = "pipelines-service"


log = logging.getLogger(__name__)


class Service(BaseService):
    """
    A connection to the pipelines service API server
    """

    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)

    def get_pipelines(self) -> List:
        """
        Returns the pipelines available on the current server

        Refer to the API documentation for the Pipelines service to see formatting of data.

        :return: List of pipelines
        """
        resp = self.session.get(self.session.url_from_endpoint("pipelines"))
        pipelines = resp.json()["pipelines"]
        return pipelines

    def get_projects(self) -> List:
        """
        Returns the projects that have been created on the current server

        Refer to the API documentation for the Pipelines service to see formatting of data.

        :return: List of projects
        """
        resp = self.session.get(self.session.url_from_endpoint("projects"))
        projects = resp.json()["projects"]
        return projects

    def find_job(self, job_id: Union[int, str]) -> PipelineJob:
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
        return PipelineJob(self.session, job["job_id"], job)

    def get_jobs(
        self,
        user_name: Optional[str] = None,
        status: Optional[str] = None,
        project: Optional[str] = None,
        pipeline: Optional[str] = None,
        limit: Optional[int] = 50,
    ) -> List[PipelineJob]:
        """
        Get a list of jobs satisfying the supplied criteria

        :param user_name: The user who created the job
        :param status: Current status of jobs
        :param project: Filter by project
        :param pipeline: Filter by pipeline name
        :param limit: Maximum number of jobs to return
        """
        data: Dict = {"limit": limit}
        if user_name:
            data["user_name"] = user_name
        if status:
            data["status"] = status
        if project:
            data["project_name"] = project
        if pipeline:
            data["pipeline_name"] = pipeline
        st = time.time()
        resp = self.session.get(self.session.url_from_endpoint("jobs"), json=data)
        jobs = resp.json()["jobs"]
        log.info("Retrieved %s jobs in %.2f sec", len(jobs), time.time() - st)
        ret = []
        for job in jobs:
            ret.append(PipelineJob(self.session, job["job_id"], job))
        return ret

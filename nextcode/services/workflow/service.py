"""
Service class
------------------
Service object for interfacing with the Workflow Service API.

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
from .job import WorkflowJob
from .exceptions import JobError
from ...packagelocal import package_and_upload

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
        self,
        user_name: Optional[str] = None,
        status: Optional[str] = None,
        project: Optional[str] = None,
        pipeline: Optional[str] = None,
        state: Optional[str] = None,
        context: Optional[str] = None,
        limit: Optional[int] = 50,
    ) -> List[WorkflowJob]:
        """
        Get a list of jobs satisfying the supplied criteria

        :param user_name: The user who created the job
        :param status: Current status of jobs
        :param project: Filter by project
        :param pipeline: Filter by pipeline name
        :param state: Filter by state, each state encapsulates several statuses (running, finished)
        :param context: Filter by context string
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
        if state:
            data["state"] = state
        if context:
            data["context"] = context
        st = time.time()
        resp = self.session.get(self.session.url_from_endpoint("jobs"), json=data)
        jobs = resp.json()["jobs"]
        log.info("Retrieved %s jobs in %.2f sec", len(jobs), time.time() - st)
        ret = []
        for job in jobs:
            ret.append(WorkflowJob(self.session, job["job_id"], job))
        return ret

    def run_local(
        self,
        path,
        project_name: str = None,
        params: Optional[Dict] = None,
        profile: Optional[str] = None,
        trace: bool = False,
        details: Optional[Dict] = None,
        description: Optional[str] = None,
    ):
        """
        Run a workflow job from a local nextflow folder

        This will package the passed-in folder and upload to a specific bucket that is exported from the workflow
        service on the cluster (see 'scratch-bucket' from the svc.status() method)
        AWS access keys must be set up correctly to upload to this bucket using typical aws/boto environment and
        credential management.

        :param path: Path (relative or absolute) to a folder containing a nextflow script
        :param project_name: Name of the project to run this job on, defaults to GOR_API_PROJECT in environment
        :param params: Dictionary of parameters to forward to the job
        :param profile: Nextflow profile name to use.
        :param trace: Instruct the job to run nextflow trace flags for debugging.
        :param details: Dictionary containing the initial values for 'details' in the job
        :param description: Human readable description of the job
        """

        build_context = package_and_upload(self, "local_workflow", path)
        return self.post_job(
            None,
            project_name,
            build_source="url",
            build_context=build_context,
            profile=profile,
            trace=trace,
            params=params,
            details=details,
            description=description,
        )

    def post_job(
        self,
        pipeline_name: Optional[str] = None,
        project_name: str = None,
        params: Optional[Dict] = None,
        script: Optional[str] = None,
        revision: Optional[str] = None,
        build_source: Optional[str] = None,
        build_context: Optional[str] = None,
        profile: Optional[str] = None,
        trace: bool = False,
        details: Optional[Dict] = None,
        description: Optional[str] = None,
        executor_memory_mb: Optional[int] = None,
        context: Optional[str] = None,
        storage_type: Optional[str] = None,
        dedicated_storage_size: Optional[str] = None,
        keep_resources: Optional[bool] = None,
        mount_jobs: Optional[List[int]] = None,
        credentials: Optional[Dict] = None,
        scheduler_name: Optional[str] = None,
        features: Optional[Dict] = None
    ):
        """
        Run a workflow job

        This is a low-level implementation on top of the workflow service's POST /jobs endpoint.

        :param pipeline_name: Name of the pipeline to run
        :param project_name: Name of the project to run this job on, defaults to GOR_API_PROJECT in environment
        :param params: Dictionary of parameters to forward to the job
        :param script: Git repository url to run (only when server is in development mode)
        :param revision: Git revision or tag (only when server is in development mode)
        :param build_source: Source type of the nextflow build (builtin, git, url)
        :param build_context: Context for build_source, depends on the type.
        :param profile: Nextflow profile name to use.
        :param trace: Instruct the job to run nextflow trace flags for debugging.
        :param details: Dictionary containing the initial values for 'details' in the job
        :param description: Human readable description of the job
        :param executor_memory_mb: Override the memory limit of the nextflow executor
        :param context: Optional string to allow querying for custom information
        :param storage_type: Optional string specifying the storage option to use for the pipeline
        :param dedicated_storage_size Optional string specifying the size of the dedicated volume if using
               storage_type=dedicated
        :param keep_resources: Optional boolean specifying if resources created by workflow service for the Job should
               be exempt from being cleanup up by the workflow resource cleanup process.
        :param mount_jobs: Optional list of job-ids whose work folder will be mounted into this job under
               the folder /job/<job-id>.
        :param credentials: Optional dict containing credentials to forward to workflow-service
        example credentials:  {
            'download': {
                'aws_access_key_id': 'ASIA...',
                'aws_secret_access_key': 'k6q5...'
            },
            'upload': {
                'aws_access_key_id': 'ASIA...',
                'aws_secret_access_key': 'k6q5...'
            }
        }
        :param scheduler_name: Optional string specifying the scheduler to use. If not specified, the default scheduler
               will be used
        :param features: Extra parameters to pass to workflow-service to turn features on/off
        """
        if not project_name:
            project_name = os.environ.get("GOR_API_PROJECT")
        if not project_name:
            raise JobError(
                "No project specified and GOR_API_PROJECT not set in environment"
            )
        log.debug(
            "post_job called with pipeline_name=%s, project_name=%s, params=%s, script=%s, revision=%s, "
            "build_source=%s, build_context=%s, profile=%s, description=%s, executor_memory_mb=%s, context=%s, "
            "storage_type=%s, dedicated_storage_size=%s, mount_jobs=%s scheduler_name=%s",
            pipeline_name,
            project_name,
            params,
            script,
            revision,
            build_source,
            build_context,
            profile,
            description,
            executor_memory_mb,
            context,
            storage_type,
            dedicated_storage_size,
            mount_jobs,
            scheduler_name,
        )
        data = {
            "pipeline_name": pipeline_name,
            "project_name": project_name,
            "parameters": params,
            "revision": revision or None,
            "script": script,
            "build_context": build_context,
            "profile": profile,
            "details": details,
            "description": description,
            "context": context,
            "features": features
        }
        if storage_type:
            data["storage_type"] = storage_type
        if dedicated_storage_size:
            data["dedicated_storage_size"] = dedicated_storage_size
        if build_source:
            data["build_source"] = build_source
        if executor_memory_mb:
            data["executor_memory_mb"] = executor_memory_mb
        if trace:
            data["env"] = {"NXF_DEBUG": "3", "NXF_TRACE": "nextflow"}  # type: ignore
        if credentials:
            data["credentials"] = credentials
        if keep_resources:
            data["keep_resources"] = keep_resources
        if mount_jobs:
            data["mount_jobs"] = mount_jobs
        if scheduler_name:
            data["scheduler_name"] = scheduler_name

        endpoint = self.session.url_from_endpoint("jobs")

        resp = self.session.post(endpoint, json=data)
        job = resp.json()
        return WorkflowJob(self.session, job["job_id"], job=job)

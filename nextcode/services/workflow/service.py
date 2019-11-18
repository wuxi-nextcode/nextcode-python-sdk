import time

from ...services import BaseService
from ...client import Client
from ...exceptions import NotFound
from .job import WorkflowJob

import logging

SERVICE_PATH = "/workflow"

log = logging.getLogger(__name__)


class Service(BaseService):
    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)

    def find_job(self, job_id):
        jobs_endpoint = self.session.url_from_endpoint("jobs")

        data = {"limit": 1}
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

    def get_jobs(self, user_name, status, limit):
        data = {"limit": limit}
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
        pipeline_name,
        project_name,
        params,
        script,
        revision,
        build_source,
        build_context,
        profile=None,
        trace=False,
    ):
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

        if profile:
            data["profile"] = profile
        if trace:
            data["env"] = {"NXF_DEBUG": "3", "NXF_TRACE": "nextflow"}

        endpoint = self.session.url_from_endpoint("jobs")

        resp = self.session.post(endpoint, json=data)
        job = resp.json()
        return WorkflowJob(self.session, job["job_id"], job=job)

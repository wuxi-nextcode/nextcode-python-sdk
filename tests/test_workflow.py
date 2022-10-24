import responses
from unittest import mock
import datetime
from copy import deepcopy
import os

from nextcode import Client
from nextcode.exceptions import ServerError
from nextcode.services.workflow import weblog
from nextcode.services.workflow.exceptions import JobError
from tests import BaseTestCase, REFRESH_TOKEN, AUTH_RESP, AUTH_URL

# FIXME: We need to change this so we're validating against a openapi/swagger specification instead of this!
# FIXME: Until we do these tests aren't really testing anything!
WORKFLOW_URL = "https://test.wuxinextcode.com/workflow"
JOBS_URL = WORKFLOW_URL + "/jobs"
PIPELINES_URL = WORKFLOW_URL + "/pipelines"
PROJECTS_URL = WORKFLOW_URL + "/projects"
JOB_ID = 666
JOB_URL = JOBS_URL + "/{}".format(JOB_ID)
PROCESSES_URL = JOB_URL + "/processes"
PROCESS_URL = PROCESSES_URL + "/1"
EVENTS_URL = JOB_URL + "/events"
LOGS_URL = JOB_URL + "/logs"
ROOT_RESP = {
    "endpoints": {
        "health": WORKFLOW_URL + "/health",
        "documentation": WORKFLOW_URL + "/documentation",
        "jobs": JOBS_URL,
        "pipelines": PIPELINES_URL,
        "projects": PROJECTS_URL,
    },
    "current_user": {"email": "testuser"},
}

dt = datetime.datetime.utcnow().isoformat()
JOB_RESP = {
    "job_id": JOB_ID,
    "links": {
        "self": JOB_URL,
        "inspect": JOB_URL,
        "processes": PROCESSES_URL,
        "events": EVENTS_URL,
        "logs": LOGS_URL,
    },
    "complete_date": dt,
    "status_date": dt,
    "submit_date": dt,
    "status": "FINISHED",
}
JOBS_RESP = {"jobs": [JOB_RESP]}

PROCESS_RESP = {"process_id": 1}

PIPELINES_RESP = {
    "pipelines": [
        {
            "description": "Smoketest pipeline which is run without parameters to check if the service and dependencies is valid",
            "links": {
                "self": "https://platform-cluster.wuxinextcodedev.com/workflow/pipelines/smoketest"
            },
            "name": "smoketest",
            "parameters": None,
            "revision": None,
            "script": "https://gitlab.com/wuxi-nextcode/cohort/workflows/workflow-smoketest.git",
            "storage_type": "shared",
        }
    ]
}
PROJECTS_RESP = {
    "projects": [
        {
            "create_date": "2019-08-26T10:49:51.322125",
            "csa_file_path": "/mnt/csa/env/dev/projects/testing",
            "description": None,
            "internal_name": "testing",
            "links": {
                "self": "https://platform-cluster.wuxinextcodedev.com/workflow/projects/35"
            },
            "name": None,
            "project_id": 35,
        }
    ]
}


class WorkflowTest(BaseTestCase):
    def setUp(self):
        super(WorkflowTest, self).setUp()
        self.svc = self.get_service()

    @responses.activate
    def get_service(self):
        responses.add(responses.POST, AUTH_URL, json=AUTH_RESP)
        responses.add(responses.GET, WORKFLOW_URL, json=ROOT_RESP)

        client = Client(api_key=REFRESH_TOKEN)
        svc = client.service("workflow")
        svc.session._initialize()
        return svc

    @responses.activate
    def test_workflow_status(self):
        _ = self.svc.status()

    @responses.activate
    def test_workflow(self):

        svc = self.svc
        responses.add(responses.GET, WORKFLOW_URL + "/documentation", json={})
        ret = svc.openapi_spec()

        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.GET, WORKFLOW_URL + "/health")
            ret = svc.healthy()
            self.assertTrue(ret)

        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.GET, WORKFLOW_URL + "/health", status=404)
            ret = svc.healthy()
            self.assertFalse(ret)

    @responses.activate
    def test_find_job(self):
        responses.add(responses.GET, JOBS_URL, json=JOBS_RESP)

        job = self.svc.find_job(JOB_ID)

        job_id = "latest"
        job = self.svc.find_job(job_id)
        repr(job)

        job_id = "invalid"
        with self.assertRaises(Exception) as se:
            job = self.svc.find_job(job_id)

    @responses.activate
    def test_job_methods(self):
        responses.add(responses.GET, JOBS_URL, json=JOBS_RESP)
        responses.add(responses.GET, JOB_URL, json=JOB_RESP)
        responses.add(responses.PUT, JOB_URL, json=JOB_RESP)
        responses.add(responses.DELETE, JOB_URL, json={"status_message": "Cancelled"})
        job = self.svc.find_job(JOB_ID)
        _ = job.running
        _ = job.running
        _ = job.finished
        _ = job.finished
        _ = job.resume()
        _ = job.cancel()

    @responses.activate
    def test_inspect(self):
        responses.add(responses.GET, JOBS_URL, json=JOBS_RESP)
        responses.add(responses.GET, JOB_URL, json=JOB_RESP)
        responses.add(responses.PUT, JOB_URL, json=JOB_RESP)
        responses.add(responses.DELETE, JOB_URL, json={"status_message": "Cancelled"})
        job = self.svc.find_job(JOB_ID)
        _ = job.inspect()

        del job.links["inspect"]
        with self.assertRaises(ServerError):
            _ = job.inspect()

    @responses.activate
    def test_processes(self):
        responses.add(responses.GET, JOBS_URL, json=JOBS_RESP)
        responses.add(responses.GET, JOB_URL, json=JOB_RESP)
        responses.add(responses.GET, PROCESSES_URL, json={"processes": PROCESS_RESP})
        responses.add(responses.GET, PROCESS_URL, json=PROCESS_RESP)
        job = self.svc.find_job(JOB_ID)
        _ = job.processes()
        _ = job.processes(is_all=True)
        _ = job.processes(status="RUNNING")
        _ = job.processes(process_id=1)

    @responses.activate
    def test_events(self):
        responses.add(responses.GET, JOBS_URL, json=JOBS_RESP)
        responses.add(responses.GET, JOB_URL, json=JOB_RESP)
        responses.add(responses.GET, EVENTS_URL, json={"events": []})
        job = self.svc.find_job(JOB_ID)
        _ = job.events()

    @responses.activate
    def test_logs(self):
        responses.add(responses.GET, JOBS_URL, json=JOBS_RESP)
        responses.add(responses.GET, JOB_URL, json=JOB_RESP)
        log_group_url = "https://group1"
        responses.add(
            responses.GET, LOGS_URL, json={"links": {"group1": log_group_url}}
        )
        responses.add(responses.GET, log_group_url)
        responses.add(responses.GET, log_group_url + "?filter=bleh")
        job = self.svc.find_job(JOB_ID)
        _ = job.log_groups()
        with self.assertRaises(ServerError):
            job.logs("invalidgroup")
        job.logs("group1")
        job.logs("group1", log_filter="bleh")

        with self.assertRaises(AttributeError):
            job.invalid

    @responses.activate
    def test_job_duration(self):
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, JOBS_URL, json=JOBS_RESP)
            job = self.svc.find_job(JOB_ID)
            d = job.duration
            self.assertEqual(d, datetime.timedelta(0))
            job.complete_date = None
            job.status = None
            job.status_date = None
            d = job.duration
            self.assertEqual(d, "-")

        resp = deepcopy(JOBS_RESP)
        resp["jobs"][0]["complete_date"] = None
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, JOBS_URL, json=resp)
            job = self.svc.find_job(JOB_ID)
            d = job.duration
            self.assertEqual(d, datetime.timedelta(0))

        resp["jobs"][0]["status"] = "STARTED"
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, JOBS_URL, json=resp)
            job = self.svc.find_job(JOB_ID)
            d = job.duration

    @responses.activate
    def test_get_jobs(self):
        responses.add(responses.GET, JOBS_URL, json=JOBS_RESP)
        user_name = "user_name"
        status = "status"
        ret = self.svc.get_jobs(user_name, status, 666)

    @responses.activate
    def test_post_job(self):
        responses.add(responses.POST, JOBS_URL, json=JOBS_RESP["jobs"][0])

        pipeline_name = "pipeline_name"
        project_name = "project_name"
        params = {}
        script = None
        revision = None
        build_source = "builtin"
        build_context = None
        profile = "test"
        storage_type = "dedicated"
        scheduler_name = "custom-scheduler"

        job = self.svc.post_job(
            pipeline_name,
            project_name,
            params,
            script,
            revision,
            build_source,
            build_context,
            profile,
            storage_type,
            scheduler_name,
        )
        self.assertEqual(666, job.job_id)

    @responses.activate
    def test_post_job_with_creds(self):
        responses.add(responses.POST, JOBS_URL, json=JOBS_RESP["jobs"][0])

        pipeline_name = "pipeline_name"
        project_name = "project_name"
        params = {}
        script = None
        revision = None
        build_source = "builtin"
        build_context = None
        profile = "test"
        storage_type = "dedicated"
        enable_fast_local_storage = True,
        credentials = {
            "ukbb_readonly": {
                "aws_access_key_id": "AKIALKIADSFASJGASGDS",
                "aws_secret_access_key": "Aj39sadfljhdslafjasls",
            }
        }
        scheduler_name = "custom-scheduler"

        job = self.svc.post_job(
            pipeline_name,
            project_name,
            params,
            script,
            revision,
            build_source,
            build_context,
            profile,
            storage_type,
            enable_fast_local_storage,
            credentials,
            scheduler_name,
        )
        self.assertEqual(666, job.job_id)

    @responses.activate
    def test_pipelines(self):
        responses.add(responses.GET, PIPELINES_URL, json=PIPELINES_RESP)
        pipelines = self.svc.get_pipelines()
        self.assertEqual(pipelines, PIPELINES_RESP["pipelines"])

    @responses.activate
    def test_project(self):
        responses.add(responses.GET, PROJECTS_URL, json=PROJECTS_RESP)
        projects = self.svc.get_projects()
        self.assertEqual(projects, PROJECTS_RESP["projects"])

    @responses.activate
    def test_wait(self):
        responses.add(responses.POST, JOBS_URL, json=JOBS_RESP["jobs"][0])

        pipeline_name = "pipeline_name"
        project_name = "project_name"
        params = {}
        script = None
        revision = None
        build_source = "builtin"
        build_context = None
        profile = "test"

        job = self.svc.post_job(
            pipeline_name,
            project_name,
            params,
            script,
            revision,
            build_source,
            build_context,
            profile,
        )
        job.status = "STARTED"
        responses.add(responses.GET, JOB_URL, json=JOB_RESP)
        with self.assertRaises(JobError):
            job.wait(max_seconds=1)
        _ = job.done
        _ = job.failed


class WeblogTest(BaseTestCase):
    def setUp(self):
        super(WeblogTest, self).setUp()
        self.url = "http://test.local/"
        os.environ["WEBLOG_URL"] = self.url
        responses.add(responses.GET, self.url)
        responses.add(responses.POST, self.url)

    @responses.activate
    def test_add_to_details(self):
        weblog.add_to_details("key")

    @responses.activate
    def test_set_details(self):
        weblog.set_details("key", "value")

    @responses.activate
    def test_set_status_message(self):
        weblog.set_status_message("msg")

    def test_noenviron(self):
        os.environ["WEBLOG_URL"] = ""
        weblog.add_to_details("key")
        weblog.set_details("key", "value")
        weblog.set_status_message("msg")

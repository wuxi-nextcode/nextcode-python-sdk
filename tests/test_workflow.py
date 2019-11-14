import responses
from unittest import mock
import datetime
from copy import deepcopy

from nextcode import Client
from tests import BaseTestCase, REFRESH_TOKEN, AUTH_RESP, AUTH_URL

WORKFLOW_URL = "https://test.wuxinextcode.com/workflow"
JOBS_URL = WORKFLOW_URL + "/jobs"
JOB_ID = 666
JOB_URL = JOBS_URL + "/{}".format(JOB_ID)
PROCESSES_URL = JOB_URL + "/processes"
ROOT_RESP = {
    "endpoints": {
        "health": WORKFLOW_URL + "/health",
        "documentation": WORKFLOW_URL + "/documentation",
        "jobs": JOBS_URL,
    },
    "current_user": {"email": "testuser"},
}

dt = datetime.datetime.utcnow().isoformat()
JOB_RESP = {
    "job_id": JOB_ID,
    "links": {"self": JOB_URL, "inspect": JOB_URL, "processes": PROCESSES_URL},
    "complete_date": dt,
    "status_date": dt,
    "submit_date": dt,
    "status": "FINISHED",
}
JOBS_RESP = {"jobs": [JOB_RESP]}


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
        _ = job.running(True)
        _ = job.finished(True)
        _ = job.resume()
        _ = job.cancel()
        _ = job.inspect()
        # _ = job.processes()

    @responses.activate
    def test_job_duration(self):
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, JOBS_URL, json=JOBS_RESP)
            job = self.svc.find_job(JOB_ID)
            d = job.duration
            self.assertEqual(d, datetime.timedelta(0))

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

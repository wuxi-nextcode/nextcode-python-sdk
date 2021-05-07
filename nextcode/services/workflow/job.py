"""
Workflow Job
------------------

The Query class represents a workflow job model from the RESTFul Workflow Service API

"""
import configparser
import json
import datetime
import os

import botocore.session
import dateutil
import time
import logging
from typing import Callable, Union, Optional, Dict, List

from . import RUNNING_STATUSES, FINISHED_STATUSES, FAILED_STATUSES
from .exceptions import JobError
from ...exceptions import ServerError
from ...session import ServiceSession

log = logging.getLogger(__name__)


class WorkflowJob:
    """
    Proxy object for a serverside workflow job.

    This object can be queried for the current status of a workflow job and will
    automatically refresh from server until the job is finished (or failed)
    """

    def __init__(self, session: ServiceSession, job_id: int, job: Dict):
        self.session = session
        self.job = job
        self.job_id = self.job["job_id"]
        self.links = self.job["links"]

    def __repr__(self) -> str:
        return json.dumps(self.job)

    @property
    def duration(self) -> str:
        """
        Stringified duration of job for human consumption
        """
        if self.complete_date:
            complete_date = self.complete_date
        elif self.status in RUNNING_STATUSES:
            complete_date = datetime.datetime.utcnow()
        elif self.status_date:
            complete_date = self.status_date
        else:
            return "-"
        ret = complete_date - self.submit_date
        # remove microseconds since no one wants them
        ret = ret - datetime.timedelta(microseconds=ret.microseconds)
        return ret

    @property
    def finished(self) -> bool:
        """
        Has the job finished (might be failed)
        """
        if self.status in RUNNING_STATUSES:
            self.refresh()
        return self.status in FINISHED_STATUSES

    @property
    def running(self) -> bool:
        """
        Is the job currently running
        """
        if self.status in RUNNING_STATUSES:
            self.refresh()
        return self.status in RUNNING_STATUSES

    @property
    def failed(self) -> bool:
        """
        Is the job in a failed state
        """
        if self.status in RUNNING_STATUSES:
            self.refresh()
        return self.status in FAILED_STATUSES

    @property
    def done(self) -> bool:
        """
        Has the job completed successfully
        """
        if self.status in RUNNING_STATUSES:
            self.refresh()
        return self.status == "COMPLETED"

    def refresh(self) -> None:
        """
        Refresh the local cache of the serverside job object
        """
        self.job = self.session.get(self.links["self"]).json()

    def resume(self) -> None:
        """
        Rerun a job that has previously failed
        """
        _ = self.session.put(self.links["self"])
        self.refresh()

    def wait(self, max_seconds: Optional[int] = None, poll_period: float = 0.5):
        """
        Wait for a running job to complete.

        This is similar to the wait method in the Query Service and will wait by default
        indefinitely for a workflow job to complete and poll the server regularly to update
        the local status. When the job is completed (or failed) the method will return the
        workflow job object.

        :param max_seconds: raise an exception if the job runs longer than this
        :param poll_period: Number of seconds to wait between polling (max 10 seconds)
        :returns: WorkflowJob
        :raises: :exc:`JobError`
        """
        if not self.running:
            return self
        log.info("Waiting for job %s to complete...", self.job_id)
        start_time = time.time()
        duration = 0.0
        period = poll_period
        is_running = self.running
        while is_running:
            time.sleep(period)
            duration = time.time() - start_time
            is_running = self.running

            # cancel the wait if the executor pod is in trouble after 30 seconds of waiting to start.
            # it most likely means that the nextflow script has a syntax error or something.
            if self.status == "PENDING" and (
                max_seconds and duration > max_seconds or duration > 30.0
            ):
                log.info("Job has been PENDING for %.0fsec. Inspecting it...", duration)
                curr_status = self.inspect()
                executor_pod = None
                for pod in curr_status["pods"]:
                    if pod["metadata"]["labels"]["app-name"] == "nextflow-executor":
                        executor_pod = pod
                        break
                if not executor_pod:
                    log.warning(
                        "Job is still pending after %.0fsec and executor pod is missing",
                        duration,
                    )
                    raise JobError(
                        f"Job is still pending after {duration:.0f}s and executor pod is missing. View logs or inspect job for failures."
                    )
                if not executor_pod["status"]["container_statuses"][0]["state"][
                    "running"
                ]:
                    log.warning(
                        "Job is still pending after %.0fsec and executor pod is not in running state",
                        duration,
                    )
                    raise JobError(
                        f"Job is still pending after {duration:.0f}s and executor pod is not in running state. View logs or inspect job for failures."
                    )

            if is_running and max_seconds and duration > max_seconds:
                raise JobError(
                    f"Job {self.job_id} has exceeded wait time {max_seconds}s and we will not wait any longer. It is currently {self.status}."
                )

            period = min(period + 0.5, 10.0)
        if self.status == "DONE":
            log.info(
                "Job %s completed in %.2f sec and returned %s rows",
                self.job_id,
                duration,
                self.line_count,
            )
        else:
            log.info(
                "Job %s has status %s after %.2f sec",
                self.job_id,
                self.status,
                duration,
            )
        return self

    def cancel(
        self, status: Optional[str] = None, status_message: Optional[str] = None
    ) -> Optional[str]:
        """
        Cancel a running job

        :param status: status of the cancelled job. Defaults to CANCELLED
        :returns: Status message from the server
        """
        data: Dict = {}
        data["status"] = status or "CANCELLED"
        data["status_message"] = status_message
        resp = self.session.delete(self.links["self"], json=data)
        status_message = resp.json()["status_message"]
        return status_message

    def inspect(self) -> Dict:
        """
        Inspect a failed job for debugging.

        Returns unfiltered pod and node information from the kubernetes system

        :returns: Dictionary containing low-level debugging information
        :raises: :exc:`ServerError` if the server is not configured for inspection capabilities
        """
        try:
            url = self.links["inspect"]
        except KeyError:
            raise ServerError("Server does not support inspect functionality")
        resp = self.session.get(url)
        return resp.json()

    def cost(self, recalculate: bool = False) -> Dict:
        """
        Get the estimates cost of this job.
        :param recalculate: If set to True then the cost will be recalculated.
        """
        url = self.links["cost"]
        data = {}
        if recalculate:
            data["recalculate"] = "true"

        resp = self.session.get(url, json=data)
        return resp.json()

    def processes(
        self,
        process_id: Optional[int] = None,
        is_all: bool = False,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get a list of all nextflow processes in this job

        :param process_id: process_id to show
        :param is_all: Show all processes, otherwise show only running processes
        :param limit: Maximum number of processes to return
        :param status: Filter processes by status
        """
        url = self.links["processes"]
        if process_id:
            url += "/%s" % process_id
            resp = self.session.get(url)
            return [resp.json()]
        else:
            data: Dict = {"limit": limit}
            if is_all:
                data["all"] = 1
            if status:
                data["status"] = status
            resp = self.session.get(url, json=data)
            return resp.json()["processes"]

    def events(self, limit: int = 50) -> List[Dict]:
        """
        Get a list of events reported by Nextflow for this job

        :param limit: Maximum number of events to return
        """
        url = self.links["events"]
        data = {"limit": limit}
        resp = self.session.get(url, json=data)
        return resp.json()["events"]

    def log_groups(self) -> Dict:
        """
        Get available log groups

        :returns: Dictionary with log group name and server url to the log group
        """
        logs_url = self.links["logs"]
        resp = self.session.get(logs_url)
        return resp.json()["links"]

    def logs(self, log_group: str = "pod", log_filter: Optional[str] = None) -> str:
        """
        Get text logs for the specified log group

        :param log_group: Name of the log group to view
        :param log_filter: Optional filter to apply to the logs
        :raises: :exc:`ServerError` If the log group is not available
        """
        groups = self.log_groups()
        url = None
        for k, v in groups.items():
            if k.startswith(log_group):
                url = v
                break
        if not url:
            raise ServerError(f"Log Group '{log_group}' is not available.")
        if log_filter:
            url += "?filter=%s" % log_filter
        logs = self.session.get(url).text
        return logs

    def __getattr__(self, name):
        try:
            val = self.job[name]
        except KeyError:
            raise AttributeError

        if name.endswith("_date") and val:
            val = dateutil.parser.parse(val)
        return val

"""
Pipeline Job
------------------

The PipelineJob class represents a pipelines job model from the RESTFul Workflow Service API

"""

import json
import datetime
import dateutil
import time
import logging
from typing import Callable, Union, Optional, Dict, List

from . import RUNNING_STATUSES, FINISHED_STATUSES, FAILED_STATUSES
from .exceptions import JobError
from ...exceptions import ServerError
from ...session import ServiceSession

log = logging.getLogger(__name__)


def _smart_cast(name, val):
    if not val:
        return val
    if name.startswith("date_"):
        try:
            val = dateutil.parser.parse(val)
        except Exception:
            pass
    else:
        try:
            val = int(val)
        except:
            try:
                val = float(val)
            except:
                pass
    return val


class PipelineJob:
    """
    Proxy object for a serverside pipeline job.

    This object can be queried for the current status of a pipeline job and will
    automatically refresh from server until the job is finished (or failed)
    """

    def __init__(self, session: ServiceSession, job_id: int, job: Dict):
        self.session = session
        self.job = job
        self.job_id = self.job["job_id"]
        self.links = self.job["links"]

    def __repr__(self) -> str:
        return f"<Pipeline Job {self.job_id} ({self.status})>"

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

    def steps(self) -> List[Dict]:
        """
        Get a list of all nextflow processes in this job
        """
        url = self.links["steps"]
        resp = self.session.get(url)
        steps = resp.json()
        for step in steps:
            for k, v in step.items():
                step[k] = _smart_cast(k, v)
        return steps

    def instance(self) -> Dict:
        """
        Get instance information for this job
        """
        url = self.links["instances"]
        resp = self.session.get(url)
        url = resp.json()[0]["links"]["self"]
        ret = self.session.get(url).json()
        return ret

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

        val = _smart_cast(name, val)
        return val

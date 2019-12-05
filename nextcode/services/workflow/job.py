"""
Workflow Job
------------------

The Query class represents a workflow job model from the RESTFul Workflow Service API

"""

import json
import datetime
import dateutil
from typing import Callable, Union, Optional, Dict, List

from . import RUNNING_STATUSES, FINISHED_STATUES
from ...exceptions import ServerError
from ...session import ServiceSession


class WorkflowJob:
    """
    Proxy object for a serverside workflow job
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

    def running(self, force: bool = False) -> bool:
        """
        If the job currently running
        """
        if force:
            self.refresh()
        return self.status in RUNNING_STATUSES

    def finished(self, force: bool = False) -> bool:
        """
        Has the job finished
        """
        if force:
            self.refresh()
        return self.status in FINISHED_STATUES

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

    def cancel(
        self, status: Optional[str] = None, status_message: Optional[str] = None
    ) -> Optional[str]:
        """
        Cancel a running job

        :param status: status of the cancelled job. Defaults to CANCELLED
        """
        data: Dict = {}
        data["status"] = status or "CANCELLED"
        data["status_message"] = status_message
        resp = self.session.delete(self.links["self"], json=data)
        status_message = resp.json()["status_message"]
        return status_message

    def inspect(self) -> Dict:
        """
        Inspect a failed job for debugging
        """
        try:
            url = self.links["inspect"]
        except KeyError:
            raise ServerError("Server does not support inspect functionality")
        resp = self.session.get(url)
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
        """
        logs_url = self.links["logs"]
        resp = self.session.get(logs_url)
        return resp.json()["links"]

    def logs(self, log_group: str, log_filter: Optional[str] = None) -> str:
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

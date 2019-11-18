import json
import datetime
import dateutil
from . import RUNNING_STATUSES, FINISHED_STATUES
from ...exceptions import ServerError


class WorkflowJob:
    def __init__(self, session, job_id, job):
        self.session = session
        self.job = job
        self.job_id = self.job["job_id"]
        self.links = self.job["links"]

    def __repr__(self):
        return json.dumps(self.job)

    @property
    def duration(self):
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

    def running(self, force=False):
        if force:
            self.refresh()
        return self.status in RUNNING_STATUSES

    def finished(self, force=False):
        if force:
            self.refresh()
        return self.status in FINISHED_STATUES

    def refresh(self):
        self.job = self.session.get(self.links["self"]).json()

    def resume(self):
        _ = self.session.put(self.links["self"])
        self.refresh()

    def cancel(self):
        resp = self.session.delete(self.links["self"])
        status_message = resp.json()["status_message"]
        return status_message

    def inspect(self):
        try:
            url = self.links["inspect"]
        except KeyError:
            raise ServerError("Server does not support inspect functionality")
        resp = self.session.get(url)
        return resp.json()

    def processes(self, process_id=None, is_all=False, limit=50, status=None):
        url = self.links["processes"]
        if process_id:
            url += "/%s" % process_id
            resp = self.session.get(url)
            return [resp.json()]
        else:
            data = {"limit": limit}
            if is_all:
                data["all"] = 1
            if status:
                data["status"] = status
            resp = self.session.get(url, json=data)
            return resp.json()["processes"]

    def events(self, limit=50):
        url = self.links["events"]
        data = {"limit": limit}
        resp = self.session.get(url, json=data)
        return resp.json()["events"]

    def log_groups(self):
        logs_url = self.links["logs"]
        resp = self.session.get(logs_url)
        return resp.json()["links"]

    def logs(self, log_group, log_filter=None):
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

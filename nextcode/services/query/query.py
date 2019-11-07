"""
Query-API Query
------------------

The Query class represents a query model from the RESTFul Query API

"""

import logging
import time
from typing import Dict, Tuple, Sequence, List, Optional, Union
from dateutil.parser import parse

try:
    import pandas as pd

    jupyter_available = True
except ImportError:
    jupyter_available = False

from io import StringIO

from .exceptions import QueryError

SERVICE_PATH = "/api/query"

RUNNING_STATUSES = ("PENDING", "RUNNING", "CANCELLING")
RESULTS_PAGE_SIZE = 200000

log = logging.getLogger(__name__)


class Query:
    """
    A local proxy representing a serverside Gor Query.
    This object is returned from query methods in the 'query' service.

    :param service: query service handle
    :param resp: json response from query api endpoint

    Example usage:

    >>> svc = nextcode.Client(profile_name='test').service('query', project='myproject')
    >>> query = svc.get_queries(limit=1)[0]
    >>> query.status
    'DONE'
    """

    query_id = None
    url = None
    duration = None
    query = None
    status = None

    def __init__(self, service, resp: Optional[Dict] = None):
        self.service = service
        self.session = service.session
        if resp:
            self.init_from_resp(resp)

    def init_from_resp(self, resp: Dict):
        """
        Initialize the query object from a server json response.
        If the response is a 'simple query', e.g. from the queries list
        the object will only contain partial information.
        If the caller requests a field that is not included in the local proxy object
        the query will be refreshed from the server.
        """
        # make sure the url is set

        self.url = resp["links"]["self"]
        self.raw = resp
        self.__dict__.update(resp)
        self.submit_date = parse(resp["submit_date"])
        if "stats" in resp:
            stats = resp["stats"]
            self.__dict__.update(resp["stats"])
            if stats.get("end_timestamp"):
                self.duration = stats.get("end_timestamp") - stats.get(
                    "submit_timestamp"
                )

    def __repr__(self):
        return f"<GorQuery {self.query_id or 'NEW'} ({self.status})>"

    def __getattr__(self, name):
        # if we cannot find the attribute we refresh the query from the server
        # just in case we have a partial object
        self.refresh()
        if name in self.__dict__:
            return self.__dict__[name]
        else:
            raise AttributeError()

    def running(self) -> bool:
        """
        Is the query currently running
        """
        if self.status in RUNNING_STATUSES:
            self.refresh()
        return self.status in RUNNING_STATUSES

    def wait(self, max_seconds: Optional[int] = None):
        """
        Wait for the query to complete

        :param max_seconds: raise an exception if the query runs longer than this

        :raises: QueryError
        """
        if not self.running():
            return self
        log.info("Waiting for query %s to complete...", self.query_id)
        start_time = time.time()
        duration = 0.0
        period = 0.5
        while self.running():
            time.sleep(period)
            duration = time.time() - start_time
            if max_seconds and duration > max_seconds:
                raise QueryError(
                    f"Query {self.query_id} has status {self.status} after {max_seconds} seconds"
                )
            period = min(period + 0.5, 5.0)
        if self.status == "DONE":
            log.info(
                "Query %s completed in %.2f sec and returned %s rows",
                self.query_id,
                duration,
                self.line_count,
            )
        else:
            log.info(
                "Query %s has status %s after %.2f sec",
                self.query_id,
                self.status,
                duration,
            )
        return self

    def refresh(self):
        """
        Refresh the local query object from the RESTful service
        """
        if not self.url:
            return
        resp = self.session.get(self.url)
        self.init_from_resp(resp.json())
        return self

    def get_results(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort: Optional[str] = None,
        is_json: bool = True,
    ) -> Union[Dict, str]:
        """
        Returns results from a completed query, optionally with limit and offset

        :param limit: number of rows to return (default all)
        :param offset: number of rows to skip
        :param sort: gor sort string in format '[column] [ASC|DESC]'
        :param is_json: return rows as a dictionary containing 'header' and 'data'
        :returns: dictonary containing 'header' and 'data' lists or tsv
        :raises: QueryError

        """
        start_time = time.time()
        url = self.links["result"]
        if self.status != "DONE":
            raise QueryError(f"Query {self.query_id} is {self.status}")
        if not self.available:
            raise QueryError(
                "Query results for query {self.query_id} are not available"
            )
        accept = "application/json+compact" if is_json else "text/tab-separated-values"

        responses = []
        num_rows_total = self.line_count or 0
        num_rows_to_fetch = num_rows_total
        if limit:
            num_rows_to_fetch = min(num_rows_total, limit)
        num_rows_received = 0
        skip_header = False
        if num_rows_to_fetch > RESULTS_PAGE_SIZE:
            log.info(
                "Requesting %s rows in %s rows per page...",
                num_rows_to_fetch,
                min(RESULTS_PAGE_SIZE, num_rows_to_fetch),
            )
        while num_rows_received < num_rows_to_fetch:
            num_rows_remaining = num_rows_to_fetch - num_rows_received
            num_rows_to_fetch_this_time = min(num_rows_remaining, RESULTS_PAGE_SIZE)
            data = {
                "limit": num_rows_to_fetch_this_time,
                "offset": num_rows_received,
                "sort": sort,
                "skipheader": skip_header,
            }
            skip_header = True
            st = time.time()
            resp = self.session.get(url, json=data, headers={"Accept": accept})
            diff = time.time() - st
            num_rows_received += num_rows_to_fetch_this_time
            responses.append(resp)
            log.debug(
                "Fetched %s rows this time in %.1fsec. Received %s/%s rows",
                num_rows_to_fetch_this_time,
                diff,
                num_rows_received,
                num_rows_to_fetch,
            )
        ret: Union[Dict, str]
        if is_json:
            ret = {}
            for r in responses:
                contents = r.json()
                if "data" not in ret:
                    ret["header"] = contents["header"]
                    ret["data"] = []
                ret["data"].extend(contents["data"])
        else:
            ret = ""
            for r in responses:
                ret += r.text
        log.info(
            "Retrieved %s rows from server in %.2f sec",
            num_rows_received,
            (time.time() - start_time),
        )
        return ret

    def cancel(self):
        if self.status not in RUNNING_STATUSES:
            raise QueryError("Query is not running")
        self.session.delete(self.url)

    def dataframe(self, limit=None):
        if not jupyter_available:
            raise QueryError("Pandas library is not installed")
        tsv_data = self.get_results(is_json=False, limit=limit)
        if not tsv_data:
            return pd.DataFrame()
        df = pd.read_csv(StringIO(tsv_data), delimiter="\t")
        return df

"""
Query Object
------------------

The Query class represents a query model from the RESTFul Query API.

There are several helper methods available here but you can view the
raw server response in the `raw` member.

Note that the object is dynamic and some of the attributes available are not
documented here because they are added from the server response.
"""

import logging
import time
from typing import Dict, Tuple, Sequence, List, Optional, Union, Callable
from dateutil.parser import parse
import os

from io import StringIO

from .exceptions import QueryError
from ...utils import jupyter_available

SERVICE_PATH = "/api/query"

RUNNING_STATUSES = ("PENDING", "RUNNING", "CANCELLING")
FAILED_STATUSES = ("CANCELLING", "CANCELLED", "FAILED")
RESULTS_PAGE_SIZE = 1000000

log = logging.getLogger(__name__)


def _log_download_progress(
    num_chunk,
    num_bytes,
    num_lines,
    total_received_lines,
    total_expected_lines,
    start_time,
    callback=None,
):
    """
    Helper for logging out download progress and notifying a listener or delta lines
    """
    mb = num_bytes / 1024 / 1024
    if callback:
        callback(num_lines)
    diff = time.time() - start_time
    if num_chunk is not None and num_chunk % 1000 == 0:
        msg = f"Downloaded {total_received_lines}/{total_expected_lines} lines ({mb:.2f} MB) in {diff:.2f} sec"
        log.info(msg)


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

    raw: Dict = {}
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

    @property
    def running(self) -> bool:
        """
        Is the query currently running
        """
        if self.status in RUNNING_STATUSES:
            self.refresh()
        return self.status in RUNNING_STATUSES

    @property
    def failed(self) -> bool:
        """
        Is the query in a failed state
        """
        if self.status in RUNNING_STATUSES:
            self.refresh()
        return self.status in FAILED_STATUSES

    @property
    def done(self) -> bool:
        """
        Is the query in the DONE state
        """
        if self.status in RUNNING_STATUSES:
            self.refresh()
        return self.status == "DONE"

    @property
    def perspectives(self) -> List[str]:
        """
        Returns a list of perspectives available for this query.

        This only applies to template queries. If this is an ad-hoc query the list will be empty.
        """
        perspective_links = self.raw["links"].get("perspectives") or []
        ret = [p["name"] for p in perspective_links]
        return ret

    def wait(self, max_seconds: Optional[int] = None, poll_period: float = 0.5):
        """
        Wait for the query to complete

        :param max_seconds: raise an exception if the query runs longer than this
        :param poll_period: Number of seconds to wait between polling (max 10 seconds)

        :raises: QueryError
        """
        if not self.running:
            return self
        log.info("Waiting for query %s to complete...", self.query_id)
        start_time = time.time()
        duration = 0.0
        period = poll_period
        is_running = self.running
        while is_running:
            time.sleep(period)
            duration = time.time() - start_time
            is_running = self.running
            if is_running and max_seconds and duration > max_seconds:
                raise QueryError(
                    f"Query {self.query_id} has exceeded wait time {max_seconds}s and we will not wait any longer. It is currently {self.status}."
                )
            period = min(period + 0.5, 10.0)
        if self.status == "DONE":
            log.info(
                "Query %s completed in %.2f sec and generated %s rows",
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

    def download_results(self, filename, callback=None):
        """
        Download the entire results for the query to a local file in a single call
        via streaming.
        :param filename: Local filename to save results to
        :raises: QueryError if data is missing.
        """
        filename = os.path.expanduser(filename)
        start_time = time.time()
        try:
            url = self.links["streamresults"]
        except KeyError:
            raise Exception(
                "Server does not support result downloading via streaming"
            ) from None
        num_bytes = 0
        num_lines = 0
        total_expected_lines = 0
        with open(filename, "wb") as f:
            with self.session.get(
                url, headers={"Accept": "text/tab-separated-values"}, stream=True
            ) as r:
                r.raise_for_status()
                total_expected_lines = int(r.headers.get("Line-Count", -1))
                log.info(f"Starting to stream {total_expected_lines} lines...")
                total_received_lines = 0
                for i, chunk in enumerate(r.iter_content(chunk_size=8192)):
                    num_bytes += len(chunk)
                    num_lines = chunk.count(b"\n")
                    total_received_lines += num_lines
                    f.write(chunk)

                    _log_download_progress(
                        i,
                        num_bytes,
                        num_lines,
                        total_received_lines,
                        total_expected_lines,
                        start_time,
                        callback,
                    )

        _log_download_progress(
            0,
            num_bytes,
            num_lines,
            total_received_lines,
            total_expected_lines,
            start_time,
            callback,
        )
        if total_received_lines < total_expected_lines:
            raise QueryError(
                f"Downloaded {total_received_lines} lines but {total_expected_lines} lines expected"
            )
        return filename

    def get_results(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort: Optional[str] = None,
        filt: Optional[str] = None,
        perspective: Optional[str] = None,
        is_json: bool = True,
        callback: Optional[Callable] = None,
    ) -> Union[Dict, str]:
        """
        Returns results from a completed query, optionally with limit and offset

        :param limit: number of rows to return (default all)
        :param offset: number of rows to skip
        :param sort: gor sort string in format '[column] [ASC|DESC]'
        :param filt: filter to apply to the results serverside
        :param perspective: perspective name to apply to results (for template queries)
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
                f"Query results for query {self.query_id} are not available"
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
                "filt": filt,
                "perspective": perspective,
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
            if callback:
                callback(received=num_rows_received, total=num_rows_total)
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
        """
        Cancel a running query

        :raises QueryError: Query is not in a running state
        """
        if self.status not in RUNNING_STATUSES:
            raise QueryError("Query is not running")
        self.session.delete(self.url)

    def dataframe(self, limit: Optional[int] = None):
        """
        Return a Pandas dataframe object containing the results of this query

        :param limit: Maximum number of rows to return (default all)
        :raises QueryError: If the pandas library is not installed
        :return: Pandas dataframe object
        """
        if not jupyter_available():
            raise QueryError("Pandas library is not installed")
        tsv_data = self.get_results(is_json=False, limit=limit)
        import pandas as pd

        if not tsv_data:
            return pd.DataFrame()
        df = pd.read_csv(StringIO(tsv_data), delimiter="\t")  # type: ignore
        return df

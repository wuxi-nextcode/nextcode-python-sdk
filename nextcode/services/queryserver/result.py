"""
Query result object for Query Server queries.
"""
import json
import logging
import time
import zlib
from typing import Optional
from io import StringIO

from requests import Response

from nextcode.exceptions import ServerError
from nextcode.services.query.exceptions import QueryError, MissingRelations
from nextcode.utils import jupyter_available

log = logging.getLogger(__name__)


class Result(object):
    """
    Query result object for Query Server queries.
    """
    def __init__(self, resp: Response, gzip: bool):
        self.resp = resp
        self.open = True
        self.start_time = time.time()
        self.num_bytes = 0
        self.num_lines = -1  # For the header.
        self.gzip = gzip

    def iter_lines(self, limit: Optional[int] = None, callback=None):
        """
        Return iterator to iterate through the result.
        :param limit: Maximum number of rows to return (default all)
        :param callback: callback for progress
        :return: iterator
        """
        self.__check_open__()
        self.start_time = time.time()
        log.info(f"Starting to stream lines...")
        for line in self.iter_lines_unzip(decode_unicode=False, delimiter=b'\n'):

            if line:
                if line.startswith(b'#> EXCEPTION'):
                    throw_error_from_line(line.decode('utf-8'))
                elif line.startswith(b'#>'):
                    continue

                self.num_lines += 1
                self.num_bytes += len(line)

                if self.num_lines % 10000 == 0:
                    _log_download_progress(
                        self.num_lines / 10000,
                        self.num_bytes,
                        self.num_lines,
                        self.num_lines,
                        1,
                        self.start_time,
                        callback,
                    )

                if limit is not None and self.num_lines > limit:
                    break

                yield line.decode('utf-8')
        self.__close_response__()

    def lines(self, limit: Optional[int] = None):
        """
        Get query result lines in one string.
        :param limit: Maximum number of rows to return (default all).
        :return: query result lines in one string.
        """
        result_text: str = ""
        for line in self.iter_lines(limit):
            if len(result_text) > 0:
                result_text += '\n'
            result_text += line
        return result_text

    def content(self):
        """Content of the result, in bytes."""
        self.__check_open__()
        content = self.resp.content
        self.__close_response__()
        return content

    def text(self):
        """Content of the result, in unicode."""
        self.__check_open__()
        text = self.resp.text
        self.__close_response__()
        return text

    def dataframe(self, limit: Optional[int] = None):
        """
        Return a Pandas dataframe object containing the results of this query.

        :param limit: Maximum number of rows to return (default all).
        :raises QueryError: If the pandas library is not installed.
        :return: Pandas dataframe object.
        """
        if not jupyter_available():
            raise QueryError("Pandas library is not installed")
        tsv_data = self.lines(limit=limit)

        import pandas as pd
        if not tsv_data:
            return pd.DataFrame()
        df = pd.read_csv(StringIO(tsv_data), delimiter="\t")  # type: ignore
        return df

    def cancel(self):
        self.__close_response__()

    def __close_response__(self):
        self.resp.close()
        self.open = False

    def __check_open__(self):
        if not self.open:
            raise Exception("Response has been closed, data can not been accessed")

    ITER_CHUNK_SIZE = 512

    def iter_lines_unzip(self, chunk_size=ITER_CHUNK_SIZE, decode_unicode=False, delimiter=None):
        """Iterates over the response data, one line at a time.  When
        stream=True is set on the request, this avoids reading the
        content at once into memory for large responses.

        .. note:: This method is not reentrant safe.
        """

        pending = None

        d = zlib.decompressobj(16+zlib.MAX_WBITS)

        for chunk in self.resp.iter_content(chunk_size=chunk_size, decode_unicode=decode_unicode):

            if self.gzip:
                chunk = d.decompress(chunk)

            if pending is not None:
                chunk = pending + chunk

            if delimiter:
                lines = chunk.split(delimiter)
            else:
                lines = chunk.splitlines()

            if lines and lines[-1] and chunk and lines[-1][-1] == chunk[-1]:
                pending = lines.pop()
            else:
                pending = None

            for line in lines:
                yield line

        if pending is not None:
            yield pending


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


def throw_error_from_line(line):
    if line.startswith("#> EXCEPTION") and line.find('{') > -1:
        # Assume this is an exception from Query Server with embedded json.
        json_ex = json.loads(line[line.find('{'):line.rfind('}')+1])
        if "errorType" in json_ex and json_ex["errorType"] == "GorMissingRelationException":
            raise MissingRelations(
                [r for r in json_ex["uri"].split(',')]
            )
        else:
            raise ServerError(json_ex["gorMessage"])
    else:
        raise ServerError("Error while running query.\n{}".format(line))

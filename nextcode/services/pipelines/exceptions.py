"""
Exceptions
~~~~~~~~~~

Custom exceptions raised by the pipelines service.

"""

from typing import List


class JobError(Exception):
    def __init__(self, message: str, job_id: int = None):
        self.job_id = job_id

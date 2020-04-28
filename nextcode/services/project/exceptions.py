"""
Exceptions
~~~~~~~~~~

Custom exceptions raised by the projects service.

"""

from typing import List


class ProjectError(Exception):
    def __init__(self, message: str, job_id: int = None):
        self.job_id = job_id

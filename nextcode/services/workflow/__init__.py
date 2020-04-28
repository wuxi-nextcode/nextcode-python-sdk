"""
Workflow Service
------------------
Service object for interfacing with the Workflow service API

"""
INIT_STATUSES = ("PENDING",)
RUNNING_STATUSES = ("PENDING", "STARTED")
FAILED_STATUSES = ("ERROR", "KILLED")
FINISHED_STATUSES = ("CANCELLED", "COMPLETED") + FAILED_STATUSES

from .service import Service

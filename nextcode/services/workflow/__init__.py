"""
Workflow Service
------------------
Service object for interfacing with the Workflow service API

"""
INIT_STATUSES = ("PENDING",)
RUNNING_STATUSES = ("PENDING", "STARTED")
FAILED_STATUES = ("ERROR", "KILLED")
FINISHED_STATUES = ("CANCELLED", "COMPLETED") + FAILED_STATUES

from .service import Service

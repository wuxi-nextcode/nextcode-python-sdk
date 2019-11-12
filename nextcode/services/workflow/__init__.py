"""
Workflow Service
------------------
Service object for interfacing with the Workflow service API

"""
INIT_STATUSES = ("PENDING",)
RUNNING_STATUSES = ("PENDING", "STARTED")
FINISHED_STATUES = ("CANCELLED", "COMPLETED", "ERROR")

from .service import Service

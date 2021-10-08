"""
Analysis catalog run
------------------

Analysis catalog run status


"""

import json
import datetime
import dateutil
import time
import logging
from posixpath import join as urljoin
from typing import Callable, Union, Optional, Dict, List

from .exceptions import PhenotypeError
from ...exceptions import ServerError
from ...session import ServiceSession

log = logging.getLogger(__name__)


class AnalysisCatalogRun:
    """
    A local object representing an analysis catalog run response from the phenotype
    catalog service.

    Please refer to the API Documentation for the phenotype catalog service.

    In addition to the ones documented here, this object has at least these attributes:

    * name - Analysis Catalog Run name
    * state - the state of the Analysis Catalog Run
    * created_at - Timestamp when the analysis catalog run was first created
    * updated_at - Timestamp when the analysis catalog run was last updated
    * ended_at - Timestamp when the analysis catalog run ended (entered 'failed' or 'completed' state)

    """

    def __init__(self, session: ServiceSession, data: Dict):
        self.session = session
        self.data = data

    def __getattr__(self, name):
        try:
            val = self.data[name]
        except KeyError:
            raise AttributeError

        try:
            val = dateutil.parser.parse(val)
        except Exception:
            pass

        return val

    def __repr__(self) -> str:
        return f"<AnalysisCatalogRun {self.name} in project {self.project_key}>"

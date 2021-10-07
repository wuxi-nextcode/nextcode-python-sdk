"""
Analysis catalog
------------------

Analysis catalog is a collection of phenotypes and parameters that are needed to run
the workflow analysis


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


class AnalysisCatalog:
    """
    A local object representing an analysis catalog response from the phenotype
    catalog service.

    Please refer to the API Documentation for the phenotype catalog service.

    In addition to the ones documented here, this object has at least these attributes:

    * name - Analysis Catalog name
    * recipe_name - The name of the recipe to use
    * recipe_parameters - The parameters required to run the recipe
    * analysis_catalog_items - phenotypes/covariates used as input when generating preparation data
    * excluded_pns - the PNs to exclude from the analysis
    * created_at - Timestamp when the analysis catalog was first created
    * updated_at - Timestamp when the analysis catalog was last updated
    * created_by - Username who created the analysis catalog

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
        return f"<AnalysisCatalog {self.name} in project {self.project_key}>"

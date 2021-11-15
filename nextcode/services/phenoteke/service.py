"""
Service class
------------------
Service object for interfacing with the Phenoteke API

"""

import os
import logging
from posixpath import join as urljoin
from typing import Optional, List, Union, Dict

from ...client import Client
from ...services import BaseService

SERVICE_PATH = "phenoteke/api/v1"

log = logging.getLogger(__file__)

class Service(BaseService):
    """
    Phenoteke Service
    """

    links: Dict = {}

    def __init__(self, client: Client, *args, **kwargs) -> None:
        super(Service, self).__init__(client, SERVICE_PATH, *args, **kwargs)

    def map_cids_to_ipns(
            self,
            site_id: str,
            study_id: str,
            cids: List[str],
            subcategory_id: Optional[str] = None,
    ) -> List:
        """
        Get mapping from collaborator ids to ipns

        :param site_id: Site code
        :param study_id: Study code
        :param cids: List of collaborator ids
        :param subcategory_id: Optional sub category within study
        :return: List of {"cid": <cid>, "ipn": <ipn>}
        :raises: ServerError
        """
        uri = urljoin(
            self.session.url_from_endpoint("root"),
            "cids_to_ipns_mapping",
        )
        result = []
        parts = int((len(cids)+4)/5)

        payload = {
            "site_id": site_id,
            "study_id": study_id,
        }
        if subcategory_id:
            payload["subcategory_id"] = subcategory_id

        def list_split(l, parts):
            length = len(l)
            return [ l [i*length // parts: (i+1)*length // parts] for i in range(parts) ]

        for cid_parts in list_split(cids,parts):
            payload["cids"] = cid_parts

            resp = self.session.post(uri, json=payload)
            resp.raise_for_status()
            data = resp.json()
            result.extend(data["data"])

        return result


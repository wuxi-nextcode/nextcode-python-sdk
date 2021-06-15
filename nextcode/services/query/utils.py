"""
Utility methods
------------------

Utility methods used by the query service.
"""

import hashlib
from typing import Dict, Tuple, Sequence, List, Optional, Union, Any

from nextcode.services.query.exceptions import QueryError

DEFAULT_EXTENSION = ".tsv"


def get_fingerprint(contents: str) -> str:
    """
    Generate a fingerprint for the contents of a virtual relation.

    This fingerprint is used by the server for caching purposes.

    :param contents: The full contents of a tsv file
    :returns: md5 sum representing the file contents
    """
    md5 = hashlib.md5()
    md5.update(repr(contents).encode())
    return md5.hexdigest()


def extract_virtual_relations(kw, relations: Optional[List[Dict]] = None):
    """
    Extract virtual relations from input arguments
    :param kw:          optional keyword arguments
    :param relations:   optional relations
    :return:  relations ready for payload
    """
    _relations: List[Dict] = []
    if relations:
        _relations = relations
    else:
        for k, v in kw.items():
            _relations.append({"name": f"[{k}]", "data": v})

    payload_relations: List[Dict] = []
    for r in _relations:
        if "name" not in r or ("data" not in r and "fingerprint" not in r):
            raise QueryError("Virtual relations must have name and eiter data or fingerprint fields")

        name = r["name"]
        data = r["data"] if "data" in r else None

        if data is not None:
            if hasattr(data, "to_csv"):
                data = data.to_csv(index=False, sep="\t")

            if not isinstance(data, str):
                raise QueryError(f"Virtual relation data for {name} must be a string")

            if not data.startswith("#"):
                data = "#" + data

        fingerprint = r.get("fingerprint") or get_fingerprint(data)
        extension = r.get("extension") or DEFAULT_EXTENSION
        payload_relations.append(
            {
                "name": name,
                "fingerprint": fingerprint,
                "extension": extension,
                "data": data,
            }
        )
    return payload_relations

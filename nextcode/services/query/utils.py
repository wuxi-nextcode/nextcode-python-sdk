"""
Utility methods
------------------

Utility methods used by the query service.
"""

import hashlib


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

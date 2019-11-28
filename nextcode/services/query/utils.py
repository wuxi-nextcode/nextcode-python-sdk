"""
Utility methods
------------------

Utility methods used by the query service.
"""

from importlib.util import find_spec
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


def jupyter_available() -> bool:
    """
    Check if jupyter dependencies are available without importing these heavy libraries.
    """
    pandas_spec = find_spec("pandas")
    ipython_spec = find_spec("IPython")
    if pandas_spec is not None and ipython_spec is not None:
        return True
    return False

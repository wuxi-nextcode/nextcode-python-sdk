"""
exceptions
~~~~~~~~~~
Custom exceptions raised by the nextcode-sdk.

"""
from typing import Dict


class ServerError(Exception):
    """
    Raised when there was some sort of an error triggered by the server.
    """

    response: Dict = {}
    url: str = ""

    def __init__(self, message, response=None, url=None, **kw):
        self.response = response
        self.url = url
        self.message = message

    def __str__(self):
        ret = self.message
        if self.url:
            ret += " - {}".format(self.url)
        return ret


class InvalidToken(Exception):
    """
    JWT Token (API Key or access token) is invalid.
    """

    pass


class InvalidProfile(Exception):
    """
    The selected profile is invalid.
    """

    pass


class ServiceNotFound(Exception):
    """
    The requested service is not available on the server.
    """

    pass


class UploadError(Exception):
    """
    The requested server is not available on the server.
    """

    pass


class NotFound(Exception):
    """
    The requested resource was not found
    """

    pass


class AuthServerError(Exception):
    """
    An error with keycloak or CSA management
    """

    pass


class CSAError(Exception):
    """
    An error occurred when interfacing with CSA
    """

    pass

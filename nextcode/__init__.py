"""
nextcode
~~~~~~~~~~
nextcode is a python module for interfacing with RESTFul services provided by
Wuxi Nextcode.

"""
import os
import logging

from .config import Config
from .client import Client, get_service

log = logging.getLogger()

cfg = Config()


def read_version():
    directory = os.path.dirname(__file__)
    with open(os.path.join(directory, "VERSION"), "r") as version_file:
        version = version_file.readline().strip()
        return version


__version__ = read_version()

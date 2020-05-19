"""
nextcode
~~~~~~~~~~
nextcode is a python module for interfacing with RESTFul services provided by
Wuxi Nextcode.

"""
import os
import logging

from .config import Config

# we want these available from the top-level package
from .client import Client, get_service

log = logging.getLogger()

cfg = Config()


def read_version():
    directory = os.path.dirname(__file__)
    with open(os.path.join(directory, "VERSION"), "r") as version_file:
        version = version_file.readline().strip()
        return version


__version__ = read_version()

# loading this here allows easy extension setup in jupyterhub
from .services.query.jupyter import load_ipython_extension
from .services.query import jupyter


def bla():
    print("Blehssss")
    return "bluye"

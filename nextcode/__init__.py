"""
nextcode
~~~~~~~~~~
nextcode is a python module for interfacing with RESTFul services provided by
Wuxi Nextcode.

"""
import os
import logging
import importlib.metadata

from .config import Config
# we want these available from the top-level package
from .client import Client, get_service

log = logging.getLogger()

cfg = Config()


__version__ = importlib.metadata.version("nextcode-sdk")

# loading this here allows easy extension setup in jupyterhub
from .services.query.jupyter import load_ipython_extension
from .services.query import jupyter


def bla():
    print("Blehssss")
    return "bluye"

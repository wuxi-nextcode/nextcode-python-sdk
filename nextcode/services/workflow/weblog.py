"""
Weblog facilities
------------------

"""
import os
import requests
import datetime
import logging

log = logging.getLogger()


def add_to_details(key, **kw):
    """
    Add a dictionary to a list under 'key' for the job in WEBLOG_URL environment

    :param key: Name of the key to append to
    """
    weblog_url = os.environ.get("WEBLOG_URL")
    if not weblog_url:
        log.warning("No weblog url set. Cannot send message")
        return
    contents = {"event": "custom_details_add", "details": {"key": key, "value": kw}}
    resp = requests.post(weblog_url, json=contents)
    resp.raise_for_status()


def set_details(key, val):
    """
    Set a key under details to a value for the job in WEBLOG_URL environment

    :param key: name of the key in details
    :param val: value to put
    """
    weblog_url = os.environ.get("WEBLOG_URL")
    if not weblog_url:
        log.warning("No weblog url set. Cannot send message")
        return
    contents = {"event": "custom_details_set", "details": {"key": key, "value": val}}
    resp = requests.post(weblog_url, json=contents)
    resp.raise_for_status()


def set_status_message(msg):
    """
    Sets the status message for the job in WEBLOG_URL environment

    :param msg: status message
    """
    weblog_url = os.environ.get("WEBLOG_URL")
    if not weblog_url:
        log.warning("No weblog url set. Cannot send message")
        return
    contents = {"event": "custom_status_message", "details": {"message": msg}}
    resp = requests.post(weblog_url, json=contents)
    resp.raise_for_status()

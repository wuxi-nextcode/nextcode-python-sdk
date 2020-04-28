"""
Project
------------------

The Project class represents a project model from the RESTFul Project Service API

"""

import json
import datetime
import dateutil
import time
import logging
import os
from typing import Callable, Union, Optional, Dict, List

import boto3
from botocore.client import Config as BotoConfig

from .exceptions import ProjectError
from ...exceptions import ServerError
from ...session import ServiceSession

log = logging.getLogger(__name__)


class Project:
    """
    Proxy object for a serverside project.
    """

    def __init__(self, service, project: dict):
        self.service = service
        self.session = service.session
        self.project = project
        self.project_name = project["project_name"]

    def __repr__(self) -> str:
        return f"<Project {self.project_name})>"

    def __getattr__(self, name):
        try:
            val = self.project[name]
        except KeyError:
            raise AttributeError

        return val

    def get_users(self):
        # TODO: admin
        users_link = self.links["users"]
        users = self.session.get(users_link)
        return users.json()

    def add_user(self, user_name, policies):
        # TODO: admin
        users_link = self.links["users"]
        data = {"user_name": user_name, "policies": policies}
        try:
            users = self.session.post(users_link, json=data)
        except ServerError as se:
            raise ProjectError(str(se)) from None
        return users.json()

    def remove_user(self, user_name):
        # TODO: admin
        pass

    def delete_project(self):
        # TODO: admin
        pass

    def get_bucket(self):
        credentials = self.service.get_credentials()
        s3 = boto3.resource(
            "s3",
            endpoint_url="https://platform-projects.wuxinextcodedev.com",
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            config=BotoConfig(signature_version="s3v4"),
        )
        bucket = s3.Bucket(self.project_name)  # pylint: disable=E1101
        return bucket

    def list(self, prefix=""):
        bucket = self.get_bucket()
        result = bucket.meta.client.list_objects(
            Bucket=bucket.name, Delimiter="/", Prefix=prefix
        )
        ret = {"folders": [], "files": []}
        if "CommonPrefixes" in result:
            for o in result["CommonPrefixes"]:
                ret["folders"].append(o["Prefix"])
        if "Contents" in result:
            for o in result["Contents"]:
                ret["files"].append(o["Key"])
        return ret

    def download(self, key, path):
        """
        """
        bucket = self.get_bucket()
        path = os.path.expanduser(path)
        if path.endswith("/") or os.path.isdir(path):
            filename = key.split("/")[-1]
            path = os.path.join(path, filename)
        log.info(f"Downloading {key} from project {self.project_name} to {path}")
        bucket.download_file(key, path)

    def upload(self, filename, key):
        bucket = self.get_bucket()
        path = os.path.expanduser(filename)
        if key.endswith("/"):
            key += os.path.basename(filename)
        log.info(f"Uploading {path} to {key} in project {self.project_name}")
        try:
            bucket.upload_file(path, key)
        except Exception as e:
            raise e from None

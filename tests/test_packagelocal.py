from unittest import TestCase
from unittest.mock import patch, MagicMock

from nextcode import config, Client
from nextcode.packagelocal import package_and_upload
from nextcode.exceptions import UploadError
from tests import BaseTestCase

import logging

logging.basicConfig(level=logging.DEBUG)

cfg = config.Config()


class PackageLocalTest(BaseTestCase):
    def test_no_scratch_bucket(self):
        svc = MagicMock()
        name = "name"
        folder = "/tmp/test"
        svc.app_info = {"scratch_bucket": None}
        with self.assertRaises(UploadError) as ctx:
            package_and_upload(svc, name, folder)
        self.assertIn(
            "Cannot upload local package because the service has no scratch bucket",
            repr(ctx.exception),
        )

    def test_no_files(self):
        svc = MagicMock()
        name = "name"
        folder = "/tmp/test"
        svc.app_info = {"scratch_bucket": "testbucket"}
        with self.assertRaises(UploadError) as ctx:
            with patch("os.walk", return_value=[]):
                package_and_upload(svc, name, folder)
        self.assertIn("Failed to upload local package", repr(ctx.exception))

    def test_access_denied(self):
        svc = MagicMock()
        name = "name"
        folder = "/tmp/test"
        svc.app_info = {"scratch_bucket": "testbucket"}
        with patch(
            "nextcode.packagelocal._package_and_upload",
            side_effect=Exception("AccessDenied"),
        ):
            with self.assertRaises(UploadError) as ctx:
                package_and_upload(svc, name, folder)
            self.assertIn("Failed to upload local package", repr(ctx.exception))

    def test_package_and_upload(self):
        svc = MagicMock()
        name = "name"
        folder = "/tmp/test"
        svc.app_info = {"scratch_bucket": "testbucket"}
        with patch("os.walk") as mockwalk, patch(
            "nextcode.packagelocal.ZipFile"
        ), patch("nextcode.packagelocal.boto3"), patch("nextcode.packagelocal.sleep"):
            mockwalk.return_value = [
                ("/.foo", ("bar",), ("baz",)),
                ("/foo", ("bar",), ("baz",)),
                ("/foo/bar", (), ("spam", "eggs")),
                ("/foo/barz", (), (".spam", "eggs")),
            ]
            package_and_upload(svc, name, folder)

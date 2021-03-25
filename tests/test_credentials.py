import os
from collections import OrderedDict
from pathlib import Path
from typing import NamedTuple
from unittest.mock import patch, MagicMock

from nextcode.credentials import (
    generate_credential_struct,
    creds_to_dict,
    find_aws_credentials,
)
from tests import BaseTestCase

aws_credentials_path = os.path.join(os.path.dirname(__file__), "data/aws_credentials")


def mock_os_path_join(*args):
    return aws_credentials_path


class CredentialsTest(BaseTestCase):
    local_profile_name = "local_profile_something"
    remote_profile_name = "remote_profile_other"

    access_key = "totes-legis-aws-access-key-id"
    secret_key = "secret-key-is-secret"
    region = "great-region"
    token = "very-long-token-yes-please"

    def _get_cred_dict(self):
        return creds_to_dict([f"{self.remote_profile_name}={self.local_profile_name}"])

    def _get_credentials_mock(self):
        credentials_mock = MagicMock()
        credentials_mock.access_key = self.access_key
        credentials_mock.secret_key = self.secret_key
        credentials_mock.region = self.region
        credentials_mock.token = self.token
        return credentials_mock

    def test_creds_to_dict(self):
        cred_dict = self._get_cred_dict()
        cred_dict.keys()
        self.assertIn(
            self.remote_profile_name,
            cred_dict.keys(),
            "Cred dict should be keyed by local profile",
        )
        self.assertEqual(
            cred_dict[self.remote_profile_name],
            self.local_profile_name,
            "cred_dict entry for local profile should contain remote_profile",
        )

    @patch("botocore.session")
    def test_credentials_not_found(self, mocked_boto):
        mocked_session = mocked_boto.get_session()
        mocked_session.get_credentials.return_value = None
        with patch("os.path.join", mock_os_path_join):
            with self.assertRaises(RuntimeError):
                find_aws_credentials("bad profile no biscuit")

    @patch("botocore.session")
    def test_find_aws_credentials(self, mocked_boto):
        mocked_session = mocked_boto.get_session()
        credentials_mock = self._get_credentials_mock()
        mocked_session.get_credentials.return_value = credentials_mock

        with patch("os.path.join", mock_os_path_join):
            test_creds = find_aws_credentials(self.local_profile_name)
        self.assertEqual(test_creds.get("aws_access_key_id"), self.access_key)
        self.assertEqual(test_creds.get("aws_secret_access_key"), self.secret_key)
        self.assertEqual(test_creds.get("aws_session_token"), self.token)
        self.assertEqual(test_creds.get("region"), self.region)

    @patch("botocore.session")
    def test_find_all_aws_credentials(self, mocked_boto):
        mocked_session = mocked_boto.get_session()
        credentials_mock = self._get_credentials_mock()
        mocked_session.get_credentials.return_value = credentials_mock
        test_creds = find_aws_credentials("")
        self.assertEqual(test_creds.get("aws_access_key_id"), self.access_key)
        self.assertEqual(test_creds.get("aws_secret_access_key"), self.secret_key)
        self.assertEqual(test_creds.get("aws_session_token"), self.token)
        self.assertEqual(test_creds.get("region"), self.region)

    def test_generate_credentials(self):
        credentials_mock = MagicMock()
        credentials_mock.return_value = {
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "region": self.region,
            "aws_session_token": self.token,
        }
        with (patch("nextcode.credentials.find_aws_credentials", credentials_mock)):
            test_creds = generate_credential_struct(self._get_cred_dict())
            self.assertIn(self.remote_profile_name, test_creds)
            self.assertEqual(
                test_creds[self.remote_profile_name].get("aws_access_key_id"),
                self.access_key,
            )
            self.assertEqual(
                test_creds[self.remote_profile_name].get("aws_secret_access_key"),
                self.secret_key,
            )
            self.assertEqual(
                test_creds[self.remote_profile_name].get("region"), self.region
            )

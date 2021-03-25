import os
import botocore.session
import configparser
from collections import OrderedDict


def find_aws_credentials(profile):
    """
    Returns the aws credentials for the specified profile.
    If no profile is passed in, returns the credentials for the currently selected profile

    Args:
        profile name

    Returns:
        Dict containing at least aws_access_key_id, aws_secret_access_key

    Raises:
        RuntimeError is no default profile or the named profile was not found

    """
    if not profile:
        access_key = None
        secret_key = None
        region = None
        token = ""
        credentials = botocore.session.get_session().get_credentials()
        if credentials:
            access_key = credentials.access_key
            secret_key = credentials.secret_key
            region = credentials.region
            token = getattr(credentials, "token") or ""
        if not access_key or not secret_key:
            raise RuntimeError("No Default AWS profile set")

        ret = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "aws_session_token": token,
        }
        # only add the region if it is defined
        if region:
            ret["region"] = region

        return ret
    else:

        folder = os.path.join(os.path.expanduser("~"), ".aws")
        filename = os.path.join(folder, "credentials")
        cfg = configparser.ConfigParser()
        with open(filename) as fp:
            cfg.read_file(fp)
            ret = {}
            if profile not in cfg:
                raise RuntimeError(
                    "No AWS profile '%s' found in %s" % (profile, filename)
                )
            for key in cfg[profile]:
                ret[key] = cfg[profile][key]
        return ret


def creds_to_dict(credentials: list) -> OrderedDict:
    """
    :param credentials: list of the form ['upload=joe', 'remote_profile=local_profile']
    :return OrderedDict of the form {'upload': 'joe', 'remote_profile': 'local_profile'}
    """
    ret = OrderedDict()
    # credentials are supplied on the form 'upload=joe'
    # 'joe' being the local profile in ~/.aws/credentials
    # and 'upload' being the name we give the credentials
    # when forwarding to the workflow-service
    for cred in credentials:
        key, value = cred.split("=")
        ret[key] = value
    return ret


def generate_credential_struct(credential_map: OrderedDict) -> dict:
    """

    :param credential_map: An OrderedDict of profile maps of the form local-profile-name=remote-profile-name
    :type credential_map: OrderedDict
    :return: Returns an empty dict if credential_map is Falsy, otherwise returns  AWS Credentials as a dict, keyed to profile_name.
    :rtype: dict
    """
    cred_struct = {}
    if not credential_map:
        return cred_struct

    for upload_name, local_name in credential_map.items():
        cred = find_aws_credentials(local_name)
        cred_struct[upload_name] = {}
        cred_struct[upload_name]["aws_access_key_id"] = cred["aws_access_key_id"]
        cred_struct[upload_name]["aws_secret_access_key"] = cred[
            "aws_secret_access_key"
        ]
        if "region" in cred:
            cred_struct[upload_name]["region"] = cred["region"]
    return cred_struct

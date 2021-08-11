"""
packagelocal
~~~~~~~~~~~~

Package a local folder and upload to S3 for workflow service and pipelines service.
"""

import os
from time import sleep
import boto3
import socket
from zipfile import ZipFile
import tempfile
import logging
from .exceptions import UploadError
from typing import Dict, Tuple, Sequence, List, Optional, Union, Callable
from .services import BaseService

log = logging.getLogger(__name__)

# !TODO: Temporary until services expose correctly
DEFAULT_SCRATCH_BUCKET = "nextcode-scratch"
EXPIRATION_SECONDS = 7 * 24 * 60 * 60  # expires in 7 days


def package_and_upload(
    service: BaseService, package_name: str, project_path: str
) -> str:
    """
    Create a zip file from a folder and upload to S3. Returns a presigned https URL with an expiration of 24 hours

    :param service: service instance of a workflow service or a pipelines service which supports package uploads
    :param package_name: name of the package, will be used as a partial filename
    :param project_path: local folder to package and upload
    :returns: https url to the zip file on S3
    :raises: UploadError

    """
    log.debug(
        "package_and_upload called with package_name=%s, project_path=%s",
        package_name,
        project_path,
    )
    scratch_bucket = service.app_info.get("scratch_bucket", DEFAULT_SCRATCH_BUCKET)  # type: ignore

    if not scratch_bucket:
        raise UploadError(
            "Cannot upload local package because the service has no scratch bucket"
        )

    log.info(
        "Uploading local package %s from %s to s3://%s...",
        package_name,
        project_path,
        scratch_bucket,
    )

    try:
        return _package_and_upload(scratch_bucket, package_name, project_path)
    except Exception as e:
        if "AccessDenied" in repr(
            e
        ) or "The AWS Access Key Id you provided does not exist in our records" in repr(
            e
        ):
            raise UploadError(
                "Failed to upload local package. You do not have access to s3 bucket '%s'."
                % scratch_bucket
            )
        else:
            raise UploadError(f"Failed to upload local package ({repr(e)})")


def _package_and_upload(
    scratch_bucket: str, package_name: str, project_path: str
) -> str:
    """
    Zip up all relevant files from 'project_path' and upload to s3 so that we
    can download it from the ec2 worker node for local deployment.
    """
    log.info("Packaging '%s'", project_path)
    zip_filename = "{}_{}.zip".format(package_name, socket.gethostname())
    full_zip_filename = tempfile.mkstemp(".zip")[1]
    project_path = os.path.abspath(project_path)
    log.debug("project_path is %s", project_path)
    log_archive = ZipFile(full_zip_filename, "w")

    files = []
    for root, directories, filenames in os.walk(
        project_path, followlinks=False, topdown=True
    ):
        # skip everything starting with a .
        if any([l.startswith(".") for l in root.split("/")]):
            continue

        for filename in filenames:
            if not filename.startswith("."):
                full_filename = os.path.join(root, filename)
                # ignore symlinks
                if not os.path.islink(full_filename):
                    files.append(full_filename)

    for f in files:
        write_filename = f.replace(project_path, "")
        write_filename = package_name + write_filename
        log_archive.write(f, arcname=write_filename)
    log_archive.close()

    if len(files) == 0:
        raise RuntimeError("No files found in '%s'" % project_path)
    s3_resource = boto3.resource("s3")
    b = s3_resource.Bucket(scratch_bucket)  # pylint: disable=no-member
    s3_path = "builds/" + zip_filename
    b.upload_file(full_zip_filename, s3_path)

    log.info("Uploaded %s to %s (%s files)", zip_filename, s3_path, len(files))
    s3_client = boto3.client("s3")
    url = s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": scratch_bucket, "Key": s3_path},
        ExpiresIn=EXPIRATION_SECONDS,
    )
    # wait for a few seconds to give s3 time to catch up
    sleep(2.0)
    return url

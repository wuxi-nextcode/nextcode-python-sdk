import os
import time
import boto3
import socket
import zipfile
import tempfile
import logging
from .exceptions import UploadError

log = logging.getLogger(__name__)

# !TODO: Temporary until services expose correctly
DEFAULT_SCRATCH_BUCKET = "nextcode-scratch"
EXPIRATION_SECONDS = 7 * 24 * 60 * 60  # expires in 7 days


def _get_path(project_name):
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../", project_name)
    )
    if not os.path.exists(path):
        raise RuntimeError("Path %s does not exist" % path)
    return path


def package_and_upload(service, project_name, project_path):
    log.debug(
        "package_and_upload called with project_name=%s, project_path=%s",
        project_name,
        project_path,
    )
    scratch_bucket = service.app_info.get("scratch_bucket", DEFAULT_SCRATCH_BUCKET)

    if not scratch_bucket:
        raise UploadError(
            "Cannot upload local package because the service has no scratch bucket"
        )

    log.info(
        "Uploading local package {} from {} to s3://{}...".format(
            project_name, project_path, scratch_bucket
        )
    )

    try:
        return _package_and_upload(scratch_bucket, project_name, project_path)
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
            raise UploadError("Failed to upload local package.")


def _package_and_upload(scratch_bucket, project_name, project_path):
    """Zip up all relevant files from 'project_path' and upload to s3 so that we
    can download it from the ec2 worker node for local deployment.
    """
    log.info("Packaging '%s'", project_path)
    zip_filename = "{}_{}.zip".format(project_name, socket.gethostname())
    full_zip_filename = tempfile.mkstemp(".zip")[1]
    project_path = os.path.abspath(project_path)
    log.debug("project_path is %s", project_path)
    log_archive = zipfile.ZipFile(full_zip_filename, "w")

    files = []
    for root, directories, filenames in os.walk(
        project_path, followlinks=False, topdown=True
    ):
        # skip everything starting with a . and the nextflow 'work' folder
        if any([l.startswith(".") for l in root.split("/")]):
            continue

        for filename in filenames:
            if not filename.startswith("."):
                full_filename = os.path.join(root, filename)
                files.append(full_filename)

    for f in files:
        write_filename = f.replace(project_path, "")
        write_filename = project_name + write_filename
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
    time.sleep(2.0)
    return url

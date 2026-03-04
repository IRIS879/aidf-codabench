# src/utils/data.py

import os
import uuid
from datetime import timedelta

import requests
import boto3
from botocore.config import Config
from azure.storage.blob import BlobSasPermissions
from django.conf import settings
from django.utils.deconstruct import deconstructible
from django.utils.timezone import now

from utils.storage import BundleStorage

import logging
logger = logging.getLogger(__name__)


@deconstructible
class PathWrapper(object):
    """Helper to generate UUID's in file names while maintaining their extension"""

    def __init__(self, base_directory, manual_override=False):
        self.path = base_directory
        self.manual_override = manual_override

    def __call__(self, instance, filename):
        if not self.manual_override:
            name, extension = os.path.splitext(filename)
            truncated_uuid = uuid.uuid4().hex[0:12]
            truncated_name = name[0:35]

            path = os.path.join(
                self.path,
                now().strftime('%Y-%m-%d-%s'),
                truncated_uuid,
                "{0}{1}".format(truncated_name, extension),
            )
        else:
            path = os.path.join(filename)

        return path


def _get_sigv4_s3_client():
    """
    Create an S3 client that ALWAYS uses SigV4 for presigning.
    This fixes MinIO setups that reject SigV2 presigned URLs.
    """
    endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None) or None
    region_name = getattr(settings, "AWS_S3_REGION_NAME", None) or "us-east-1"

    # Use the same creds you already set for MinIO/AWS
    access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region_name,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},  # safer for MinIO + localhost:9000
        ),
    )


def make_url_sassy(path, permission="r", duration=60 * 60 * 24 * 5, content_type="application/zip"):
    """
    Generate a signed URL (read or write) for the configured storage backend.

    - S3/MinIO: presigned URL using SigV4 (required for many MinIO configs)
    - GCS: signed URL via blob.generate_signed_url
    - Azure: SAS URL

    NOTE (important):
    - For MinIO + browser uploads, signing ContentType can break PUT due to mismatched Content-Type.
      So we do NOT sign ContentType when AWS_S3_ENDPOINT_URL is set (custom endpoint).
    """
    assert permission in ("r", "w"), "SASSY urls only support read and write ('r' or 'w' permission)"

    if settings.STORAGE_IS_S3:
        # Remove the beginning of the URL (before bucket name) so we just have the path to the file
        path = path.split(settings.AWS_STORAGE_PRIVATE_BUCKET_NAME)[-1]

        # remove prepended slash
        if path.startswith("/"):
            path = path[1:]

        # Spaces replaced with +'s, so we have to replace those...
        path = path.replace("+", " ")

        params = {
            "Bucket": settings.AWS_STORAGE_PRIVATE_BUCKET_NAME,
            "Key": path,
        }

        # AWS uses method instead of permission
        if permission == "r":
            client_method = "get_object"
        else:
            client_method = "put_object"

        # If using a custom endpoint (MinIO), do NOT sign ContentType (common cause of 403)
        is_custom_endpoint = bool(getattr(settings, "AWS_S3_ENDPOINT_URL", ""))
        if content_type and not is_custom_endpoint:
            params["ContentType"] = content_type

        # Force SigV4 for presigning (fixes MinIO rejecting SigV2 URLs)
        s3 = _get_sigv4_s3_client()

        return s3.generate_presigned_url(
            client_method,
            Params=params,
            ExpiresIn=duration,
        )

    elif settings.STORAGE_IS_GCS:
        if permission == "r":
            client_method = "GET"
        else:
            client_method = "PUT"

        bucket = BundleStorage.client.get_bucket(settings.GS_PRIVATE_BUCKET_NAME)
        return bucket.blob(path).generate_signed_url(
            expiration=now() + timedelta(seconds=duration),
            method=client_method,
            content_type=content_type,
        )

    elif settings.STORAGE_IS_AZURE:
        if permission == "r":
            client_method = BlobSasPermissions(read=True)
        else:
            client_method = BlobSasPermissions(read=True, write=True)

        sas_token = BundleStorage.service.generate_blob_shared_access_signature(
            BundleStorage.azure_container,
            path,
            client_method,
            expiry=now() + timedelta(seconds=duration),
        )

        return BundleStorage.service.make_blob_url(
            container_name=BundleStorage.azure_container,
            blob_name=path,
            sas_token=sas_token,
        )

    raise RuntimeError("No supported storage backend configured (S3/GCS/AZURE).")


def put_blob(url, file_path):
    return requests.put(
        url,
        data=open(file_path, "rb"),
        headers={
            # Only for Azure but AWS ignores this fine
            "x-ms-blob-type": "BlockBlob",
        },
    )


def pretty_bytes(bytes, decimal_places=1, suffix="B", binary=False, return_0_for_invalid=False):
    # Ensure bytes is a valid number
    try:
        bytes = float(bytes)
    except (ValueError, TypeError):
        return 0 if return_0_for_invalid else ""  # Return 0 or empty string for invalid inputs

    if bytes < 0:
        return 0 if return_0_for_invalid else ""  # Return 0 or empty string for invalid inputs

    factor = 1024.0 if binary else 1000.0
    units = ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"] if binary else ["", "k", "M", "G", "T", "P", "E", "Z"]

    for unit in units:
        if abs(bytes) < factor:
            return f"{bytes:.{decimal_places}f} {unit}{suffix}"
        bytes /= factor

    return f"{bytes:.{decimal_places}f} {units[-1]}{suffix}"


def gb_to_bytes(gb, binary=False):
    factor = 1024**3 if binary else 1000**3
    return gb * factor
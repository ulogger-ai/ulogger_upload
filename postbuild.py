#!/usr/bin/env python3
"""
Client script for uploading AXF firmware files to uLogger Cloud.

This script provides a client for uploading AXF firmware files to the uLogger platform.
It uses MQTT to request presigned S3 URLs and then uploads files directly to S3.

Usage:
    python postbuild.py --version 1.0.0 --git_hash abc123 --branch main --file firmware.axf

Environment Variables:
    ULOGGER_CUSTOMER_ID: Customer identifier
    ULOGGER_APPLICATION_ID: Application identifier  
    ULOGGER_DEVICE_TYPE: Device type
    ULOGGER_CERT_DATA: Certificate data in PEM format
    ULOGGER_KEY_DATA: Private key data in PEM format
"""

import json
import os
import sys
import logging
import random
import tempfile
from pathlib import Path
from typing import Optional

import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://upload-api.ulogger.ai"


class AxfUploadClient:
    """Client for uploading AXF files via the Upload API (mTLS)."""

    def __init__(self, customer_id: str, device_type: str,
                 cert_file: str = "certificate.pem.crt",
                 key_file: str = "private.pem.key",
                 api_url: str = DEFAULT_API_URL,
                 timeout: int = 30):
        self.customer_id = customer_id
        self.device_type = device_type
        self.cert_file = cert_file
        self.key_file = key_file
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self._temp_cert_file: Optional[str] = None
        self._temp_key_file: Optional[str] = None

        if not os.path.exists(self.cert_file):
            raise FileNotFoundError(f"Certificate file not found: {self.cert_file}")
        if not os.path.exists(self.key_file):
            raise FileNotFoundError(f"Key file not found: {self.key_file}")

    def _request_presigned_url(self, git_hash: str, version_number: str,
                               application_id: int, branch: Optional[str] = None) -> dict:
        """POST to the Upload API to get a presigned S3 URL."""
        payload = {
            "customer_id": self.customer_id,
            "application_id": application_id,
            "device_type": self.device_type,
            "git_hash": git_hash,
            "version_number": version_number,
        }
        if branch:
            payload["branch"] = branch

        url = f"{self.api_url}/upload"
        logger.info(f"Requesting presigned URL from {url}")

        response = requests.post(
            url,
            json=payload,
            cert=(self.cert_file, self.key_file),
            timeout=self.timeout,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Upload API returned {response.status_code}: {response.text}"
            )

        data = response.json()
        if "presigned_url" not in data:
            raise RuntimeError(f"Response missing presigned_url: {data}")

        logger.info(f"Received presigned URL for s3_key={data.get('s3_key')}")
        return data

    @staticmethod
    def _upload_file_to_s3(file_path: str, presigned_url: str) -> bool:
        """Upload a file to S3 using a presigned PUT URL."""
        logger.info(f"Uploading {file_path} to S3")
        file_size = os.path.getsize(file_path)
        with open(file_path, 'rb') as f:
            response = requests.put(
                presigned_url,
                data=f,
                headers={
                    'Content-Type': 'application/octet-stream',
                    'Content-Length': str(file_size),
                },
                timeout=300,
            )

        if response.status_code == 200:
            logger.info("File uploaded successfully to S3")
            return True
        else:
            logger.error(f"S3 upload failed: {response.status_code} - {response.text}")
            return False

    def upload_axf_file(self, file_path: str, git_hash: str,
                        version_number: str, branch: Optional[str] = None,
                        **_kwargs) -> bool:
        """
        Complete workflow: request presigned URL then upload file.

        Returns True on success.
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False

        application_id = getattr(self, 'application_id', None)
        if application_id is None:
            logger.error("application_id not set on client")
            return False

        try:
            data = self._request_presigned_url(
                git_hash=git_hash,
                version_number=version_number,
                application_id=application_id,
                branch=branch,
            )
            return self._upload_file_to_s3(file_path, data['presigned_url'])
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False

    def cleanup(self):
        """Remove temporary certificate files if created."""
        for path in (self._temp_cert_file, self._temp_key_file):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def main():
    """CLI entry point for uploading AXF files."""
    import argparse

    parser = argparse.ArgumentParser(description="AXF Upload Client")
    parser.add_argument('--customer_id', type=int, default=None,
                        help='Customer identifier (or set ULOGGER_CUSTOMER_ID env var)')
    parser.add_argument('--application_id', type=int, default=None,
                        help='Application identifier (or set ULOGGER_APPLICATION_ID env var)')
    parser.add_argument('--device_type', type=str, default=None,
                        help='Device type (or set ULOGGER_DEVICE_TYPE env var)')
    parser.add_argument('--version', type=str, required=True,
                        help='Software version number')
    parser.add_argument('--git_hash', type=str, required=True,
                        help='Git hash for the firmware')
    parser.add_argument('--branch', type=str, required=True,
                        help='Branch name to include in upload request')
    parser.add_argument('--cert_path', type=str, default='certificate.pem.crt',
                        help='Path to certificate file')
    parser.add_argument('--key_path', type=str, default='private.pem.key',
                        help='Path to private key file')
    parser.add_argument('--file', type=str, required=True,
                        help='AXF file to upload')
    parser.add_argument('--api_url', type=str, default=DEFAULT_API_URL,
                        help=f'Upload API base URL (default: {DEFAULT_API_URL})')
    parser.add_argument('--timeout', type=int, default=60,
                        help='Request timeout in seconds (default: 60)')

    args = parser.parse_args()

    # Resolve from env vars if not provided
    customer_id = args.customer_id or os.environ.get('ULOGGER_CUSTOMER_ID')
    application_id = args.application_id or os.environ.get('ULOGGER_APPLICATION_ID')
    device_type = args.device_type or os.environ.get('ULOGGER_DEVICE_TYPE')

    for name, val in [('customer_id', customer_id), ('application_id', application_id), ('device_type', device_type)]:
        if val is None:
            logger.error(f"{name} not provided and ULOGGER_{name.upper()} env var not set.")
            sys.exit(1)

    customer_id = int(customer_id)
    application_id = int(application_id)

    # Support cert/key data from env vars (e.g. in CI)
    cert_data = os.environ.get('ULOGGER_CERT_DATA', '')
    key_data = os.environ.get('ULOGGER_KEY_DATA', '')
    cert_path = args.cert_path
    key_path = args.key_path
    temp_cert_file = None
    temp_key_file = None

    try:
        if cert_data:
            fd, temp_cert_file = tempfile.mkstemp(suffix='.crt', text=True)
            with os.fdopen(fd, 'w') as f:
                f.write(cert_data)
            cert_path = temp_cert_file
            logger.info("Using certificate data from ULOGGER_CERT_DATA env var")

        if key_data:
            fd, temp_key_file = tempfile.mkstemp(suffix='.key', text=True)
            with os.fdopen(fd, 'w') as f:
                f.write(key_data)
            key_path = temp_key_file
            logger.info("Using key data from ULOGGER_KEY_DATA env var")

        client = AxfUploadClient(
            customer_id=customer_id,
            device_type=device_type,
            cert_file=cert_path,
            key_file=key_path,
            api_url=args.api_url,
            timeout=args.timeout,
        )
        client.application_id = application_id
        client._temp_cert_file = temp_cert_file
        client._temp_key_file = temp_key_file

        success = client.upload_axf_file(
            file_path=args.file,
            git_hash=args.git_hash,
            version_number=args.version,
            branch=args.branch,
        )

        if success:
            logger.info("Upload completed successfully!")
        else:
            logger.error("Upload failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        for path in (temp_cert_file, temp_key_file):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
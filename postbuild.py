#!/usr/bin/env python3
"""
uLogger AXF Upload Client

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
import time
import requests
import random
import paho.mqtt.client as mqtt
import threading
from typing import Optional, Dict, Any
import logging
import os
import ssl
from pathlib import Path
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AxfUploadClient:
    """Client for uploading AXF files using MQTT-triggered workflow."""
    
    def __init__(self, customer_id: str, device_type: str, broker: str = "mqtt.ulogger.ai", port: int = 8883,
                 cert_file: str = "certificate.pem.crt", key_file: str = "private.pem.key"):
        """
        Initialize the upload client.
        
        Args:
            customer_id: Customer identifier for MQTT topic
            broker: MQTT broker hostname
            port: MQTT broker port
            cert_file: Path to certificate file
            key_file: Path to private key file
        """
        self.customer_id = customer_id
        self.device_type = device_type
        self.broker = broker
        self.port = port
        self.cert_file = cert_file
        self.key_file = key_file
        self.mqtt_client = None
        self.received_response = threading.Event()
        self.upload_response = None
        self._temp_cert_file = None
        self._temp_key_file = None
        self.current_upload_id = None
        
        # Validate certificate files exist
        if not os.path.exists(self.cert_file) or not os.path.exists(self.key_file):
            raise FileNotFoundError(f"Certificate or key file not found. Please provide valid paths: {self.cert_file}, {self.key_file}")
        
    def setup_mqtt_client(self):
        """Set up MQTT client with certificate-based authentication."""
        try:
            # Create MQTT client
            self.mqtt_client = mqtt.Client(client_id=f"cust-{self.customer_id}-uploader-{random.randint(0, 4294967295)}")
            
            # Set up SSL/TLS with certificates for ulogger broker
            self.mqtt_client.tls_set(
                ca_certs=None,  # Set to CA file if required by broker
                certfile=self.cert_file,
                keyfile=self.key_file,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_message = self._on_message
            self.mqtt_client.on_disconnect = self._on_disconnect
            
            # Connect to ulogger MQTT broker
            logger.info(f"Connecting to MQTT broker: {self.broker}:{self.port}")
            self.mqtt_client.connect(self.broker, self.port, 60)
            
            # Start the MQTT loop in a separate thread
            self.mqtt_client.loop_start()
            
        except Exception as e:
            logger.error(f"Failed to setup MQTT client: {e}")
            raise
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when MQTT client connects."""
        if rc == 0:
            logger.info("Connected to MQTT broker")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            logger.info(f"Received message on topic {topic}: {payload}")
            
            # Store the response and signal that we received it
            self.upload_response = payload
            self.received_response.set()
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when MQTT client disconnects."""
        logger.info(f"Disconnected from MQTT broker, return code {rc}")
    
    def publish_upload_request(self, upload_request: Dict[str, Any]) -> bool:
        """
        Publish upload request to MQTT topic (which triggers the Lambda function).
        
        Args:
            upload_request: Request payload to publish
            device_type: Type of device
        Returns:
            True if message was published successfully
        """
        try:
            # Publish to the request topic that triggers the Lambda
            request_topic = f"upload/v0/firmware/{self.customer_id}/{self.device_type}"
            message = json.dumps(upload_request)
            
            logger.info(f"Publishing upload request to topic: {request_topic}")
            result = self.mqtt_client.publish(request_topic, message, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info("Upload request published successfully")
                return True
            else:
                logger.error(f"Failed to publish upload request: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing upload request: {e}")
            return False
    
    def upload_file_to_s3(self, file_path: str, presigned_url: str) -> bool:
        """
        Upload file to S3 using presigned URL.
        
        Args:
            file_path: Path to the file to upload
            presigned_url: Presigned URL for upload
            
        Returns:
            True if upload was successful
        """
        try:
            logger.info(f"Uploading file {file_path} to S3")
            
            # Read the file
            with open(file_path, 'rb') as file:
                file_data = file.read()
            
            # Upload using the presigned URL
            response = requests.put(
                presigned_url,
                data=file_data,
                headers={'Content-Type': 'application/octet-stream'}
            )
            
            if response.status_code == 200:
                logger.info("File uploaded successfully to S3")
                return True
            else:
                logger.error(f"Failed to upload file: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return False
    
    def upload_axf_file(self, file_path: str, git_hash: str,
                       version_number: str, upload_id: Optional[int] = None, timeout: int = 30, branch: Optional[str] = None) -> bool:
        """
        Complete workflow to upload an AXF file.
        
        Args:
            file_path: Path to the AXF file to upload
            device_type: Type of device
            git_hash: Git hash for the firmware
            version_number: Version number
            upload_id: Optional upload ID (will be generated if not provided)
            timeout: Timeout in seconds to wait for MQTT response
            
        Returns:
            True if the complete workflow was successful
        """
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return False

            # Generate upload ID if not provided
            if upload_id is None:
                upload_id = int(time.time() * 1000)  # Use timestamp as upload ID

            # Prepare request payload
            upload_request = {
                "upload_id": upload_id,
                "device_type": self.device_type,
                "git_hash": git_hash,
                "version_number": version_number,
                "customer_id": self.customer_id,
                "application_id": getattr(self, 'application_id', None),
                "branch": branch
            }
            
            # Reset the response event
            self.received_response.clear()
            self.upload_response = None
            self.current_upload_id = upload_id
            
            # Setup MQTT client if not already done
            if self.mqtt_client is None:
                self.setup_mqtt_client()
                time.sleep(2)  # Give MQTT client time to connect
            
            # Subscribe to the upload response topic with upload_id
            response_topic = f"upload/v0/{self.customer_id}/{upload_id}"
            self.mqtt_client.subscribe(response_topic)
            logger.info(f"Subscribed to response topic: {response_topic}")
            
            # Publish upload request to MQTT (triggers Lambda function)
            if not self.publish_upload_request(upload_request):
                return False
            
            # Wait for MQTT response
            logger.info(f"Waiting for MQTT response (timeout: {timeout}s)")
            if not self.received_response.wait(timeout):
                logger.error("Timeout waiting for MQTT response")
                return False
            
            # Check if we received a valid response
            if not self.upload_response or 'presigned_url' not in self.upload_response:
                logger.error("Invalid response received from MQTT")
                return False
            
            # Verify upload_id matches
            if self.upload_response.get('upload_id') != upload_id:
                logger.error("Upload ID mismatch in response")
                return False
            
            # Upload file to S3
            presigned_url = self.upload_response['presigned_url']
            if not self.upload_file_to_s3(file_path, presigned_url):
                return False
            
            logger.info("Complete upload workflow finished successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Error in upload workflow: {e}")
            return False
    
    def cleanup(self):
        """Clean up MQTT client connection and temporary files."""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logger.info("MQTT client disconnected")
        
        # Clean up temporary certificate files
        if self._temp_cert_file:
            try:
                os.unlink(self._temp_cert_file)
                logger.info(f"Removed temporary certificate file")
            except Exception as e:
                logger.warning(f"Failed to remove temporary certificate file: {e}")
        
        if self._temp_key_file:
            try:
                os.unlink(self._temp_key_file)
                logger.info(f"Removed temporary key file")
            except Exception as e:
                logger.warning(f"Failed to remove temporary key file: {e}")


def main():
    """Main function demonstrating the upload workflow with CLI argument parsing."""
    import argparse

    parser = argparse.ArgumentParser(description="AXF Upload Client")
    parser.add_argument('--customer_id', type=int, default=None, help='Customer identifier for MQTT topic (or set ULOGGER_CUSTOMER_ID env var)')
    parser.add_argument('--application_id', type=int, default=None, help='Application identifier (or set ULOGGER_APPLICATION_ID env var)')
    parser.add_argument('--device_type', type=str, default=None, help='Device type (or set ULOGGER_DEVICE_TYPE env var)')
    parser.add_argument('--version', type=str, required=True, help='Software version number')
    parser.add_argument('--git_hash', type=str, required=True, help='Git hash for the firmware')
    parser.add_argument('--branch', type=str, required=True, help='Branch name to include in upload request')
    parser.add_argument('--cert_path', type=str, default='certificate.pem.crt', help='Path to certificate file')
    parser.add_argument('--key_path', type=str, default='private.pem.key', help='Path to private key file')
    parser.add_argument('--file', type=str, required=True, help='AXF file to upload')
    parser.add_argument('--timeout', type=int, default=30, help='Timeout in seconds to wait for MQTT response')

    args = parser.parse_args()

    # Pull customer_id, application_id, and device_type from environment if not provided
    customer_id = args.customer_id if args.customer_id is not None else os.environ.get('ULOGGER_CUSTOMER_ID')
    application_id = args.application_id if args.application_id is not None else os.environ.get('ULOGGER_APPLICATION_ID')
    device_type = args.device_type if args.device_type is not None else os.environ.get('ULOGGER_DEVICE_TYPE')

    if customer_id is None:
        logger.error("customer_id not provided and ULOGGER_CUSTOMER_ID environment variable not set.")
        exit(1)
    if application_id is None:
        logger.error("application_id not provided and ULOGGER_APPLICATION_ID environment variable not set.")
        exit(1)
    if device_type is None:
        logger.error("device_type not provided and ULOGGER_DEVICE_TYPE environment variable not set.")
        exit(1)

    # Convert customer_id and application_id to int if they came from env
    if isinstance(customer_id, str):
        try:
            customer_id = int(customer_id)
        except ValueError:
            logger.error("ULOGGER_CUSTOMER_ID environment variable must be an integer.")
            exit(1)
    
    if isinstance(application_id, str):
        try:
            application_id = int(application_id)
        except ValueError:
            logger.error("ULOGGER_APPLICATION_ID environment variable must be an integer.")
            exit(1)

    sample_file = args.file

    # Check for certificate and key data in environment variables
    cert_data = os.environ.get('ULOGGER_CERT_DATA', '')
    key_data = os.environ.get('ULOGGER_KEY_DATA', '')
    
    cert_path = args.cert_path
    key_path = args.key_path
    
    # If cert/key data is provided in env vars, create temporary files
    temp_cert_file = None
    temp_key_file = None
    
    try:
        if cert_data:
            # Create temporary file for certificate data
            temp_cert_fd, temp_cert_file = tempfile.mkstemp(suffix='.crt', text=True)
            with os.fdopen(temp_cert_fd, 'w') as f:
                f.write(cert_data)
            cert_path = temp_cert_file
            logger.info(f"Using certificate data from ULOGGER_CERT_DATA environment variable")
        
        if key_data:
            # Create temporary file for key data
            temp_key_fd, temp_key_file = tempfile.mkstemp(suffix='.key', text=True)
            with os.fdopen(temp_key_fd, 'w') as f:
                f.write(key_data)
            key_path = temp_key_file
            logger.info(f"Using key data from ULOGGER_KEY_DATA environment variable")

        # Create upload client with certificate authentication
        client = AxfUploadClient(
            customer_id=customer_id,
            device_type=device_type,
            cert_file=cert_path,
            key_file=key_path
        )
        
        # Store application_id for use in upload request
        client.application_id = application_id
        
        # Store temp file paths in client for cleanup
        client._temp_cert_file = temp_cert_file
        client._temp_key_file = temp_key_file

        # Upload the file
        success = client.upload_axf_file(
            file_path=sample_file,
            git_hash=args.git_hash,
            version_number=args.version,
            upload_id=random.randint(0, int(100e9)),
            timeout=args.timeout,
            branch=args.branch
        )

        if success:
            logger.info("Upload completed successfully!")
        else:
            logger.error("Upload failed!")

        # Cleanup
        client.cleanup()

    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        # Clean up temporary certificate files if they were created
        if temp_cert_file and os.path.exists(temp_cert_file):
            try:
                os.unlink(temp_cert_file)
                logger.info(f"Removed temporary certificate file")
            except Exception as e:
                logger.warning(f"Failed to remove temporary certificate file: {e}")
        
        if temp_key_file and os.path.exists(temp_key_file):
            try:
                os.unlink(temp_key_file)
                logger.info(f"Removed temporary key file")
            except Exception as e:
                logger.warning(f"Failed to remove temporary key file: {e}")


if __name__ == "__main__":
    main()

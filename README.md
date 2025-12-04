# uLogger AXF Upload GitHub Action

A GitHub composite action that uploads AXF firmware files to the uLogger platform using MQTT and S3.

## Features

- 🚀 Easy integration - just a few lines in your workflow
- 🔐 Secure authentication with certificate-based MQTT
- 📦 Automatic dependency management
- ⚡ Fast uploads with presigned S3 URLs
- 🔄 Built-in retry logic and error handling

## Usage

### Basic Example

```yaml
name: Build and Upload Firmware

on:
  push:
    branches: [ main ]

jobs:
  build-and-upload:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      # Your build steps here
      - name: Build firmware
        run: make build
      
      # Upload the AXF file
      - name: Upload to uLogger
        uses: ulogger-ai/ulogger_upload@v1
        with:
          customer_id: ${{ secrets.ULOGGER_CUSTOMER_ID }}
          application_id: ${{ secrets.ULOGGER_APPLICATION_ID }}
          device_type: 'your-device-name'
          version: '1.0.0'
          git_hash: ${{ github.sha }}
          branch: ${{ github.ref_name }}
          file: 'build/firmware.axf'
          cert_data: ${{ secrets.ULOGGER_CERT_DATA }}
          key_data: ${{ secrets.ULOGGER_KEY_DATA }}
```

### Using Certificate Files

If you prefer to use certificate files instead of storing them in secrets:

```yaml
- name: Upload to uLogger
  uses: ulogger-ai/ulogger_upload@v1
  with:
    customer_id: ${{ secrets.ULOGGER_CUSTOMER_ID }}
    application_id: ${{ secrets.ULOGGER_APPLICATION_ID }}
    device_type: 'your-device-name'
    version: '1.0.0'
    git_hash: ${{ github.sha }}
    branch: ${{ github.ref_name }}
    file: 'build/firmware.axf'
    cert_path: './certs/certificate.pem.crt'
    key_path: './certs/private.pem.key'
```

### Using Environment Variables

You can also set credentials via environment variables in your workflow:

```yaml
- name: Upload to uLogger
  uses: ulogger-ai/ulogger_upload@v1
  env:
    ULOGGER_CUSTOMER_ID: ${{ secrets.ULOGGER_CUSTOMER_ID }}
    ULOGGER_APPLICATION_ID: ${{ secrets.ULOGGER_APPLICATION_ID }}
    ULOGGER_DEVICE_TYPE: 'your-device-name'
    ULOGGER_CERT_DATA: ${{ secrets.ULOGGER_CERT_DATA }}
    ULOGGER_KEY_DATA: ${{ secrets.ULOGGER_KEY_DATA }}
  with:
    version: '1.0.0'
    git_hash: ${{ github.sha }}
    branch: ${{ github.ref_name }}
    file: 'build/firmware.axf'
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `customer_id` | Customer identifier for MQTT topic | No* | - |
| `application_id` | Application identifier | No* | - |
| `device_type` | Device type | No* | - |
| `version` | Software version number | Yes | - |
| `git_hash` | Git hash for the firmware | Yes | - |
| `branch` | Branch name to include in upload request | Yes | - |
| `file` | Path to the AXF file to upload | Yes | - |
| `cert_data` | Certificate data (PEM format) for MQTT authentication | No** | - |
| `key_data` | Private key data (PEM format) for MQTT authentication | No** | - |
| `cert_path` | Path to certificate file (alternative to cert_data) | No** | `certificate.pem.crt` |
| `key_path` | Path to private key file (alternative to key_data) | No** | `private.pem.key` |
| `timeout` | Timeout in seconds to wait for MQTT response | No | `30` |

\* Can be provided via `ULOGGER_CUSTOMER_ID`, `ULOGGER_APPLICATION_ID`, and `ULOGGER_DEVICE_TYPE` environment variables.

\*\* Either `cert_data`/`key_data` or `cert_path`/`key_path` must be provided. Certificate data can also be provided via `ULOGGER_CERT_DATA` and `ULOGGER_KEY_DATA` environment variables.

## Setting Up Secrets

To use this action, you'll need to configure the following secrets in your GitHub repository:

1. Go to your repository's **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add the following:

### Required Secrets

- `ULOGGER_CUSTOMER_ID`: Your uLogger customer ID
- `ULOGGER_APPLICATION_ID`: Your uLogger application ID
- `ULOGGER_DEVICE_TYPE`: Your device type identifier
- `ULOGGER_CERT_DATA`: Your MQTT certificate in PEM format
- `ULOGGER_KEY_DATA`: Your MQTT private key in PEM format

### Certificate Format

The certificate and key should be in PEM format. To convert your certificate files to the format needed for GitHub secrets:

```bash
# Certificate
cat certificate.pem.crt

# Private Key
cat private.pem.key
```

Copy the entire output including the `-----BEGIN CERTIFICATE-----` and `-----END CERTIFICATE-----` lines.

## Advanced Usage

### Dynamic Versioning

```yaml
- name: Get version from tag
  id: version
  run: echo "VERSION=${GITHUB_REF#refs/tags/}" >> $GITHUB_OUTPUT

- name: Upload to uLogger
  uses: ulogger-ai/ulogger_upload@v1
  with:
    # ... other inputs
    version: ${{ steps.version.outputs.VERSION }}
    git_hash: ${{ github.sha }}
```

### Multiple Builds

```yaml
strategy:
  matrix:
    device: [sensor-v1, sensor-v2, gateway]
    
steps:
  - name: Build ${{ matrix.device }}
    run: make build-${{ matrix.device }}
    
  - name: Upload ${{ matrix.device }} to uLogger
    uses: ulogger-ai/ulogger_upload@v1
    with:
      device_type: ${{ matrix.device }}
      file: 'build/${{ matrix.device }}.axf'
      # ... other inputs
```

## How It Works

1. **MQTT Request**: The action publishes an upload request to the uLogger MQTT broker
2. **Lambda Trigger**: The MQTT message triggers an AWS Lambda function
3. **Presigned URL**: Lambda generates and returns a presigned S3 URL
4. **S3 Upload**: The action uploads the AXF file directly to S3 using the presigned URL

## Troubleshooting

### Certificate Authentication Errors

If you see certificate authentication errors:
- Verify your certificate and key are in valid PEM format
- Ensure the certificate hasn't expired
- Check that the certificate matches the customer ID

### Timeout Issues

If uploads are timing out:
- Check your network connectivity
- Verify the MQTT broker (`mqtt.ulogger.ai:8883`) is accessible

### File Not Found

If the AXF file isn't found:
- Verify the file path is correct relative to the workspace root
- Ensure your build step completed successfully
- Check that the file has a `.axf` extension

## Support

For issues or questions:
- Open an issue in this repository
- Contact uLogger support at support@ulogger.ai
- Visit our documentation at (https://www.ulogger.ai/documentation.html)

## License

This action is provided as-is for use with the uLogger platform.

# Cloud Storage Integration Guide

This guide covers integrating EdgarTools with cloud storage providers (AWS S3, Google Cloud Storage, Azure Blob Storage) and S3-compatible services (Cloudflare R2, MinIO, DigitalOcean Spaces).

## Why Cloud Storage?

Cloud storage provides several advantages over local storage:

| Benefit | Description |
|---------|-------------|
| **Scalability** | Store terabytes of SEC data without local disk constraints |
| **Team Sharing** | Multiple users/services access the same dataset |
| **Durability** | Cloud providers offer 99.999999999% durability |
| **Cost Efficiency** | Pay only for storage used; cheaper than provisioning servers |
| **Global Access** | Access data from anywhere, any environment |

## Integration Approaches

EdgarTools supports cloud storage through three mechanisms:

1. **`use_cloud_storage()`** - Native cloud integration via fsspec for **reading and writing** (recommended)
2. **`EDGAR_DATA_URL`** - Point to any HTTP endpoint for **reading** data
3. **`EDGAR_LOCAL_DATA_DIR` + FUSE** - Mount cloud storage as a local path (legacy)

### Approach Comparison

| Feature | Native (`use_cloud_storage`) | EDGAR_DATA_URL | FUSE Mount |
|---------|------------------------------|----------------|------------|
| **Setup Complexity** | Simple | Simple | Complex |
| **Read Data** | Yes | Yes | Yes |
| **Write Data** | Yes | No | Yes |
| **Requires Mount** | No | No | Yes |
| **Platform Support** | All | All | Linux/macOS |
| **Best For** | Full cloud integration | Read-only HTTP | Legacy systems |

---

## Approach 1: EDGAR_DATA_URL (Read-Only)

The simplest approach for read-only access. Point EdgarTools to an HTTP endpoint serving your SEC data.

### How It Works

```python
import os
os.environ['EDGAR_DATA_URL'] = 'https://your-bucket.s3.amazonaws.com/edgar-data/'
os.environ['EDGAR_USE_LOCAL_DATA'] = '1'

from edgar import Company
company = Company("AAPL")  # Fetches from your S3 bucket
```

### Setting Up S3 Static Website Hosting

#### Step 1: Create and Configure S3 Bucket

```bash
# Create bucket
aws s3 mb s3://my-edgar-data --region us-east-1

# Enable static website hosting
aws s3 website s3://my-edgar-data \
    --index-document index.html \
    --error-document error.html
```

#### Step 2: Set Bucket Policy for Public Read

Create `bucket-policy.json`:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::my-edgar-data/*"
        }
    ]
}
```

Apply the policy:

```bash
aws s3api put-bucket-policy \
    --bucket my-edgar-data \
    --policy file://bucket-policy.json
```

#### Step 3: Upload Your Data

```bash
# Sync local edgar data to S3
aws s3 sync ~/.edgar s3://my-edgar-data/ --storage-class STANDARD_IA
```

#### Step 4: Configure EdgarTools

```python
import os

# S3 static website URL format
os.environ['EDGAR_DATA_URL'] = 'http://my-edgar-data.s3-website-us-east-1.amazonaws.com/'
os.environ['EDGAR_USE_LOCAL_DATA'] = '1'

from edgar import Company
company = Company("AAPL")  # Now reads from S3
```

### Google Cloud Storage Setup

```bash
# Create bucket with uniform access
gsutil mb -l us-central1 gs://my-edgar-data

# Make bucket publicly readable
gsutil iam ch allUsers:objectViewer gs://my-edgar-data

# Upload data
gsutil -m rsync -r ~/.edgar gs://my-edgar-data/
```

Configure EdgarTools:

```python
import os
os.environ['EDGAR_DATA_URL'] = 'https://storage.googleapis.com/my-edgar-data/'
os.environ['EDGAR_USE_LOCAL_DATA'] = '1'
```

### Azure Blob Storage Setup

```bash
# Create storage account and container
az storage account create --name myedgardata --resource-group mygroup
az storage container create --name edgar --account-name myedgardata --public-access blob

# Upload data
az storage blob upload-batch \
    --account-name myedgardata \
    --destination edgar \
    --source ~/.edgar
```

Configure EdgarTools:

```python
import os
os.environ['EDGAR_DATA_URL'] = 'https://myedgardata.blob.core.windows.net/edgar/'
os.environ['EDGAR_USE_LOCAL_DATA'] = '1'
```

### Adding CloudFront CDN (Recommended for Production)

For better performance and reduced S3 costs, add CloudFront:

```bash
# Create CloudFront distribution pointing to S3
aws cloudfront create-distribution \
    --origin-domain-name my-edgar-data.s3.amazonaws.com \
    --default-root-object index.html
```

Then use your CloudFront URL:

```python
os.environ['EDGAR_DATA_URL'] = 'https://d1234567890.cloudfront.net/'
```

---

## Approach 2: FUSE Mount (Read/Write)

For full read/write access, mount cloud storage as a local filesystem using FUSE (Filesystem in Userspace).

### FUSE Tool Comparison

| Tool | Provider | Performance | Caching | Notes |
|------|----------|-------------|---------|-------|
| **s3fs-fuse** | AWS S3 | Moderate | Basic | Most compatible |
| **goofys** | AWS S3 | Fast | Aggressive | Performance-focused |
| **rclone mount** | All providers | Good | Configurable | Most versatile |
| **gcsfuse** | Google Cloud | Good | Metadata | Official GCS tool |
| **blobfuse2** | Azure | Good | File cache | Official Azure tool |

### s3fs-fuse Setup (AWS S3)

#### Installation

```bash
# Ubuntu/Debian
sudo apt-get install s3fs

# macOS
brew install s3fs

# From source
git clone https://github.com/s3fs-fuse/s3fs-fuse.git
cd s3fs-fuse && ./autogen.sh && ./configure && make && sudo make install
```

#### Configuration

Create credentials file:

```bash
echo "ACCESS_KEY_ID:SECRET_ACCESS_KEY" > ~/.passwd-s3fs
chmod 600 ~/.passwd-s3fs
```

#### Mount the Bucket

```bash
# Create mount point
mkdir -p /mnt/edgar-data

# Mount with caching for better performance
s3fs my-edgar-bucket /mnt/edgar-data \
    -o passwd_file=~/.passwd-s3fs \
    -o url=https://s3.amazonaws.com \
    -o use_cache=/tmp/s3fs-cache \
    -o ensure_diskfree=1024 \
    -o parallel_count=15
```

#### Configure EdgarTools

```python
import os
os.environ['EDGAR_LOCAL_DATA_DIR'] = '/mnt/edgar-data'
os.environ['EDGAR_USE_LOCAL_DATA'] = '1'

from edgar import download_filings
download_filings("2025-01-15")  # Writes directly to S3!
```

### goofys Setup (High Performance S3)

goofys offers better performance than s3fs at the cost of some POSIX compliance.

#### Installation

```bash
# Download binary
wget https://github.com/kahing/goofys/releases/latest/download/goofys
chmod +x goofys
sudo mv goofys /usr/local/bin/
```

#### Mount

```bash
# Uses standard AWS credentials (~/.aws/credentials)
goofys my-edgar-bucket /mnt/edgar-data

# With specific profile
goofys --profile production my-edgar-bucket /mnt/edgar-data

# With caching
goofys --stat-cache-ttl 1h --type-cache-ttl 1h my-edgar-bucket /mnt/edgar-data
```

### rclone mount (Multi-Provider)

rclone supports 40+ cloud storage providers with a unified interface.

#### Installation

```bash
# Linux
curl https://rclone.org/install.sh | sudo bash

# macOS
brew install rclone
```

#### Configure Provider

```bash
# Interactive configuration
rclone config

# Example: Configure S3
# Name: edgar-s3
# Type: s3
# Provider: AWS
# Access key: (your key)
# Secret key: (your secret)
# Region: us-east-1
```

#### Mount

```bash
# Basic mount
rclone mount edgar-s3:my-edgar-bucket /mnt/edgar-data

# With VFS caching (recommended)
rclone mount edgar-s3:my-edgar-bucket /mnt/edgar-data \
    --vfs-cache-mode full \
    --vfs-cache-max-age 24h \
    --vfs-read-ahead 128M \
    --buffer-size 128M \
    --daemon
```

### gcsfuse Setup (Google Cloud)

```bash
# Installation
export GCSFUSE_REPO=gcsfuse-$(lsb_release -c -s)
echo "deb https://packages.cloud.google.com/apt $GCSFUSE_REPO main" | sudo tee /etc/apt/sources.list.d/gcsfuse.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update && sudo apt-get install gcsfuse

# Mount
gcsfuse --implicit-dirs my-edgar-bucket /mnt/edgar-data
```

### blobfuse2 Setup (Azure)

```bash
# Installation
wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update && sudo apt-get install blobfuse2

# Create config file
cat > ~/blobfuse2.yaml << EOF
allow-other: true
logging:
  type: syslog
  level: log_warning
components:
  - libfuse
  - file_cache
  - attr_cache
  - azstorage
libfuse:
  attribute-expiration-sec: 120
  entry-expiration-sec: 120
file_cache:
  path: /tmp/blobfuse2
  timeout-sec: 120
  max-size-mb: 4096
azstorage:
  type: block
  account-name: myedgardata
  account-key: YOUR_ACCOUNT_KEY
  container: edgar
EOF

# Mount
blobfuse2 mount /mnt/edgar-data --config-file=~/blobfuse2.yaml
```

### Systemd Service (Auto-Mount on Boot)

Create `/etc/systemd/system/edgar-s3.service`:

```ini
[Unit]
Description=Mount S3 Edgar Data
After=network-online.target

[Service]
Type=forking
User=edgar
ExecStart=/usr/local/bin/goofys -o allow_other my-edgar-bucket /mnt/edgar-data
ExecStop=/bin/fusermount -u /mnt/edgar-data
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl enable edgar-s3
sudo systemctl start edgar-s3
```

---

## S3-Compatible Services

### Cloudflare R2

R2 offers S3-compatible storage with zero egress fees.

#### Key Configuration

R2 requires `region_name='auto'`:

```bash
# s3fs with R2
echo "R2_ACCESS_KEY:R2_SECRET_KEY" > ~/.passwd-r2
s3fs my-bucket /mnt/edgar-data \
    -o passwd_file=~/.passwd-r2 \
    -o url=https://ACCOUNT_ID.r2.cloudflarestorage.com \
    -o use_path_request_style
```

#### rclone Configuration for R2

```bash
rclone config

# Name: edgar-r2
# Type: s3
# Provider: Cloudflare
# access_key_id: (R2 access key)
# secret_access_key: (R2 secret key)
# endpoint: https://ACCOUNT_ID.r2.cloudflarestorage.com
# acl: private
```

Mount:

```bash
rclone mount edgar-r2:my-edgar-bucket /mnt/edgar-data \
    --vfs-cache-mode full
```

#### EDGAR_DATA_URL with R2

For read-only access via R2's public URL:

```python
import os

# Enable public access on your R2 bucket first
os.environ['EDGAR_DATA_URL'] = 'https://pub-xxxxx.r2.dev/'
os.environ['EDGAR_USE_LOCAL_DATA'] = '1'
```

### MinIO

MinIO is perfect for on-premises or private cloud deployments.

```bash
# s3fs with MinIO
s3fs my-bucket /mnt/edgar-data \
    -o passwd_file=~/.passwd-minio \
    -o url=https://minio.example.com \
    -o use_path_request_style

# rclone config
# Provider: Minio
# Endpoint: https://minio.example.com
```

### DigitalOcean Spaces

```bash
# rclone config
# Provider: DigitalOcean
# Endpoint: nyc3.digitaloceanspaces.com
```

---

## Hybrid Architecture Pattern

Combine the best of both approaches for optimal performance:

```
┌─────────────────────────────────────────────────────────────┐
│                    Hybrid Architecture                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   WRITES (Download/Sync)          READS (Analysis)          │
│   ┌─────────────────┐            ┌─────────────────┐        │
│   │   FUSE Mount    │            │ EDGAR_DATA_URL  │        │
│   │   (s3fs/rclone) │            │ + CloudFront    │        │
│   └────────┬────────┘            └────────┬────────┘        │
│            │                              │                 │
│            ▼                              ▼                 │
│   ┌──────────────────────────────────────────────────┐      │
│   │              S3 Bucket (Origin)                  │      │
│   │              my-edgar-data                       │      │
│   └──────────────────────────────────────────────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

**Download Server (writes to S3):**

```bash
# Mount S3 for writing
goofys my-edgar-bucket /mnt/edgar-data

# Configure EdgarTools
export EDGAR_LOCAL_DATA_DIR=/mnt/edgar-data
export EDGAR_USE_LOCAL_DATA=1
```

```python
from edgar import download_filings
download_filings("2025-01-01:2025-01-31")  # Writes to S3
```

**Analysis Clients (reads via HTTP):**

```python
import os

# Fast reads via CloudFront
os.environ['EDGAR_DATA_URL'] = 'https://d1234567890.cloudfront.net/'
os.environ['EDGAR_USE_LOCAL_DATA'] = '1'

from edgar import Company, get_filings
# All reads go through CloudFront CDN
filings = get_filings(form="10-K", year=2024)
```

---

## Sync Strategies

### Initial Bulk Upload

```bash
# Parallel upload with rclone
rclone copy ~/.edgar edgar-s3:my-edgar-bucket \
    --transfers 32 \
    --checkers 16 \
    --progress

# Or with AWS CLI
aws s3 sync ~/.edgar s3://my-edgar-bucket \
    --storage-class STANDARD_IA
```

### Incremental Daily Sync

Create a cron job for daily updates:

```bash
# /etc/cron.d/edgar-sync
0 6 * * * edgar /usr/local/bin/edgar-daily-sync.sh
```

`edgar-daily-sync.sh`:

```bash
#!/bin/bash
set -e

# Download yesterday's filings locally first
export EDGAR_LOCAL_DATA_DIR=/tmp/edgar-staging
python -c "
from edgar import download_filings
from datetime import datetime, timedelta
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
download_filings(yesterday)
"

# Sync to S3
rclone sync /tmp/edgar-staging/filings edgar-s3:my-edgar-bucket/filings \
    --transfers 16 \
    --progress

# Cleanup
rm -rf /tmp/edgar-staging
```

### Bidirectional Sync

For teams with multiple download nodes:

```bash
# Use rclone bisync for two-way sync
rclone bisync /mnt/local-edgar edgar-s3:my-edgar-bucket \
    --resync \
    --verbose
```

---

## Performance Optimization

### Caching Recommendations

| Scenario | Tool | Cache Settings |
|----------|------|----------------|
| Frequent reads | goofys | `--stat-cache-ttl 1h` |
| Large file writes | rclone | `--vfs-cache-mode full --vfs-cache-max-size 10G` |
| Mixed workload | s3fs | `-o use_cache=/tmp/s3cache -o ensure_diskfree=2048` |

### Compression

Filings are already compressed by EdgarTools. Additional S3 compression isn't necessary.

### Lifecycle Policies

Reduce storage costs with lifecycle rules:

```json
{
    "Rules": [
        {
            "ID": "MoveToIA",
            "Status": "Enabled",
            "Filter": {"Prefix": "filings/"},
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 180,
                    "StorageClass": "GLACIER"
                }
            ]
        }
    ]
}
```

---

## Troubleshooting

### Common Issues

**"Transport endpoint not connected"**
```bash
# FUSE mount crashed - remount
sudo fusermount -u /mnt/edgar-data
goofys my-edgar-bucket /mnt/edgar-data
```

**Slow performance with s3fs**
```bash
# Enable parallel requests and caching
s3fs bucket /mnt/data \
    -o parallel_count=20 \
    -o multipart_size=52 \
    -o use_cache=/tmp/s3cache \
    -o max_stat_cache_size=100000
```

**Permission denied on mount**
```bash
# Add user_allow_other to /etc/fuse.conf
echo "user_allow_other" | sudo tee -a /etc/fuse.conf

# Mount with allow_other
s3fs bucket /mnt/data -o allow_other
```

**R2 connection issues**
```bash
# Ensure region is set to 'auto'
s3fs bucket /mnt/data \
    -o url=https://ACCOUNT_ID.r2.cloudflarestorage.com \
    -o use_path_request_style \
    -o sigv2
```

### Debugging

```bash
# s3fs debug mode
s3fs bucket /mnt/data -d -f -o dbglevel=info

# rclone debug
rclone mount remote:bucket /mnt/data -vv --log-file=/tmp/rclone.log

# Check mount status
mount | grep fuse
df -h /mnt/edgar-data
```

---

## Security Best Practices

### IAM Policies (AWS)

Least-privilege policy for EdgarTools:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::my-edgar-bucket",
                "arn:aws:s3:::my-edgar-bucket/*"
            ]
        }
    ]
}
```

### Encryption

```bash
# Enable server-side encryption
aws s3api put-bucket-encryption \
    --bucket my-edgar-bucket \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

### Private Access (No Public URLs)

For internal-only access, skip the static website hosting and use:

1. FUSE mount with IAM credentials
2. VPC endpoints for AWS
3. Private connectivity for GCP/Azure

---

## Native Cloud Support

EdgarTools provides native cloud storage support via `fsspec`, enabling seamless integration with S3, Google Cloud Storage, Azure Blob Storage, and S3-compatible services.

### Installation

Install the cloud storage dependencies for your provider:

```bash
# AWS S3, Cloudflare R2, MinIO, DigitalOcean Spaces
pip install edgartools[s3]

# Google Cloud Storage
pip install edgartools[gcs]

# Azure Blob Storage
pip install edgartools[azure]

# All cloud providers
pip install edgartools[all-cloud]
```

### Basic Usage

```python
import edgar

# AWS S3 (uses default credentials from ~/.aws or environment)
edgar.use_cloud_storage('s3://my-edgar-bucket/')

# Now all operations use cloud storage
company = edgar.Company("AAPL")
filings = company.get_filings(form="10-K")
```

### Provider Examples

#### AWS S3

```python
import edgar

# Using default AWS credentials
edgar.use_cloud_storage('s3://my-edgar-bucket/')

# With explicit credentials
edgar.use_cloud_storage(
    's3://my-edgar-bucket/',
    client_kwargs={
        'aws_access_key_id': 'YOUR_ACCESS_KEY',
        'aws_secret_access_key': 'YOUR_SECRET_KEY',
        'region_name': 'us-east-1'
    }
)
```

#### Cloudflare R2

```python
import edgar

edgar.use_cloud_storage(
    's3://my-bucket/',
    client_kwargs={
        'endpoint_url': 'https://ACCOUNT_ID.r2.cloudflarestorage.com',
        'region_name': 'auto'
    }
)
```

#### Google Cloud Storage

```python
import edgar

# Using default GCP credentials
edgar.use_cloud_storage('gs://my-edgar-bucket/')

# With explicit project
edgar.use_cloud_storage(
    'gs://my-edgar-bucket/',
    client_kwargs={'project': 'my-project'}
)
```

#### Azure Blob Storage

```python
import edgar

edgar.use_cloud_storage(
    'az://my-container/edgar/',
    client_kwargs={
        'account_name': 'myaccount',
        'account_key': 'YOUR_ACCOUNT_KEY'
    }
)
```

#### MinIO (Self-Hosted S3)

```python
import edgar

edgar.use_cloud_storage(
    's3://edgar-data/',
    client_kwargs={
        'endpoint_url': 'http://localhost:9000',
        'aws_access_key_id': 'minioadmin',
        'aws_secret_access_key': 'minioadmin'
    }
)
```

### Disabling Cloud Storage

```python
import edgar

# Revert to local storage
edgar.use_cloud_storage(disable=True)
```

### Uploading Data to Cloud Storage

EdgarTools provides two ways to populate your cloud storage with SEC data:

#### Option 1: Download and Upload in One Step

Use the `upload_to_cloud` parameter with `download_filings()`:

```python
import edgar

# Configure cloud storage first
edgar.use_cloud_storage('s3://my-edgar-bucket/')

# Download filings and upload to cloud automatically
edgar.download_filings('2025-01-15', upload_to_cloud=True)

# Download a date range
edgar.download_filings('2025-01-01:2025-01-15', upload_to_cloud=True)
```

#### Option 2: Sync Existing Local Data

Use `sync_to_cloud()` to upload data you've already downloaded locally:

```python
import edgar

# Configure cloud storage
edgar.use_cloud_storage('s3://my-edgar-bucket/')

# Sync all local filings to cloud
result = edgar.sync_to_cloud('filings')
print(f"Uploaded: {result['uploaded']}, Skipped: {result['skipped']}")

# Sync specific date directory
edgar.sync_to_cloud('filings/20250115')

# Preview what would be uploaded (dry run)
edgar.sync_to_cloud('filings', dry_run=True)

# Overwrite existing files in cloud
edgar.sync_to_cloud('filings', overwrite=True)
```

#### sync_to_cloud() Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_path` | str | None | Subdirectory to sync (e.g., 'filings', 'filings/20250115') |
| `pattern` | str | '**/*' | Glob pattern for files to sync |
| `batch_size` | int | 20 | Number of concurrent uploads |
| `overwrite` | bool | False | Overwrite existing files in cloud |
| `dry_run` | bool | False | Preview without uploading |

#### Return Value

`sync_to_cloud()` returns a dict with upload statistics:

```python
{
    'uploaded': 150,    # Files successfully uploaded
    'skipped': 50,      # Files already in cloud (when overwrite=False)
    'failed': 0,        # Files that failed to upload
    'errors': []        # Error messages for failed uploads
}
```

### Features

| Feature | Description |
|---------|-------------|
| **Cross-platform** | Works on Windows, macOS, and Linux |
| **No FUSE required** | Pure Python implementation |
| **Transparent compression** | Handles `.gz` files automatically |
| **Full read/write** | Both reading and writing supported |
| **Provider agnostic** | Same API for all cloud providers |

---

## Summary

| Use Case | Recommended Approach |
|----------|---------------------|
| **Native cloud support** | `use_cloud_storage()` (recommended) |
| **Read-only HTTP access** | `EDGAR_DATA_URL` + static website |
| **Legacy FUSE mount** | goofys or rclone mount |
| **On-premises** | MinIO + `use_cloud_storage()` |
| **Zero egress costs** | Cloudflare R2 |

### Quick Start

**Native cloud storage (recommended):**
```python
import edgar

# Install: pip install edgartools[s3]
edgar.use_cloud_storage('s3://my-edgar-bucket/')

# Read from cloud
company = edgar.Company("AAPL")

# Write to cloud
edgar.download_filings('2025-01-15', upload_to_cloud=True)

# Or sync existing local data
edgar.sync_to_cloud('filings')
```

**Read-only via HTTP:**
```python
import os
os.environ['EDGAR_DATA_URL'] = 'https://your-bucket.s3.amazonaws.com/'
os.environ['EDGAR_USE_LOCAL_DATA'] = '1'
```

**Legacy FUSE mount (Linux/macOS):**
```bash
goofys my-edgar-bucket /mnt/edgar-data
export EDGAR_LOCAL_DATA_DIR=/mnt/edgar-data
export EDGAR_USE_LOCAL_DATA=1
```

For questions or feedback, see [Discussion #507](https://github.com/dgunning/edgartools/discussions/507).

#!/bin/sh
set -eu

awslocal s3api head-bucket --bucket tutorcrm-private 2>/dev/null || \
  awslocal s3api create-bucket \
    --bucket tutorcrm-private \
    --create-bucket-configuration LocationConstraint=eu-central-1

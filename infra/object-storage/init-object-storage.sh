#!/bin/sh
set -eu

: "${GROVELLO_OBJECT_STORAGE_ENDPOINT:?Object storage endpoint is required}"
: "${GROVELLO_OBJECT_STORAGE_BUCKET:?Object storage bucket is required}"
: "${GROVELLO_OBJECT_STORAGE_ROOT_USER:?Object storage root user is required}"
: "${GROVELLO_OBJECT_STORAGE_ROOT_PASSWORD:?Object storage root password is required}"
: "${GROVELLO_OBJECT_STORAGE_ACCESS_KEY_ID:?Application access key ID is required}"
: "${GROVELLO_OBJECT_STORAGE_SECRET_ACCESS_KEY:?Application secret access key is required}"

if [ "$GROVELLO_OBJECT_STORAGE_ROOT_USER" = "$GROVELLO_OBJECT_STORAGE_ACCESS_KEY_ID" ]; then
  echo "Application access key must differ from the MinIO root user" >&2
  exit 1
fi

bucket_length=${#GROVELLO_OBJECT_STORAGE_BUCKET}
case "$GROVELLO_OBJECT_STORAGE_BUCKET" in
  *..* | *[!a-z0-9.-]* | .* | *- | -* | *.)
    echo "Object storage bucket must use a normalized DNS-compatible name" >&2
    exit 1
    ;;
esac
if [ "$bucket_length" -lt 3 ] || [ "$bucket_length" -gt 63 ]; then
  echo "Object storage bucket must contain between 3 and 63 characters" >&2
  exit 1
fi

alias_name="grovello-local"
policy_name="grovello-asset-storage-$GROVELLO_OBJECT_STORAGE_BUCKET"
policy_file="/tmp/grovello-asset-storage-policy.json"

mc alias set \
  "$alias_name" \
  "$GROVELLO_OBJECT_STORAGE_ENDPOINT" \
  "$GROVELLO_OBJECT_STORAGE_ROOT_USER" \
  "$GROVELLO_OBJECT_STORAGE_ROOT_PASSWORD" >/dev/null
mc ready "$alias_name"
mc mb --ignore-existing "$alias_name/$GROVELLO_OBJECT_STORAGE_BUCKET"
mc version enable "$alias_name/$GROVELLO_OBJECT_STORAGE_BUCKET"
mc anonymous set none "$alias_name/$GROVELLO_OBJECT_STORAGE_BUCKET"

cat >"$policy_file" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation",
        "s3:ListBucket",
        "s3:ListBucketMultipartUploads"
      ],
      "Resource": ["arn:aws:s3:::$GROVELLO_OBJECT_STORAGE_BUCKET"]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:AbortMultipartUpload",
        "s3:DeleteObject",
        "s3:GetObject",
        "s3:ListMultipartUploadParts",
        "s3:PutObject"
      ],
      "Resource": ["arn:aws:s3:::$GROVELLO_OBJECT_STORAGE_BUCKET/*"]
    }
  ]
}
EOF

if ! mc admin policy info "$alias_name" "$policy_name" >/dev/null 2>&1; then
  mc admin policy create "$alias_name" "$policy_name" "$policy_file"
fi

if mc admin user info "$alias_name" "$GROVELLO_OBJECT_STORAGE_ACCESS_KEY_ID" >/dev/null 2>&1; then
  mc admin user remove "$alias_name" "$GROVELLO_OBJECT_STORAGE_ACCESS_KEY_ID"
fi
mc admin user add \
  "$alias_name" \
  "$GROVELLO_OBJECT_STORAGE_ACCESS_KEY_ID" \
  "$GROVELLO_OBJECT_STORAGE_SECRET_ACCESS_KEY"
mc admin policy attach \
  "$alias_name" \
  "$policy_name" \
  --user "$GROVELLO_OBJECT_STORAGE_ACCESS_KEY_ID"

echo "Grovello object storage initialized with a private, versioned bucket."

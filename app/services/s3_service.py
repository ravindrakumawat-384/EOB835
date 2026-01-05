import boto3
from botocore.exceptions import BotoCoreError, ClientError
from typing import Optional
from urllib.parse import urlparse
from ..utils.logger import get_logger

logger = get_logger(__name__)

class S3Service:
    def __init__(self, bucket_name: str, aws_access_key_id: str, aws_secret_access_key: str, region_name: str):
        self.bucket_name = bucket_name
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )

    def upload_file(self, file_content: bytes, file_name: str) -> Optional[str]:
        try:
            self.s3.put_object(Bucket=self.bucket_name, Key=file_name, Body=file_content)
            logger.info(f"File {file_name} uploaded to S3 bucket {self.bucket_name}")
            return f"s3://{self.bucket_name}/{file_name}"
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to upload {file_name} to S3: {e}")
            return None
    
    def download_file(self, s3_path: str) -> bytes:
        """Download file content from S3"""
        try:
            # Extract bucket and key from s3://bucket/key format
            parsed = urlparse(s3_path)
            bucket_name = parsed.netloc
            file_key = parsed.path.lstrip("/")
            
            logger.info(f"Downloading from bucket: {bucket_name}, key: {file_key}")
            response = self.s3.get_object(Bucket=bucket_name, Key=file_key)
            file_content = response['Body'].read()
            logger.info(f"Successfully downloaded {len(file_content)} bytes from {s3_path}")
            return file_content
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to download file from {s3_path}: {e}")
            raise

    
    def generate_presigned_url(self, s3_key: str, expiration: int = 3600, response_content_disposition: Optional[str] = None, response_content_type: Optional[str] = None) -> Optional[str]:
        """Generate a presigned URL for downloading a file from S3.

        Optional parameters allow overriding the response content type and adding
        a ResponseContentDisposition header to force download with a filename.
        """
        try:
            parsed = urlparse(s3_key)
            bucket_name = parsed.netloc
            file_name = parsed.path.lstrip("/")
            params = {
                'Bucket': bucket_name,
                'Key': file_name,
            }
            # Allow caller to override response content type (default to pdf)
            params['ResponseContentType'] = response_content_type or "application/pdf"
            # Allow setting content disposition to force attachment filename
            if response_content_disposition:
                params['ResponseContentDisposition'] = response_content_disposition

            response = self.s3.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for {s3_key}, {response}")
            return response
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to generate presigned URL for {s3_key}: {e}")
            return None

    def generate_presigned_image_url(self, s3_path: str) -> Optional[str]:
            """Generate a presigned URL for an image file in S3, with content type detection."""
            from mimetypes import guess_type
            try:
                parsed = urlparse(s3_path)
                bucket_name = parsed.netloc
                file_name = parsed.path.lstrip("/")
                mime_type, _ = guess_type(file_name)
                if not mime_type:
                    mime_type = "application/octet-stream"
                response = self.s3.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': bucket_name,
                        'Key': file_name,
                        "ResponseContentType": mime_type
                    },
                    
                )
                logger.info(f"Generated presigned image URL for {s3_path}, {response}")
                return response
            except (BotoCoreError, ClientError) as e:
                logger.error(f"Failed to generate presigned image URL for {s3_path}: {e}")
                return None

    def extract_s3_key_from_path(self, s3_path: str) -> str:
        """Extract S3 key from s3://bucket/key format"""
        if s3_path.startswith(f"s3://{self.bucket_name}/"):
            return s3_path[len(f"s3://{self.bucket_name}/"):]
        return s3_path


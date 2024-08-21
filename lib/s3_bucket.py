import os
import boto3
from dotenv import load_dotenv
load_dotenv()

def send_to_s3(local_dir_path):
  s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
  )
  local_files = os.listdir(local_dir_path)
  for f_name in local_files:
    s3_client.upload_file(
      os.path.join(local_dir_path, f_name),
      os.environ['S3_BUCKET_NAME'],
      f'{os.environ["S3_PREFIX"]}/{f_name}'
    )
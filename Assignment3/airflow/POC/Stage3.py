import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

def upload_folder_to_s3(folder_path, bucket):
    # Initialize an S3 client using boto3
    s3 = boto3.client('s3')
    
    # Walk through the directory and its subdirectories
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            # Create the full file path by joining the root with the file name
            local_file_path = os.path.join(root, file)
            
            # Remove the folder_path from the local file path to get the S3 object key
            s3_file_path = os.path.relpath(local_file_path, folder_path)
            
            try:
                # Upload each file to S3, preserving the folder structure
                s3.upload_file(local_file_path, bucket, s3_file_path)
                print(f"Upload Successful: {local_file_path} to s3://{bucket}/{s3_file_path}")
            except FileNotFoundError:
                print(f"The file was not found: {local_file_path}")
            except NoCredentialsError:
                print("Credentials not available")
            except ClientError as e:
                print(f"Client error: {e}")

# Example usage:
folder_path = os.path.join(os.getcwd(), os.getenv('DOWNLOAD_DIRECTORY', 'downloads'))  # Specify the path to the folder you want to upload
bucket = os.getenv('AWS_BUCKET_NAME')  # Specify the S3 bucket name

# Call the function to upload the folder
upload_folder_to_s3(folder_path, bucket)

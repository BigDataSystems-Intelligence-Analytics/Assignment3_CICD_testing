
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

# Replace 'your-bucket-name' with your bucket name
BUCKET_NAME = 'publications-info'

try:
    # Initialize S3 client
    s3 = boto3.client('s3')

    # List objects in the specified bucket
    response = s3.list_objects_v2(Bucket=BUCKET_NAME)

    if 'Contents' in response:
        print(f"Objects in {BUCKET_NAME}:")
        for obj in response['Contents']:
            print(obj['Key'])
    else:
        print(f"No objects found in {BUCKET_NAME}.")
except NoCredentialsError:
    print("Credentials not available.")
except PartialCredentialsError:
    print("Incomplete credentials.")
except Exception as e:
    print(f"An error occurred: {e}")

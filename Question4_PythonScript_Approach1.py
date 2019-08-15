import logging
import boto3
from botocore.exceptions import ClientError

def list_bucket_objects(bucket_name):
    s3 = boto3.client('s3')
    try:
        response = s3.list_objects_v2(Bucket=bucket_name)
    except ClientError as e:
        # AllAccessDisabled error == bucket not found
        logging.error(e)
        return None

    return response['Contents']


def main():
    #AWS S3 Bucket Name
    test_bucket_name = 'cf-templates-1rm5pwd7fg86z-eu-west-1'

    # Set up logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)s: %(asctime)s: %(message)s')

    # Retrieve the bucket's object
    objects = list_bucket_objects(test_bucket_name)
    print('********* Content of S3 Bucket incorrectly uploaded *************')
    #print(objects)
    if objects is not None:
        # Logic to list the objects which dont have extension .mp4 and .3gp

        print(f'Objects in {test_bucket_name}')
        for obj in objects:
            x =(f'  {obj["Key"]}')

            if (x[-4:] != '.3gp' and x[-4:] != '.mp4' and x[-4:] != '.png'):
                print(x)
if __name__ == '__main__':
    main()

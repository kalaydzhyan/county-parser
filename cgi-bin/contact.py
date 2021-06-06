#!/usr/bin/python3

import boto3
from botocore.exceptions import ClientError
import cgi, cgitb

form    = cgi.FieldStorage() 
name    = form.getvalue('name')
email   = form.getvalue('email')
SUBJECT = form.getvalue('subject')
message = form.getvalue('message')

print("Status: 200 OK\n")


DEFAULT_REGION = 'us-east-2'
CHARSET        = "UTF-8"
SENDER         = "Abilene Rental Homes <abilene.rental.homes@gmail.com>"
RECIPIENT      = "abilene.rental.homes@gmail.com"
BODY_TEXT      = (
                   f"{name} with email {email} sent you the following message:"
                   f"{message}"
                   "This email was sent with Amazon SES using the "
                   "AWS SDK for Python (Boto)."
                 )

#CONFIGURATION_SET = "ConfigSet"


BODY_HTML = f"""<html>
                 <head></head>
                  <body>
                   Dear Admin,
                   <br><br>
                   <strong>{name}</strong> with email <strong>{email}</strong> sent you the following message:
                   <br><br>
                   {message}
                   <br><br>
                   <p>This is an automatic email sent with AWS SDK for Python (Boto) </p>
                  </body>
                 </html>
             """



aws_dict = {'region': DEFAULT_REGION}

for fname in ['config', 'credentials']:
    with open(fname, 'r') as f:
        for line in f:
            if '=' in line:
                key, val = line.split('=')
                aws_dict.update({key.strip(): val.strip()})

client = boto3.client('ses', region_name=aws_dict['region'],
                            aws_access_key_id=aws_dict['aws_access_key_id'],
                            aws_secret_access_key=aws_dict['aws_secret_access_key'])

try:
    response = client.send_email(
        Destination={
            'ToAddresses': [
                RECIPIENT,
            ],
        },
        Message={
            'Body': {
                'Html': {
                    'Charset': CHARSET,
                    'Data': BODY_HTML,
                },
                'Text': {
                    'Charset': CHARSET,
                    'Data': BODY_TEXT,
                },
            },
            'Subject': {
                'Charset': CHARSET,
                'Data': SUBJECT,
            },
        },
        Source=SENDER,
        # If you are not using a configuration set, comment or delete the
        # following line
        #ConfigurationSetName=CONFIGURATION_SET,
    )	
except ClientError as e:
    print(e.response['Error']['Message'])
else:
    print('OK\n')


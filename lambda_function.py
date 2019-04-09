
import os
import json
import boto3
import botocore
import re
import argparse
import pandas as pd
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
import datetime
import shutil


# TODO
# schedule check in lambda
# add bot command to accept case number
# add deployment pipeline on commit
# add debug info with logger
# add functionality to catch commands
# add format checker for input
# add command /info
# programm command /status
# add some stuff to answer on simple messages
# added fully functioning local run with params
#x add format check
#x added webhook and bot request functionality
#x 1. add functionality to pick up correct sheet.
#x 5. reverse date picking
#x 4. send result to telegram
#x 2. Interpret filter result
#c 3. read excel on the fly

case_types = {
    'DP': 0,
    'PP': 0,
    'DV': 0,
    'ZM': 1,
    'TP': 2
}
FORMAT_MSG = """
    Format seems to be incorrect.
    Example: If receipt number of your application is OAM-0334-5/PP-2015,
    then you will search for OAM-334/PP-2015.
    Found result will be as follows: OAM-334/PP-2015.
"""
LOCAL_FILE = "/tmp"

def save_update_id(update_id):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ['DB_TABLE_NAME'])
    table.update_item(
        Key={
            'id': '1'
        },
        UpdateExpression='SET update_id = :val1',
        ExpressionAttributeValues={
            ':val1': update_id
        }
    )


def read_update_id():

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ['DB_TABLE_NAME'])
    response = table.get_item(
        Key={
            'id': '1',
        }
    )
    return response['Item']['update_id']


def toOrdinalNum(n):

    return str(n) + {1: 'st', 2: 'nd', 3: 'rd'}.get(4 if 10 <= n % 100 < 20 else n % 10, "th")


def define_excel_sheet(case_num):

    case_type = case_num.split('/')[1].split('-')[0]
    return case_types[case_type]


def check_format(case_num):

    pattern = re.compile('^OAM-[^0]\d+/(DP|PP|DV|ZM|TP)-\d{4}$')
    return bool(pattern.match(case_num))

def empty_bucket(bucket_name):

    print('Clean up in bucket {}'.format(bucket_name))
    s3 = boto3.resource('s3')
    try:
        bucket = s3.Bucket(bucket_name)
        bucket.objects.all().delete()
        print('Bucket {} clean.'.format(bucket_name))
        return True
    except botocore.exceptions.ClientError as e:
        print('Bucket was not cleaned. With error: {}'.format(e))
        return False


def source_file_url():

    revert_days = 0
    month = datetime.datetime.today().strftime("%B").lower()
    year = datetime.datetime.today().strftime("%Y")

    while True:
        day = toOrdinalNum(int(datetime.datetime.today().strftime("%d"))-revert_days)
        url = "https://www.mvcr.cz/mvcren/file/list-valid-to-the-{}-{}-{}.aspx".format(month,day,year)
        print(url)
        try:
            head = urlopen(Request(url, method='HEAD'))
            return head.info()['Content-Disposition'].split('=')[1].strip('"'), url
        except HTTPError as e:
            print('HTTP error {}'.format(e))
            print('Chaecking previous day')
            revert_days += 1


def source_file_S3(filename, url):

    s3 = boto3.resource('s3')
    try:
        s3.Bucket(os.environ["BUCKET"]).download_file(filename, "{}/{}".format(LOCAL_FILE, filename))
        print('File taken from s3 bucket')
        return "{}/{}".format(LOCAL_FILE, filename)
    except botocore.exceptions.ClientError as e:
        return source_file_download(filename, url)


def source_file_download(filename, url):

    print("Downloading source file from website")
    s3 = boto3.client('s3')
    # print(page.getcode())
    page = urlopen(url)
    f = open("{}/{}".format(LOCAL_FILE, filename), "wb")
    shutil.copyfileobj(page, f)
    f.close()
    empty_bucket(os.environ['BUCKET'])
    try:
        print('Saving to s3 bucket - {}'.format(os.environ['BUCKET']))
        s3.upload_file("{}/{}".format(LOCAL_FILE, filename), os.environ['BUCKET'], filename)
    except botocore.exceptions.ClientError as e:
        print("Couldn't upload to s3 {}/{}". format(os.environ['BUCKET'], filename))
    return "{}/{}".format(LOCAL_FILE, filename)


def source_file_process(tmp_file, target):

    print('Case type is {}.'.format(define_excel_sheet(target)))
    sheet_num = define_excel_sheet(target)
    df = pd.read_excel(tmp_file, sheet_name=sheet_num, index_col=0, skiprows=6, names=['a','b'])
    print('Looking for {}'.format(target))
    # print(df.head())
    df = df[df['b'].notnull()]
    search = df['b'].str.contains(target)
    df = df.loc[search]
    if  df.empty:
        answer = "Unfortunately your record {} was not found :-(".format(target)
    else:
        value = df.to_string(index=False, header=False)
        answer = "Record(s) \n {}\nwas found in MOI status file".format(value)
    return answer


def send_reply(a, chat_id):

    tlg_endpoint = "https://api.telegram.org/bot{}/sendMessage".format(os.environ['TOKEN'])
    post_fields = {'chat_id': chat_id, 'text': a}
    request = Request(tlg_endpoint, urlencode(post_fields).encode())
    json = urlopen(request).read().decode()
    return json


def main(target, chat_id):

    filename, url = source_file_url()
    path = source_file_S3(filename, url)
    answer = source_file_process(path, target)
    print(answer)
    send_reply(answer, chat_id)


def lambda_handler(event, context):
    print(event)
    if event['update_id'] > read_update_id():
        save_update_id(int(event['update_id']))
        chat_id = event['message']['chat']['id']
        target = event['message']['text'].upper()
        print('Checking format')
        if check_format(target):
            print('Format OK. Starting...')
            main(target, chat_id)
        else:
            return send_reply(FORMAT_MSG, chat_id)
    else:
        print('This is already processed')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="case number we are checking",
                    type=str)
    parser.add_argument("chat_id", help="telegram chat_id to send reply",
                    type=str)
    args = parser.parse_args()
    if check_format(args.target.upper()):
        main(args.target.upper(), args.chat_id)
    else:
        print(FORMAT_MSG)

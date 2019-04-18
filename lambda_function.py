
import os
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
import logging

FORMAT_MSG = """
    Format seems to be incorrect.
    Example: If receipt number of your application is OAM-0334-5/PP-2015,
    then you will search for OAM-334/PP-2015.
    Found result will be as follows: OAM-334/PP-2015.
"""
LOCAL_FILE = "/tmp"

lvl = os.environ['LOGLEVEL']

def logger_init():
    ''' Setting up logger basic config or logger set level depending on where this code is running.
    In ot outside main function. Considering outside main means code is running on aws lambda '''
    is_main = __name__ == "__main__"
    print(is_main)
    if lvl == 'INFO':
        logging.basicConfig(level=logging.INFO) if is_main else logger.setLevel(logging.INFO)
    elif lvl == 'DEBUG':
        logging.basicConfig(level=logging.DEBUG) if is_main else logger.setLevel(logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARN) if is_main else logger.setLevel(logging.WARN)

def save_update_id(update_id, table_name):
    ''' saves update id from telegramm payload to dynamodb table, returns response from dynamodb '''
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    response = table.update_item(
        Key={
            'id': '1'
        },
        UpdateExpression='SET update_id = :val1',
        ExpressionAttributeValues={
            ':val1': update_id
        }
    )
    return response


def read_update_id(table_name):
    ''' reads update is of latest processed telegramm request, returns update id value '''
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    response = table.get_item(
        Key={
            'id': '1',
        }
    )
    return response['Item']['update_id']


def to_ordinal_num(n):
    ''' a helper  function that coverts day of month to ordinal value 1st,2nd,3d etc '''
    return str(n) + {1: 'st', 2: 'nd', 3: 'rd'}.get(4 if 10 <= n % 100 < 20 else n % 10, "th")


def define_excel_sheet(case_num):
    ''' defines correct source excel sheet index based on application number part, returns  excel sheet index '''
    case_types = {
    'DP': 0,
    'PP': 0,
    'DV': 0,
    'ZM': 1,
    'TP': 2
    }
    case_type = case_num.split('/')[1].split('-')[0]
    return case_types[case_type]


def check_format(case_num):
    ''' check input of application number to match required format regexp, returns boolean value '''
    pattern = re.compile('^OAM-[^0]\d+/(DP|PP|DV|ZM|TP)-\d{4}$')
    return bool(pattern.match(case_num))


def empty_bucket(bucket_name):
    ''' removes all files  from tmp s3 bucket, returns  True if bucket is empty, False if exeption was caught '''
    logger.info('Clean up in bucket {}'.format(bucket_name))
    s3 = boto3.resource('s3')
    try:
        bucket = s3.Bucket(bucket_name)
        bucket.objects.all().delete()
        logger.info('Bucket {} clean.'.format(bucket_name))
        return True
    except botocore.exceptions.ClientError as e:
        logger.info('Bucket was not cleaned. With error: {}'.format(e))
        return False


def source_file_url():
    ''' Takes current date to compile a source file url and checks for hhtp headed
        if 404 takes previous day and repeat. Returns valis url, and filename from hypermedia header '''
    revert_days = 0
    month = datetime.datetime.today().strftime("%B").lower()
    year = datetime.datetime.today().strftime("%Y")

    while True:
        day = to_ordinal_num(int(datetime.datetime.today().strftime("%d"))-revert_days)
        url = "https://www.mvcr.cz/mvcren/file/list-valid-to-the-{}-{}-{}.aspx".format(month,day,year)
        logger.info(url)
        try:
            head = urlopen(Request(url, method='HEAD'))
            logger.info('Success: HTTP 200 OK')
            return head.info()['Content-Disposition'].split('=')[1].strip('"'), url
        except HTTPError as e:
            logger.info('{}'.format(e))
            logger.info('Checking previous day')
            revert_days += 1

def source_file_download(filename, url, bucket_name):
    ''' Accepts filename, url and  s3 bucket name to store
        Gets  fileobject from url and saves it to /tmp/{filename} on disk.
        Empties s3 bucket and saves downloaded file.
        Returns file path'''
    logger.info("Downloading source file from website")
    s3 = boto3.client('s3')
    # logger.info(page.getcode())
    page = urlopen(url)
    f = open("{}/{}".format(LOCAL_FILE, filename), "wb")
    shutil.copyfileobj(page, f)
    f.close()
    empty_bucket(bucket_name)
    try:
        logger.info('Saving to s3 bucket - {}'.format(bucket_name))
        s3.upload_file("{}/{}".format(LOCAL_FILE, filename), bucket_name, filename)
    except botocore.exceptions.ClientError as e:
        logger.info("Couldn't upload to s3 {}/{}". format(bucket_name, filename))
    return "{}/{}".format(LOCAL_FILE, filename)


def source_file_S3(filename, url, bucket_name):
    ''' Tries to get filename from s3 and save it to tmp
        If success returns local path
        If failure downlodas  file from web'''
    s3 = boto3.resource('s3')
    try:
        s3.Bucket(bucket_name).download_file(filename, "{}/{}".format(LOCAL_FILE, filename))
        logger.info('File taken from s3 bucket {}'.format(bucket_name))
        return "{}/{}".format(LOCAL_FILE, filename)
    except botocore.exceptions.ClientError as e:
        return source_file_download(filename, url, bucket_name)




def source_file_process(tmp_file, target):
    ''' Uses  pandas to find target in tmp_file defining excel sheet in beetween
        Returns reply message  '''
    logger.info('Case type is {}.'.format(define_excel_sheet(target)))
    sheet_num = define_excel_sheet(target)
    df = pd.read_excel(tmp_file, sheet_name=sheet_num, index_col=0, skiprows=6, names=['a','b'])
    logger.info('Looking for {}'.format(target))
    # logger.info(df.head())
    df = df[df['b'].notnull()]
    search = df['b'].str.contains(target)
    df = df.loc[search]
    date = tmp_file.split('.')[0].split('_')[2]
    if  df.empty:
        answer = "Unfortunately your record {} was not found in file from {} :-(".format(target, date)
    else:
        value = df.to_string(index=False, header=False)
        answer = "Record(s) \n {}\nwas found in MOI status file from {}".format(value,date)
    return answer


def send_reply(a, chat_id, token):
    ''' Sends reply via telegram to accepted chat_id
        Returns telegram api reply json'''
    logger.info('Sending reply to {}'.format(chat_id))
    tlg_endpoint = "https://api.telegram.org/bot{}/sendMessage".format(token)
    post_fields = {'chat_id': chat_id, 'text': a}
    request = Request(tlg_endpoint, urlencode(post_fields).encode())
    json = urlopen(request).read().decode()
    logger.info('TLG answered {}'.format(json))
    return json


def main(target, chat_id):
    ''' main sequence of application '''
    logger.warning('Logging set to {}'.format(lvl))
    token = os.environ['TOKEN']
    bucket_name = os.environ['BUCKET']

    filename, url = source_file_url()
    path = source_file_S3(filename, url, bucket_name)
    answer = source_file_process(path, target)
    print(answer)
    # send reply to telegram only on lambda run
    if __name__ != "__main__":
        send_reply(answer, chat_id, token)


def lambda_handler(event, context):
    ''' this function is entrypoint for aws lambda function
        calling function main which wraps the main sequence
        Update_id check is needed if you are not returning OK 200 to telegram api.
        If telegram gets ok 200 it removes message from queue, otherwise message lives  about 24 hours
        In this case  you need to track update id to avoid multiple processing of same messages.
        NOTE. THis code won't work if  you set up aws api gateway from lamda,
        in this case it uses proxy and event parameter structure changes
        TODO. process both event structures.
    '''
    table_name = os.environ['DB_TABLE_NAME']
    logger.info(event)
    if event['update_id'] > read_update_id(table_name):
        save_update_id(int(event['update_id']), table_name)
        chat_id = event['message']['chat']['id']
        target = event['message']['text'].upper()
        logger.info('Checking format')
        if check_format(target):
            logger.info('Format OK. Starting...')
            main(target, chat_id)
        else:
            return send_reply(FORMAT_MSG, chat_id)
    else:
        logger.info('This is already processed')


if __name__ == "__main__":

    # setting up logger for local run
    logger_init()
    logger = logging.getLogger()

    # parsing args
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="case number we are checking",
                    type=str)
    parser.add_argument("chat_id", help="telegram chat_id to send reply",
                    type=str)
    args = parser.parse_args()

    if check_format(args.target.upper()):
        print('Looking for {}'.format(args.target))
        main(args.target.upper(), args.chat_id)
    else:
        print(FORMAT_MSG)
else:
    # setting up logger for lambda
    logger = logging.getLogger()
    logger_init()

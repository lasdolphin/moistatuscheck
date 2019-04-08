
import os
import json
import boto3
import re
import argparse
import pandas as pd
import urllib.request
from urllib.parse import urlencode
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
LOCAL_FILE = "/tmp/tmp.xls"

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

def get_source_file(tmp_file):

    revert_days = 0
    month = datetime.datetime.today().strftime("%B").lower()
    year = datetime.datetime.today().strftime("%Y")

    while True:
        day = toOrdinalNum(int(datetime.datetime.today().strftime("%d"))-revert_days)
        url = "https://www.mvcr.cz/mvcren/file/list-valid-to-the-{}-{}-{}.aspx".format(month,day,year)
        # print(url)
        try:
            page = urllib.request.urlopen(url)
            break
        except urllib.error.HTTPError as e:
            revert_days += 1
    # print(page.getcode())
    f = open("{}".format(tmp_file), "wb")
    shutil.copyfileobj(page, f)
    f.close()

def process_source_file(tmp_file, target):

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
    request = urllib.request.Request(tlg_endpoint, urlencode(post_fields).encode())
    json = urllib.request.urlopen(request).read().decode()
    return json

def main(target, chat_id):

    get_source_file(LOCAL_FILE)
    answer = process_source_file(LOCAL_FILE, target)
    print(answer)
    send_reply(answer, chat_id)



def lambda_handler(event, context):
    print(event)
    if event['update_id'] > read_update_id():
        save_update_id(int(event['update_id']))
        chat_id = event['message']['chat']['id']
        target = event['message']['text'].upper()
        print('checking format')
        if check_format(target):
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

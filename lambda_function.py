
import os
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

LOCAL_FILE = "/tmp/tmp.xls"

def toOrdinalNum(n):

    return str(n) + {1: 'st', 2: 'nd', 3: 'rd'}.get(4 if 10 <= n % 100 < 20 else n % 10, "th")

def define_excel_sheet(case_num):
    case_type = case_num.split('/')[1].split('-')[0]
    return case_types[case_type]

def get_source_file(tmp_file):

    revert_days = 0
    month = datetime.datetime.today().strftime("%B").lower()
    year = datetime.datetime.today().strftime("%Y")

    while True:
        day = toOrdinalNum(int(datetime.datetime.today().strftime("%d"))-revert_days)
        url = "https://www.mvcr.cz/mvcren/file/list-valid-to-the-{}-{}-{}.aspx".format(month,day,year)
        print(url)
        try:
            page = urllib.request.urlopen(url)
            break
        except urllib.error.HTTPError as e:
            revert_days += 1
    print(page.getcode())
    f = open("{}".format(tmp_file), "wb")
    shutil.copyfileobj(page, f)
    f.close()

def process_source_file(tmp_file):

    print('Case type is {}.'.format(define_excel_sheet(os.environ['TARGET'])))
    sheet_num = define_excel_sheet(os.environ['TARGET'])
    df = pd.read_excel(tmp_file, sheet_name=sheet_num, index_col=0, skiprows=6, names=['a','b'])
    print('Looking for {}'.format(os.environ['TARGET']))
    print(df.head())
    df = df[df['b'].notnull()]
    search = df['b'].str.contains(os.environ['TARGET'])
    df = df.loc[search]
    if  df.empty:
        answer = "Unfortunately your record was not found :-("
    else:
        value = df.to_string(index=False, header=False)
        answer = "Record(s) \n {}\nwas found in MOI status file".format(value)
    return answer

def send_reply(a):
    tlg_endpoint = "https://api.telegram.org/bot{}/sendMessage".format(os.environ['TOKEN'])
    post_fields = {'chat_id': os.environ['CHAT_ID'], 'text': a}
    request = urllib.request.Request(tlg_endpoint, urlencode(post_fields).encode())
    json = urllib.request.urlopen(request).read().decode()
    return json

def main():

    get_source_file(LOCAL_FILE)
    answer = process_source_file(LOCAL_FILE)
    print(answer)
    print(send_reply(answer))


def lambda_handler(event, context):
    main()

if __name__ == "__main__":
    main()

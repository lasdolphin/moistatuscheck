
import os
import pandas as pd
import urllib.request
from urllib.parse import urlencode
import datetime
import shutil


# TODO
# 1. add functionality to pick up correct sheet.
# 3. read excel on the fly
# 5. reverse date picking
# schedule check in lambda
# add bot command to assept case number
# add deployment pipeline on commit
#x 4. send result to telegram
#x 2. Interpret filter result


LOCAL_FILE = "/tmp/tmp.xls"

def toOrdinalNum(n):

    return str(n) + {1: 'st', 2: 'nd', 3: 'rd'}.get(4 if 10 <= n % 100 < 20 else n % 10, "th")

def main():

    month = datetime.datetime.today().strftime("%B").lower()
    # -2 is temporary tp mach apr1
    day = toOrdinalNum(int(datetime.datetime.today().strftime("%d"))-2)
    year = datetime.datetime.today().strftime("%Y")
    url = "https://www.mvcr.cz/mvcren/file/list-valid-to-the-{}-{}-{}.aspx".format(month,day,year)

    page = urllib.request.urlopen(url)
    print(page)
    f = open("{}".format(LOCAL_FILE), "wb")
    shutil.copyfileobj(page, f)
    f.close()

    df = pd.read_excel(LOCAL_FILE, sheet_name=1, index_col=0, skiprows=6, names=['a','b'])
    df = df[df['b'].notnull()]
    search = df['b'].str.contains(os.environ['TARGET'])
    df = df.loc[search]
    if  df.empty:
        answer = "Unfortunately your record was not found :-("
    else:
        value = df.to_string(index=False, header=False)
        answer = "Record(s) \n {}\nwas found in MOI status file".format(value)

    print(answer)

    tlg_endpoint = "https://api.telegram.org/bot{}/sendMessage".format(os.environ['TOKEN'])
    post_fields = {'chat_id': os.environ['CHAT_ID'], 'text': answer}
    request = urllib.request.Request(tlg_endpoint, urlencode(post_fields).encode())
    json = urllib.request.urlopen(request).read().decode()
    print(json)

def lambda_handler(event, context):
    main()

if __name__ == "__main__":
    main()

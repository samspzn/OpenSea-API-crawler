"""
針對OpenSea API-Retrieve events 解析結構，每完成50筆會累計存成一個檔案，到最後一筆會再生成一個檔案。
抓專案契約地址 -> events_api = "https://api.opensea.io/api/v1/events?asset_contract_address="+ wallet_address + "&event_type=" + event_type + "&cursor=" + next_param
抓錢包地址 -> events_api = "https://api.opensea.io/api/v1/events?account_address="+ wallet_address + "&event_type=" + event_type + "&cursor=" + next_param
"""
import json
import requests
import numpy as np
import pandas as pd
import datetime
import os
import threading
import time
import s3fs

# 讀取檔案裡的錢包/專案契約地址，檔案裡是放錢包地址。
# @TODO: move this to __main__ ?
opensea_totaladdress = os.path.join(os.getcwd(), 'coolcatsnft_補跑清單0513.xlsx')
input_account_addresses = pd.read_excel(opensea_totaladdress)["token_owner_address"].array

api_v1 = "https://api.opensea.io/api/v1"
test_v1 = "https://testnets-api.opensea.io/api/v1/"


def retrieve_events(api_key=None, **query_params):
    """
    OpenSea Retrieve Events wrapper

    :param api_key: an OpenSea API Key. If not defined, call testnets-api.
    :param query_params: param_key=string_value, e.g. only_opensea="True"
    :return: dict representation of Response JSON object
    """
    headers = {"X-API-KEY": api_key}

    if api_key is None:
        events_api = test_v1 + "/events"
    else:
        events_api = api_v1 + "/events"

    if query_params:
        events_api += "?"
        while query_params:
            param, value = query_params.popitem()
            events_api = events_api + param + '=' + value
            if query_params:
                events_api += "&"

    response = requests.get(events_api, headers=headers)

    if not response.ok:
        response.raise_for_status()

    return response


def parse_events(events, page_num, wallet_address):
    """
    Parse a dictionary representation of Response JSON object into a list of events. Each item in the list is a
    dictionary representation of an asset event.

    Parameters
    ----------
    events : a dictionary containing a collection of Event objects
    page_num
    wallet_address

    Returns
    -------
    event_list
        a list of dictionaries of each event
    """
    events_list = []

    if "asset_events" in events.keys():

        for event in events["asset_events"]:
            data = {}

            if event["asset"]:
                data["num_sales"] = event["asset"]["num_sales"]
                data["token_id"] = event["asset"]["token_id"]
                if event["asset"]["owner"]:
                    data["token_owner_address"] = event["asset"]["owner"]["address"]
                else:
                    data["token_owner_address"] = event["asset"]["owner"]

            if event["asset_bundle"]:
                data["asset_bundle"] = event["asset_bundle"]

            data["event_timestamp"] = event["event_timestamp"]
            data["event_type"] = event["event_type"]

            data["listing_time"] = event["listing_time"]

            if event["seller"]:
                data["token_seller_address"] = event["seller"]["address"]
            if event["winner_account"]:
                data["token_winner_address"] = event["winner_account"]["address"]

            if event["total_price"]:
                data["deal_price"] = int(event["total_price"])

            if event["payment_token"]:
                data["payment_token_symbol"] = event["payment_token"]["symbol"]
                data["payment_token_decimals"] = event["payment_token"]["decimals"]
                data["payment_token_usdprice"] = np.float64(event["payment_token"]["usd_price"])

            data["quantity"] = event["quantity"]
            data["starting_price"] = event["starting_price"]
            data["ending_price"] = event["ending_price"]
            data["approved_account"] = event["approved_account"]
            data["auction_type"] = event["auction_type"]
            data["bid_amount"] = event["bid_amount"]

            if event["transaction"]:
                data["transaction_hash"] = event["transaction"]["transaction_hash"]
                data["block_hash"] = event["transaction"]["block_hash"]
                data["block_number"] = event["transaction"]["block_number"]

            data["collection_slug"] = event["collection_slug"]
            data["is_private"] = event["is_private"]
            data["duration"] = event["duration"]
            data["created_date"] = event["created_date"]

            data["contract_address"] = event["contract_address"]

            data["wallet_address_input"] = wallet_address
            data["pages"] = page_num
            data["msg"] = "success"  # @TODO: remove this; recording only error stat sufficient?
            data["next_param"] = events["next"]

            events_list.append(data)
    else:
        # @TODO: except KeyError
        data = {"wallet_address_input": wallet_address,
                "pages": page_num,
                "msg": "Fail-no asset_events",
                "next_param": events.get("next", "")}
        events_list.append(data)

        raise KeyError("wallet: " + wallet_address + " no asset_events!")

    return events_list


def process_run(range_run, account_addresses, data_lis, api_key, event_type, thread_n, next_param="", page_num=0):
    """
    Retrieve asset events via OpenSea API based on a list of account addresses specified by 'range_run'
    values, i.e. index of the list

    @TODO: not sure if thread_n is really needed here

    :param range_run:
    :param account_addresses:
    :param data_lis:
    :param api_key:
    :param event_type: see OpenSea API doc, e.g. "successful", "transfer", etc.
    :param thread_n:
    :param next_param:
    :param page_num:

    :return: status code: "success" or "fail"
    """
    # @TODO why global scope?
    global data_lista
    global data_listb
    status = "success"

    for m in range_run:
        wallet_address = account_addresses[m]

        try:
            next_page = True
            while next_page:
                events = retrieve_events(api_key,
                                         event_type=event_type,
                                         cursor=next_param,
                                         account_address=wallet_address).json()

                # save each response JSON as a separate file
                output_dir = os.path.join(os.getcwd(), 'data', 'asset_events', wallet_address)
                # save to aws
                # output_dir = 's3://nftfomo/asset_events/' + wallet_address
                save_response_json(events, output_dir, page_num)

                e_list = parse_events(events, page_num, wallet_address)
                for event in e_list:
                    data_lis.append(event)

                # @TODO: for DEBUGGING, remember to comment out or implement logging to speed up production
                print("wallet: " + wallet_address + ", pages: "
                      + str(page_num) + ", "
                      + event["event_timestamp"])

                next_param = events["next"]
                if next_param is not None:
                    page_num += 1
                else:
                    next_param = ""
                    next_page = False

                # @TODO: for DEBUGGING, run max 2 pages. Remember to comment or remove before production
                # if page_num == 2:
                #     next_page = False
        except requests.exceptions.RequestException as e:
            print(repr(e))
            # @TODO: better workaround when 429 Client Error: Too Many Requests for url
            if e.response.status_code == 429:
                msg = "Response [{0}]: {1}".format(e.response.status_code, e.response.reason)
                data = {"wallet_address_input": wallet_address,
                        "pages": page_num,
                        "msg": msg,
                        "next_param": next_param}
                data_lis.append(data)
                time.sleep(6) # @TODO: make the sleep time adjustable?

            # 記錄運行至檔案的哪一筆中斷與當前的cursor參數(next_param)
            rerun_range = range(m, range_run[-1] + 1)
            if (thread_n % 2) == 0:
                data_lista.append((rerun_range, next_param, page_num))
            else:
                data_listb.append((rerun_range, next_param, page_num))
            status = "fail"
        # @TODO: remove this catch all Exception
        except Exception as e:
            print(repr(e.args))
            msg = "SOMETHING WRONG"
            data = {"wallet_address_input": wallet_address,
                    "pages": page_num,
                    "msg": msg,
                    "next_param": next_param}
            data_lis.append(data)

            if m == range_run[-1] + 1:
                status = "success"
            else:
                # 記錄運行至檔案的哪一筆中斷與當前的cursor參數(next_param)
                rerun_range = range(m, range_run[-1] + 1)
                if (thread_n % 2) == 0:
                    data_lista.append((rerun_range, next_param, page_num))
                else:
                    data_listb.append((rerun_range, next_param, page_num))
                status = "fail"

        # 存檔，自己取名
        # output a file for every 50 account addresses processes or one file if less than 50 addresses total
        if (int(m) % 50 == 0 and int(m) > 0) or m == range_run[-1]:
            fn = "coolcatsnft_{0}_{1}.xlsx".format(thread_n, m)
            pd.DataFrame(data_lis) \
                .reset_index(drop=True)\
                .to_excel(os.path.join(os.getcwd(), 'data', 'asset_events', fn), encoding="utf_8_sig")

    return status


def save_response_json(events, output_dir, page_num):
    """
    If output_dir begins with `s3://`, save the events JSON to AWS s3,
    else save to the specified local directory.

    Parameters
    ----------
    events
    output_dir
    page_num

    Returns
    -------

    """
    if output_dir.startswith('s3://'):
        output_dir.removeprefix('s3://')
        s3 = s3fs.S3FileSystem(anon=False)
        rpath = output_dir + '/' + str(page_num) + '.json'
        with s3.open(rpath, 'w') as f:
            json.dump(events, fp=f)
    else:
        # create a subdirectory to save response json object
        if not os.path.isdir(os.path.join(output_dir)):
            os.makedirs(output_dir)

        with open(os.path.join(output_dir, str(page_num) + '.json'), 'w') as f:
            json.dump(events, fp=f)


def controlfunc(process_run, range_run, addresses, data_lis, api_key, event_type, thread_n, next_param=""):
    # process_run的外層函數，當執行中斷時自動繼續往下執行
    global data_lista
    global data_listb

    s_f = process_run(range_run, addresses, data_lis, api_key, event_type, thread_n, next_param)

    rerun = True
    rerun_count = 0

    while rerun:
        if s_f == "success":
            rerun = False
            print("finished!!!!")
        else:
            if (thread_n % 2) == 0:
                if data_lista:
                    range1_rerun, nxt, pg = data_lista.pop()
                    print("Rerun1 is preparing " + str(rerun_count))
                    s_f = process_run(range1_rerun, addresses, data_lis, api_key, event_type, thread_n, nxt, pg)
                    rerun_count += 1
            else:
                if data_listb:
                    range2_rerun, nxt, pg = data_listb.pop()
                    print("Rerun2 is preparing " + str(rerun_count))
                    s_f = process_run(range2_rerun, addresses, data_lis, api_key, event_type, thread_n, nxt, pg)
                    rerun_count += 1
            if rerun_count > 50:  # @TODO: parameterize this instead of hard coding
                rerun = False
                print("abort: too many errors!!!")  # @TODO: save whatever have retrieved so far


# 將檔案裡的數量分拆
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


if __name__ == '__main__':
    '''
    以下變數需手動設置，此程式預設調用兩個API，分別分配給兩個執行序來平行抓取處理。
    event_type : 設定要抓取的事件(created, successful, cancelled, bid_entered, bid_withdrawn, transfer, offer_entered, approve)
    chunk_size : 要用多少筆數來切總列數(檔案)
    range_s : 執行首序列號
    range_e : 執行末序列號
    EX. range(0,60) --> range_s=0 , range_e=60 , divide = 30

    api_key = opensea api key1
    api_key2 = opensea api key2
    '''
    event_type = "successful"
    chunk_size = 1
    range_s = 0
    range_e = 2

    # read API keys from file
    # each line in file is a key value pair separated by `=`
    #   key=key_value
    secrets = {}
    with open(os.path.join(os.getcwd(), 'OpenSea.key')) as f:
        for line in f:
            (k, v) = line.rstrip().split('=')
            secrets[k] = v
    api_key1 = secrets['api_key1']
    api_key2 = secrets['api_key2']

    data_lista = []
    data_listb = []
    range_collection = list(chunks(range(range_s, range_e), chunk_size))
    thread_n = len(range_collection)

    start = str(datetime.datetime.now())
    for n in range(thread_n):
        globals()["datalist%s" % n] = []

        # distribute keys among threads
        if (n % 2) == 0:
            key_ = api_key1
        else:
            key_ = api_key2

        # @TODO: Is there a better way to manage the return value,
        # i.e. Do we really need to pass in globals()["datalist%s" % n]?
        globals()["add_thread%s" % n] = threading.Thread(target=controlfunc, args=(
            process_run, range_collection[n], input_account_addresses, globals()["datalist%s" % n], key_,
            event_type, n))
        globals()["add_thread%s" % n].start()

    for nn in range(thread_n):
        globals()["add_thread%s" % nn].join()

    print("Start :" + start)
    print("End   :" + str(datetime.datetime.now()))

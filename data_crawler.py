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
import pathlib
from os.path import isfile, join
import threading
import time

# 讀取檔案裡的錢包/專案契約地址，檔案裡是放錢包地址。
# @TODO: move this to __main__ ?
opensea_totaladdress = os.path.join(os.getcwd(), 'coolcatsnft_補跑清單0513.xlsx')
input_account_addresses = pd.read_excel(opensea_totaladdress)["token_owner_address"].array

api_v1 = "https://api.opensea.io/api/v1"


def retrieve_events(api_key, **query_params):
    """
    OpenSea Retrieve Events wrapper

    :param api_key: an OpenSea API Key
    :param query_params: param_key=string_value, e.g. only_opensea="True"
    :return: dict representation of Response JSON object
    """
    headers = {"X-API-KEY": api_key}

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


def process_run(range_run, account_addresses, data_lis, api_key, event_type, thread_n, next_param, page_num=0):
    """
    Retrieve asset events via OpenSea API based on a list of account addresses specified by 'range_run'
    values, i.e. index of the list

    @TODO: not sure if thread_n is really needed here

    :param range_run:
    :param account_addresses:
    :param data_lis:
    :param api_key:
    :param event_type:
    :param thread_n:
    :param next_param:
    :param page_num:

    :return: status code: "success" or "fail"
    """
    # @TODO why global scope?
    global data_lists
    global data_lista
    global data_listb
    global data_list0
    global data_list1
    status = "success"

    for m in range_run:

        wallet_address = account_addresses[m]
        nextpage = True

        # create a subdirectory to save response json object
        output_dir = os.path.join(os.getcwd(), 'extracts', wallet_address)
        if not os.path.isdir(os.path.join(output_dir)):
            os.makedirs(output_dir)

        try:
            while nextpage:

                events = retrieve_events(api_key,
                                         event_type=event_type,
                                         cursor=next_param,
                                         account_address=wallet_address).json()

                with open(os.path.join(output_dir, str(page_num) + '.json'), 'w') as f:
                    json.dump(events, fp=f)

                if "asset_events" in events.keys():

                    asset_events = events["asset_events"]
                    for event in asset_events:

                        if event["asset"]:
                            num_sales = event["asset"]["num_sales"]
                            token_id = event["asset"]["token_id"]
                            if event["asset"]["owner"]:
                                token_owner_address = event["asset"]["owner"]["address"]
                            else:
                                token_owner_address = event["asset"]["owner"]
                        else:
                            num_sales = ""
                            token_id = ""
                            token_owner_address = ""

                        if event["asset_bundle"]:
                            asset_bundle = event["asset_bundle"]
                        else:
                            asset_bundle = ""

                        event_timestamp = event["event_timestamp"]
                        event_type = event["event_type"]

                        listing_time = event["listing_time"]

                        if event["seller"]:
                            token_seller_address = event["seller"]["address"]
                        else:
                            token_seller_address = ""

                        if event["total_price"]:
                            deal_price = int(event["total_price"])
                        else:
                            deal_price = ""

                        if event["payment_token"]:
                            payment_token_symbol = event["payment_token"]["symbol"]
                            payment_token_decimals = event["payment_token"]["decimals"]
                            payment_token_usdprice = np.float64(event["payment_token"]["usd_price"])
                        else:
                            payment_token_symbol = event["payment_token"]
                            payment_token_decimals = event["payment_token"]
                            payment_token_usdprice = event["payment_token"]

                        quantity = event["quantity"]
                        starting_price = event["starting_price"]
                        ending_price = event["ending_price"]
                        approved_account = event["approved_account"]
                        auction_type = event["auction_type"]
                        bid_amount = event["bid_amount"]

                        if event["transaction"]:
                            transaction_hash = event["transaction"]["transaction_hash"]
                            block_hash = event["transaction"]["block_hash"]
                            block_number = event["transaction"]["block_number"]
                        else:
                            transaction_hash = ""
                            block_hash = ""
                            block_number = ""

                        collection_slug = event["collection_slug"]
                        is_private = event["is_private"]
                        duration = event["duration"]
                        created_date = event["created_date"]

                        contract_address = event["contract_address"]

                        # @TODO: change this to dict
                        data = [event_timestamp, event_type, token_id, num_sales, listing_time, token_owner_address,
                                token_seller_address, deal_price,
                                payment_token_symbol, payment_token_decimals, payment_token_usdprice, quantity,
                                starting_price, ending_price, approved_account,
                                asset_bundle, auction_type, bid_amount, transaction_hash, block_hash, block_number,
                                is_private, duration, created_date, collection_slug, contract_address,
                                wallet_address, page_num, "success", next_param]

                        data_lis.append(data)
                        data_lists.append(data)
                        print("wallet: " + str(m) + " , pages: " + str(page_num) + ", " + event_timestamp)

                else:
                    # @TODO: except KeyError
                    data = ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
                            "", "", "", "", "", "", "", "", "", "", "", wallet_address, page_num,
                            "Fail-no asset_events", next_param]
                    data_lis.append(data)
                    data_lists.append(data)

                    print(str(m) + " no asset_events!")
                    nextpage = False

                # @TODO: fix next_param not stored with the right page
                next_param = events["next"]
                if next_param is not None:
                    page_num += 1
                else:
                    next_param = ""
                    nextpage = False

                # for debugging
                # @TODO: remember to comment or remove for production
                # if page_num == 2:
                #     nextpage = False

        except requests.exceptions.RequestException as e:
            print(repr(e))
            # @TODO: bugfix 429 Client Error: Too Many Requests for url
            # if e.response.status_code == 429:
            #     time.sleep(60)
            msg = "Response [{0}]: {1}".format(e.response.status_code, e.response.reason)
            data = ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
                    "", "", "", "", "", "", "", "", "", "", "", wallet_address, page_num, msg, next_param]
            data_lis.append(data)
            data_lists.append(data)
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
            data = ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
                    "", "", "", "", "", "", "", "", "", "", "", wallet_address, page_num, "SOMETHING WRONG",
                    next_param]

            data_lis.append(data)
            data_lists.append(data)

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
        col = ["event_timestamp", "event_type", "token_id", "num_sales", "listing_time", "token_owner_address",
               "token_seller_address", "deal_price",
               "payment_token_symbol", "payment_token_decimals", "payment_token_usdprice", "quantity", "starting_price",
               "ending_price", "approved_account",
               "asset_bundle", "auction_type", "bid_amount", "transaction_hash", "block_hash", "block_number",
               "is_private", "duration", "created_date", "collection_slug", "contract_address", "wallet_address_input",
               "pages", "msg", "next_param"]
        # output a file for every 50 account addresses processes or one file if less than 50 addresses total
        if (int(m) % 50 == 0 and int(m) > 0) or m == range_run[-1]:
            if (thread_n % 2) == 0:
                result_dfa = pd.DataFrame(data_lis, columns=col)
                result_dfa = result_dfa.reset_index(drop=True)
                result_dfa.to_excel(os.path.join(os.getcwd(), 'extracts', "coolcatsnft_0_" + str(m) + ".xlsx"),
                                    encoding="utf_8_sig")
            else:
                result_dfb = pd.DataFrame(data_lis, columns=col)
                result_dfb = result_dfb.reset_index(drop=True)
                result_dfb.to_excel(os.path.join(os.getcwd(), 'extracts', "coolcatsnft_1_" + str(m) + ".xlsx"),
                                    encoding="utf_8_sig")

    return status


def controlfunc(process_run, range_run, addresses, data_lis, api_key, event_type, thread_n, next_param):
    # process_run的外層函數，當執行中斷時自動繼續往下執行
    global data_lista
    global data_listb
    global data_list0
    global data_list1

    s_f = process_run(range_run, addresses, data_lis, api_key, event_type, thread_n, next_param)

    rerun = True
    count = 0

    while rerun:
        if s_f == "success":
            rerun = False
            print("finished!!!!")
        else:
            if (thread_n % 2) == 0:
                if data_lista:
                    range1_rerun, nxt, pg = data_lista.pop()
                    print("Rerun1 is preparing " + str(count))
                    s_f = process_run(range1_rerun, addresses, data_lis, api_key, event_type, thread_n, nxt, pg)
                    count += 1
            else:
                if data_listb:
                    range2_rerun, nxt, pg = data_listb.pop()
                    print("Rerun2 is preparing " + str(count))
                    s_f = process_run(range2_rerun, addresses, data_lis, api_key, event_type, thread_n, nxt, pg)
                    count += 1
            if count > 1000:
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

    data_lists = []
    data_lista = []
    data_listb = []
    range_collection = list(chunks(range(range_s, range_e), chunk_size))
    thread = len(range_collection)

    start = str(datetime.datetime.now())
    for n in range(thread):
        globals()["datalist%s" % n] = []
        if (n % 2) == 0:
            globals()["add_thread%s" % n] = threading.Thread(target=controlfunc, args=(
                process_run, range_collection[n], input_account_addresses, globals()["datalist%s" % n], api_key1,
                event_type, n, ""))
            globals()["add_thread%s" % n].start()
        else:
            globals()["add_thread%s" % n] = threading.Thread(target=controlfunc, args=(
                process_run, range_collection[n], input_account_addresses, globals()["datalist%s" % n], api_key2,
                event_type, n, ""))
            globals()["add_thread%s" % n].start()

    for nn in range(thread):
        globals()["add_thread%s" % nn].join()

    print("Start :" + start)
    print("End   : " + str(datetime.datetime.now()))

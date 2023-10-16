from .utils.web3_crawler import Web3Crawler, make_web3_ipc_provider
from enum import Enum
import logging
import time
import traceback
from .utils.eth_env import Transfer_Event_Topic, BOT_WALLET, IPC_PATH
from .utils.common import transfer_filter_with_map, transfer_filter, make_native_coin_transfer, make_copy_input
from .utils.contracts import convert_token_amount_to_matic_amount
from .utils.debug_trace_call import make_debug_request_and_decode_parse
from web3.types import TxData
from typing import Dict
from eth_account import Account


class Color(Enum):
    BLACK = '\33[30m'
    RED = '\33[31m'
    GREEN = '\33[32m'
    YELLOW = '\33[33m'
    BLUE = '\33[34m'
    PURPLE = '\33[35m'
    DEEPGREEN = '\33[36m'
    WHITE = '\33[37m'
    RESET = '\33[0m'


logging.basicConfig(level=logging.WARNING, filename='copy_bot.log', filemode='w',
                    format=f"{Color.YELLOW.value}%(filename)s %(funcName)s line {Color.RED.value}%(lineno)d {Color.YELLOW.value}%(asctime)s {Color.PURPLE.value}%(levelname)s {Color.DEEPGREEN.value}%(message)s {Color.RESET.value}",
                    datefmt='%m-%d %H:%M:%S'
                    )


with open('.secret', 'r') as env:
    SK = env.readline().strip().replace("sk=", "")


def process_transaction(w3, tx, tx_receipt):
    # 收集所有日志 -> 换算 -> 从金额中分析获利者 -> 对获利者进行input推断， 如果没有， 考虑msg.sender
    # -> 模拟执行 -> （收集所有日志 -> 换算 -> 从金额中分析获利者 -> 判断获利金额） -> 发送交易

    # 转账交易直接跳过
    if tx['input'] == '0x' or tx['input'] == '':
        return

    token_transfers = []

    if tx['value'] > 0:
        dic = make_native_coin_transfer(tx['from'], tx['to'], tx['value'])
        token_transfers.append(dic)
    if tx_receipt:
        if tx_receipt['status'] != 1:
            return

        for log in tx_receipt.logs:
            logging.debug('tx: ' + tx['hash'].hex() + ' logs parsing...')
            token_transfer = transfer_filter_with_map(w3, log)
            if token_transfer:
                token_transfers.append(token_transfer)

        # DEBUG
        # if tx['blockNumber'] == 15259356:
        #     exit(1)

        token_account_change = parse_token_transfers(token_transfers)

        # logging.info(repr(token_account_change))

        CheckSumAddress = str
        account_matic_dict: Dict[CheckSumAddress, int] = {}
        for addr in token_account_change:
            token_amount_dict = token_account_change[addr]
            matic_amount = 0
            for token in token_amount_dict:
                # 如果是非归档节点，只能在最近的区块进行eth_call
                # amount = convert_token_amount_to_matic_amount(w3, token, token_amount_dict[token], tx['blockNumber'])
                amount = convert_token_amount_to_matic_amount(w3, token, token_amount_dict[token], 'latest')
                if amount:
                    matic_amount += amount
            account_matic_dict[addr] = matic_amount

        N = 3
        gainers = find_gainer(account_matic_dict, N)

        profit_wallet = BOT_WALLET
        for item in gainers:
            address = item[0]
            profit = item[1]
            input_hexstr = tx['input']
            input = make_copy_input(input_hexstr, address, profit_wallet)
            if not input:
                if tx['from'] == address:
                    input = input_hexstr
            if input:
                logging.info("Found Profit TX: " + repr(tx['hash'].hex()) + ' profit: ' + str(profit))
                fake_tx, profit = simulate_and_seek_profit(w3, tx, input, profit_wallet)
                if not profit:
                    logging.info("Simulate Failed.")
                elif profit <= 0:
                    logging.info("Simulate Not Profit TX: " + repr(tx['hash'].hex()) + ' profit: ' + str(profit) + ' addr: ' + address)
                else:
                    logging.warning("Simulate Profit TX: " + repr(tx['hash'].hex()) + ' profit: ' + str(profit) + ' addr: ' + address)
                    # tx_hash = make_real_tx(w3, fake_tx, SK)
                    # profit = seek_profit_after_real_tx(w3, tx_hash, profit_wallet)
                    # if profit > 0:
                    #     logging.warning("Real Profit TX Made: " + repr(tx_hash) + ' profit: ' + str(profit))
                    # if profit <= 0:
                    #     logging.warning("Real Profit TX Made: " + repr(tx_hash) + ' profit: ' + str(profit))
            else:
                continue
    else:
        pass


def find_gainer(account_matic_dict, return_nums):
    gainer_items = sorted(account_matic_dict.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    gainer_items = list(filter(lambda x: x[1] > 1 * 10 ** 18, gainer_items[:return_nums]))
    logging.debug('gainer item: ' + repr(gainer_items))
    if gainer_items != []:
        logging.info('gainer item: ' + repr(gainer_items))
    return gainer_items


def parse_token_transfers(token_transfers):
    Address = str
    Token = str
    token_account_change: Dict[Address, Dict[Token, int]] = {}
    for i in token_transfers:
        from_dict = token_account_change.get(i['from'], {})
        from_amount = from_dict.get(i['token'], 0)
        from_amount -= i['amount']
        from_dict[i['token']] = from_amount
        token_account_change[i['from']] = from_dict

        to_dict = token_account_change.get(i['to'], {})
        to_amount = to_dict.get(i['token'], 0)
        to_amount += i['amount']
        to_dict[i['token']] = to_amount
        token_account_change[i['to']] = to_dict

    return token_account_change


def simulate_and_seek_profit(w3, tx, new_input, wallet):
    if tx['type'] == '0x2':
        fake_tx = {
            "from": wallet,
            "to": tx["to"],
            "data": new_input,
            "gas": hex(tx["gas"]),
            "maxFeePerGas": hex(tx['maxFeePerGas']),
            "maxPriorityFeePerGas": hex(tx['maxPriorityFeePerGas']),
            # "gasPrice": hex(tx["gasPrice"]),
            "value": hex(tx["value"])
        }
    else:
        fake_tx = {
            "from": wallet,
            "to": tx["to"],
            "data": new_input,
            "gas": hex(tx["gas"]),
            "gasPrice": hex(tx["gasPrice"]),
            "value": hex(tx["value"])
        }

    token_transfers = make_debug_request_and_decode_parse(IPC_PATH, fake_tx, block_number='latest', log_filter=transfer_filter_with_map)

    if token_transfers:

        if tx['value'] > 0:
            # logging.info(repr(fake_tx))
            dic = make_native_coin_transfer(wallet, tx['to'], tx['value'])
            token_transfers.append(dic)

        token_account_change = parse_token_transfers(token_transfers)
        CheckSumAddress = str
        account_matic_dict: Dict[CheckSumAddress, int] = {}
        for addr in token_account_change:
            token_amount_dict = token_account_change[addr]
            matic_amount = 0
            for token in token_amount_dict:
                # 如果是非归档节点，只能在最近的区块进行eth_call
                # amount = convert_token_amount_to_matic_amount(w3, token, token_amount_dict[token], tx['blockNumber'])
                amount = convert_token_amount_to_matic_amount(w3, token, token_amount_dict[token], 'latest')
                if amount:
                    matic_amount += amount
            account_matic_dict[addr] = matic_amount
        return fake_tx, account_matic_dict.get(wallet, 0)
    else:
        return fake_tx, None


def make_real_tx(w3, tx, sk) -> str:
    account: Account = Account.from_key(sk)
    if 'maxFeePerGas' in tx:
        real_tx = {
            "from": tx['from'],
            "to": tx['to'],
            "data": tx['data'],
            "gas": int(tx['gas'], 16),
            "maxFeePerGas": tx['maxFeePerGas'],
            "maxPriorityFeePerGas": tx['maxPriorityFeePerGas'],
            # "gasPrice": int(tx['gasPrice'], 16),
            "value": int(tx['value'], 16)
        }
    else:
        real_tx = {
            "from": tx['from'],
            "to": tx['to'],
            "data": tx['data'],
            "gas": int(tx['gas'], 16),
            "gasPrice": int(tx['gasPrice'], 16),
            "value": int(tx['value'], 16)
        }
    signed_tx = account.sign_transaction(real_tx)
    return w3.eth.send_raw_transaction(signed_tx.rawTransaction).hex()


def loop_run(interval: int = 60, default_num: int = 1, delay_blocks: int = 0):
    crawler = Web3Crawler(IPC_PATH)  # /data/matic/.bor/data/bor.ipc

    while True:
        db_max_num = default_num
        index_max_num = crawler.get_block_height() - delay_blocks
        logging.debug("block height: {}".format(index_max_num))
        if index_max_num <= db_max_num:
            time.sleep(interval)
            continue
        i = db_max_num
        while i <= index_max_num:
            logging.debug("crawling block: {}".format(i))
            if i % 1000 == 0:
                logging.warning("crawling block: {}".format(i))
            block, tx_list = crawler.crawl_block(i, True)
            full_tx_list = []
            for tx in tx_list:
                logging.debug("crawling tx_receipt: {}".format(tx['hash'].hex()))
                rc = crawler.crawl_transaction_receipt(tx['hash'].hex())
                process_transaction(crawler.w3, tx, rc)
            i += 1
        time.sleep(interval)


def seek_profit_after_real_tx(w3, tx_hash, wallet) -> int:
    receipt = w3.eth.get_transaction_receipt(tx_hash)
    tx = w3.eth.get_transaction(tx_hash)
    if receipt and receipt['status'] != 1:
        logging.warning("Real TX Reverted: " + repr(tx_hash))
        return 0
    else:
        token_transfers = []

        if tx['value'] > 0:
            dic = make_native_coin_transfer(tx['from'], tx['to'], tx['value'])
            token_transfers.append(dic)
        if receipt:
            if receipt['status'] != 1:
                return

            for log in receipt.logs:
                token_transfer = transfer_filter_with_map(w3, log)
                if token_transfer:
                    token_transfers.append(token_transfer)

            token_account_change = parse_token_transfers(token_transfers)

            CheckSumAddress = str
            account_matic_dict: Dict[CheckSumAddress, int] = {}
            for addr in token_account_change:
                token_amount_dict = token_account_change[addr]
                matic_amount = 0
                for token in token_amount_dict:
                    # 如果是非归档节点，只能在最近的区块进行eth_call
                    # amount = convert_token_amount_to_matic_amount(w3, token, token_amount_dict[token], receipt['blockNumber'])
                    amount = convert_token_amount_to_matic_amount(w3, token, token_amount_dict[token], 'latest')
                    if amount:
                        matic_amount += amount
                account_matic_dict[addr] = matic_amount
            return account_matic_dict.get(wallet, 0)


def product_run(num):
    logging.warning('new indexer')

    # cProfile.run('loop_run_with_swap(interval=10)', 'restats')

    try:
        loop_run(interval=10, default_num=num)
    except:
        logging.error("--------------------------------------------------------------------------------")
        logging.error("indexer failed.")
        s = traceback.format_exc()
        logging.error(s)
        logging.error("--------------------------------------------------------------------------------")
        cnt = 1
        while cnt < 100:
            logging.warning("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            logging.warning("After 3 min, will restart.")
            time.sleep(3 * 60)
            logging.warning("Restart...")
            logging.warning("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            try:
                loop_run(interval=10, default_num=num)
            except:
                logging.error("--------------------------------------------------------------------------------")
                logging.error("indexer failed.")
                s = traceback.format_exc()
                logging.error(s)
                logging.error("--------------------------------------------------------------------------------")
            finally:
                cnt += 1


if __name__ == '__main__':
    # loop_run(interval=10, default_num=0x1e72ead)
    product_run(15445900)
    # loop_run(interval=10, default_num=15259350)


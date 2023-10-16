from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.middleware import geth_poa_middleware
from eth_utils import to_bytes, to_hex
from typing import List, Optional, Union
from web3.types import BlockData, TxData, ENS
from .eth_env import IPC_PATH
import logging


def make_web3_ipc_provider(path=IPC_PATH):
    w3 = Web3(Web3.IPCProvider(path))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    if w3.isConnected():
        return w3
    else:
        logging.error("web3 connected false.")
        return w3


class Web3Crawler():
    def __init__(self, path=IPC_PATH):
        # path = '/data/polygon/.bor/bor.ipc'
        self.w3 = Web3(Web3.IPCProvider(path))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        print("web3 connect:", self.w3.isConnected())

    def process_block(self, block):
        pass

    def process_transaction(self, tx):
        pass

    def crawl_blocks(self, block_num_list: List[int], with_transactions: bool = True):
        block_list: List[BlockData] = []
        tx_list: List[TxData] = []
        for block_num in block_num_list:
            block: BlockData = self.w3.eth.get_block(block_num, full_transactions=with_transactions)
            self.process_block(block)
            block_list.append(block)
            if with_transactions:
                tx_list.extend(block.transactions)
        return block_list, tx_list

    def crawl_block(self, block_num, with_transactions: bool = True):
        tx_list: List[TxData] = []
        block: BlockData = self.w3.eth.get_block(block_num, full_transactions=with_transactions)
        self.process_block(block)
        if with_transactions:
            tx_list.extend(block.transactions)
        return block, tx_list

    def crawl_transaction_receipt(self, transaction_hash):
        try:
            return self.w3.eth.get_transaction_receipt(transaction_hash)
        except TransactionNotFound as err:
            print(err)
            return None

    def get_block_height(self) -> int:
        return self.w3.eth.get_block_number()


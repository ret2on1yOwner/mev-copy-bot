import logging
import traceback
from .eth_env import Transfer_Event_Topic
from typing import Dict, Optional
from web3.types import HexBytes
from .eth_env import POLY_WMATIC_ADDR


def transfer_filter(log):
    """
    给定log日志， 判断是否是Transfer
    :param log日志， 类型是Dict， Web3.types
    :return: 是否是Transfer, Bool
    """
    if len(log['topics']) > 0 and log['topics'][0] == Transfer_Event_Topic:
        return True
    else:
        return False


def transfer_filter_with_map(w3, log) -> Optional[Dict]:
    """
    给定log日志， 判断是否是Transfer， 如果是， 则进行Transfer的转换
    :param log日志， 类型是Dict， Web3.types
    :return: 如果为空， 说明不是Trasnfer， Transfer的字典包括key值 token， from， to， amount
    """
    if len(log['topics']) == 3 and isinstance(log['topics'][0], HexBytes) and log['topics'][0].hex() == Transfer_Event_Topic and log['data'] != '0x':
        dic = {'token': w3.toChecksumAddress(log['address']), 'from': w3.toChecksumAddress(log['topics'][1].hex()[-40:]),
               'to': w3.toChecksumAddress(log['topics'][2].hex()[-40:]),
               'amount': int(log['data'][2:], 16)}
        return dic
    elif len(log['topics']) == 3 and isinstance(log['topics'][0], str) and (log['topics'][0] == Transfer_Event_Topic) and log['data'] != '0x':
            dic = {'token': w3.toChecksumAddress(log['address']), 'from': w3.toChecksumAddress(log['topics'][1][-40:]),
                   'to': w3.toChecksumAddress(log['topics'][2][-40:]),
                   'amount': int(log['data'][2:], 16)}
            return dic
    else:
        return None


def make_native_coin_transfer(from_address, to_address, value):
    dic = {'token': POLY_WMATIC_ADDR, 'from': from_address, 'to': to_address,
           'amount': value}
    return dic


def make_copy_input(input, address, copy_address):
    # input = input.replace('0x', '')
    address = address.replace('0x', '').lower()
    copy_address = copy_address.replace('0x', '').lower()
    if address in input:
        input.replace(address, copy_address)
        return input
    return None


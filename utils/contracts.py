import json
from .eth_env import *
from typing import Optional
from .price_oracle import get_amount_out_v3, get_amount_out_v2
import logging


def get_pair(w3, token0, token1, fee=None) -> str:
    # with open('./UniswapV2Pair.json', 'r') as f:
    #     abi = f.read()
    if fee:
        abi = json.loads(UNIV3_FACTORY_ABI)
        contract = w3.eth.contract(address=POLY_UNIV3_FACTORY_ADDR, abi=abi)
        pair = contract.functions.getPool(token0, token1, fee).call()
    else:
        abi = json.loads(UNIV2_FACTORY_ABI)
        contract = w3.eth.contract(address=POLY_SUSHI_FACTORY_ADDR, abi=abi)
        pair = contract.functions.getPair(token0, token1).call()

    return pair


def get_pool_from_v2(w3, token0, token1) -> Optional[str]:
    abi = json.loads(UNIV2_FACTORY_ABI)
    contract = w3.eth.contract(address=POLY_SUSHI_FACTORY_ADDR, abi=abi)
    pair = contract.functions.getPair(token0, token1).call()
    if pair == '0x0000000000000000000000000000000000000000':
        return None
    return pair


def get_pool_from_v3(w3, token0, token1, fee) -> Optional[str]:
    abi = json.loads(UNIV3_FACTORY_ABI)
    contract = w3.eth.contract(address=POLY_UNIV3_FACTORY_ADDR, abi=abi)
    pair = contract.functions.getPool(token0, token1, fee).call()
    if pair == '0x0000000000000000000000000000000000000000':
        return None
    return pair


def detect_pool(w3, token):
    """
    TODO: 目前只做BASIC_COIN的捕捉
    :param w3: web3 provider
    :param token: str, checksum token address, start with '0x'
    :return: Tuple[type, pool_address], type [0 : Native Coin, 2: v2 Change, 3: v3 Change]
    """
    BASIC_COIN = [POLY_WMATIC_ADDR, POLY_WETH_ADDR, POLY_USDT_ADDR, POLY_USDC_ADDR, POLY_DAI_ADDR, POLY_WBTC_ADDR]

    if token == BASIC_COIN[0]:
        return 0, None
    elif token in BASIC_COIN:
        return 1, get_pool_from_v2(w3, token0=POLY_WMATIC_ADDR, token1=token)
    else:
        return -1, None


def get_reserves(w3, pair_address, block_num):
    abi = json.loads(UNIV2_PAIR_ABI)
    contract = w3.eth.contract(address=pair_address, abi=abi)
    reserve0, reserve1, _ = contract.functions.getReserves().call(block_identifier=block_num)
    return reserve0, reserve1


def get_reverse_in_and_out(reserve0, reserve1, token_address, token_out):
    if token_address.lower() < token_out.lower():
        return reserve0, reserve1
    elif token_address.lower() > token_out.lower():
        return reserve1, reserve0
    else:
        # unlikely
        assert False, "same token address."


def convert_token_amount_to_matic_amount(w3, token, token_amount, block_num) -> Optional[int]:
    type_num, pair_address = detect_pool(w3, token=token)
    if type_num == 0:
        return token_amount
    else:
        if not pair_address:
            return None
        else:
            reserve0, reserve1 = get_reserves(w3, pair_address, block_num)
            reserve_in, reserve_out = get_reverse_in_and_out(reserve0, reserve1, token, POLY_WMATIC_ADDR)
            amount_out = get_amount_out_v2(token_amount, reserve_in, reserve_out)
            return amount_out

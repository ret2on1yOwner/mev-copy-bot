import time
from .eth_env import POLY_UNIV3_ROUTER_ADDR, UNIV3_ROUTER_ABI
from .web3_crawler import make_web3_ipc_provider
import json

univ3_router_abi = json.loads(UNIV3_ROUTER_ABI)
w3 = make_web3_ipc_provider()
univ3_router = w3.eth.contract(address=POLY_UNIV3_ROUTER_ADDR, abi=univ3_router_abi)


def get_deadline(duration):
    """
    Given the period of validity, returns the deadline timestamp
    :param duration: The seconds of the period of validity.
    :return: The deadline timestamp in seconds.
    """
    return round(time.time()) + duration


def get_amount_out_v3(token_in, token_out, fee, amount_in_wei, account) -> int:
    contract_params = {
        'tokenIn': token_in,
        'tokenOut': token_out,
        'fee': fee,
        'recipient': account,
        'deadline': get_deadline(600),
        'amountIn': round(amount_in_wei),
        'amountOutMinimum': 0,
        'sqrtPriceLimitX96': 0,
    }
    # print('contract_params', contract_params)
    amount_out_wei = univ3_router.functions.exactInputSingle(contract_params).call({'from': account})
    return amount_out_wei


def get_amount_out_v2(amount_in, reserve_in, reserve_out):
    """
    Given an input asset amount, returns the maximum output amount of the
    other asset (accounting for fees) given reserves.
    :param amount_in: Amount of input asset.
    :param reserve_in: Reserve of input asset in the pair contract.
    :param reserve_out: Reserve of input asset in the pair contract.
    :return: Maximum amount of output asset.
    """
    # assert amount_in >= 0
    assert reserve_in > 0 and reserve_out > 0
    amount_in_with_fee = amount_in * 997
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in * 1000 + amount_in_with_fee
    return int(numerator / denominator)


import logging
import traceback
from threading import Thread
from time import time
import asyncio
import ujson

from web3.eth import AsyncEth

from web3 import Web3
from websockets import connect
from typing import cast

from web3.providers.ipc import IPCProvider
from web3.providers import WebsocketProvider
from web3.providers.base import BaseProvider
from web3.types import RPCResponse


def _fast_decode_rpc_response(raw_response: bytes) -> RPCResponse:
    decoded = ujson.loads(raw_response)
    return cast(RPCResponse, decoded)


def patch_provider(provider: BaseProvider):
    """Monkey-patch web3.py provider for faster JSON decoding.
    Call this on your provider after construction.
    This greatly improves JSON-RPC API access speeds, when fetching
    multiple and large responses.
    """
    provider.decode_rpc_response = _fast_decode_rpc_response


tracer = '''
{
    data: [],
    fault: function (log) {
    },
    step: function (log) {
        var topicCount = (log.op.toString().match(/LOG(\d)/) || [])[1];
        if (topicCount) {
            var res = {
                address: log.contract.getAddress(),
                data: log.memory.slice(parseInt(log.stack.peek(0)), parseInt(log.stack.peek(0)) + parseInt(log.stack.peek(1))),
                topics : [ ]
            };
            for (var i = 0; i < topicCount; i++)
                res['topics'].push(log.stack.peek(i + 2));
            this.data.push(res);
        }
    },
    result: function (ctx,db ) {
        return [this.data,ctx.block];
    }
}'''


def decode_debug_response(logs: list) -> list:
    events = []
    blocknumber = logs[1]

    for log in logs[0]:

        address = '0x'
        data = '0x'
        topics = []
        event = {
            'address': address,
            'blockHash': '0x',
            'blockNumber': blocknumber,
            'data': data,
            'logIndex': 0,
            'payload': '0x',
            'removed': False,
            'topic': '0x',
            'topics': topics,
            'transactionHash': '0x',
            'transactionIndex': 0
        }

        for key, value in log.items():
            if key == 'address':
                address_raw = log['address']
                for i, key in address_raw.items():
                    address = address + format(key, 'x').zfill(2)

            if key == 'data':
                data_raw = log['data']
                for i, key in data_raw.items():
                    data = data + format(key, 'x').zfill(2)

            if key == 'topics':
                topics = list(map(lambda x: '0x' + format(int(x), 'x').zfill(64), log['topics']))

        event['address'] = address
        event['data'] = data
        event['topics'] = topics
        events.append(event)
    return events


def make_debug_request(provider: BaseProvider, method: str, params: list):
    """Make a JSON-RPC request to the given provider.
    method: 'debug_traceCall' or 'debug_traceTransaction' ,
    params: txid or eth_call dict,
    tracer: '<string>',
    timeout: '<duration>'
    """

    return provider.make_request(method, params)


start_time = time()


async def subscribe(path, params, callback):
    async with connect(path) as ws:
        print(params)
        await ws.send(ujson.dumps({"id": 1, "method": "eth_subscribe", "params": params}))
        subscription_response = await ws.recv()

        print(subscription_response)

        while True:
            try:
                # t = time()
                message = await asyncio.wait_for(ws.recv(), timeout=60)
                # print(message)
                message = ujson.loads(message)
                task = asyncio.create_task(callback(message))

            except Exception as e:
                print(e)
                continue


def make_debug_request_and_decode_parse(path, tx, block_number, log_filter):
    provider = IPCProvider(path)
    patch_provider(provider)
    web3 = Web3(provider)

    def pt_with_thread(message):
        t = Thread(target=pt, args=(message,))
        t.start()

    # t = time()
    events_logs = []

    try:

        # m = message

        # txhash = m['params']['result']

        # tx = w3.eth.get_transaction(txhash)

        # fake_tx = {
        #     "from": tx["from"],
        #     "to": tx["to"],
        #     "data": tx["input"],
        #     "gas": hex(tx["gas"]),
        #     "gasPrice": hex(tx["gasPrice"]),
        #     "value": hex(tx["value"])
        # }

        method = 'debug_traceCall'
        params = [
            tx,
            block_number,  # "latest",
            {"tracer": tracer}
        ]

        res = make_debug_request(provider, method, params)

        # print(time()-t)
        if 'result' in res:
            events = decode_debug_response(res['result'])
            logging.debug('events0: ' + repr(events))
            for e in events:
                result = log_filter(web3, e)
                if result:
                    events_logs.append(result)
            logging.debug('events after filter: ' + repr(events_logs))
            return events_logs

        else:
            if 'error' in res and res['error']['code'] == -32000:
                logging.info(res)
                return None
            logging.warning("No Events Found.")
            logging.warning(res)
            # raise Exception(res)
            return None

    except Exception as e:
        s = traceback.format_exc()
        logging.error(s)
        return None



if __name__ == '__main__':

    path = 'ws://124.160.125.204:28657'  # 测试网络
    path = 'ws://3.130.50.208:8546'  # bsc

    sync_topic_hash = '0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1'
    provider = WebsocketProvider(path)

    import sys

    if len(sys.argv) < 2:
        print('Usage: python main.py <ipc_path or ws_path>')
        print('Lack of provider path, using default ', path)
    else:
        if path.startswith('ws'):
            provider = WebsocketProvider(path)
        else:
            provider = IPCProvider(path)

    patch_provider(provider)  # 是用ujson解析

    w3 = Web3(provider)

    # if w3.isConnected():
    #    print('Connected to', w3.clientVersion)
    #    print("The network is", w3.eth.chain_id)
    #    print("Blcokhead now is",w3.eth.block_number)

    events_logs = []


    def pt_with_thread(message):
        t = Thread(target=pt, args=(message,))
        t.start()


    async def pt(message):
        # t = time()

        try:
            m = message

            txhash = m['params']['result']

            tx = w3.eth.get_transaction(txhash)

            # print(time()-t)

            fake_tx = {
                "from": tx["from"],
                "to": tx["to"],
                "data": tx["input"],
                "gas": hex(tx["gas"]),
                "gasPrice": hex(tx["gasPrice"]),
                "value": hex(tx["value"])
            }

            method = 'debug_traceCall'
            params = [
                fake_tx,
                "latest",
                {"tracer": tracer}
            ]

            res = make_debug_request(provider, method, params)

            # print(time()-t)
            if 'result' in res:
                events = decode_debug_response(res['result'])
                for e in events:
                    if (e['topics'][0] == sync_topic_hash):
                        print(e)
                        print(txhash)
                        events_logs.append([e, txhash])

            else:
                # print(res)
                # print(time() - t)
                raise Exception(res)

        except Exception as e:
            print(e)


    # "newHeads", "logs", "newPendingTransactions", "syncing"

    loop = provider._loop

    asyncio.run(subscribe(path, ["newPendingTransactions"], pt))
    with open('events.json', 'w') as f:
        ujson.dump(events_logs, f)

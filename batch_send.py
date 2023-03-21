#!/usr/bin/env python3
import json
import os
import pprint

import dotenv
from eth_abi import encode_abi
from eth_utils import to_checksum_address, to_wei, to_hex, from_wei

import lib.abi_lib
from lib.gas_estimator import gas_estimator
import web3
from secure_web3 import sw3
import argparse

abi = lib.abi_lib.batch_abi


"""
Gas usage:
Recipients per batch: 
10: 13,714 gas per transfer
20: 11,523 gas per transfer
60: 9961.1 gas per transfer
100: 9648.8 gas per transfer
"""


class BatchSender:
    def __init__(self, w3, contract_address: str, private_key: (str, hex), batch_size: int = 80):
        self.batch_size = batch_size
        self.account = web3.Account.from_key(private_key)
        self.web3 = w3
        self.contract = self.web3.eth.contract(
            address=to_checksum_address(contract_address), abi=abi)
        self.value = 0
        self.calls = []
        # self.data = []

    def divide_chunks(self, l: list, n: int):
        """
        Split a list
        :param l: list
        :param n: batch size
        :return: generator
        """
        batches = []
        # looping till length l
        for i in range(0, len(l), n):
            batches.append(l[i:i + n])
        return batches

    def send(self):
        if len(self.calls):
            if len(self.calls) > self.batch_size:
                calls = self.calls.copy()
                call_batches = self.divide_chunks(calls, self.batch_size)
                for x, batch in enumerate(call_batches):
                    self.calls = batch
                    return self._send()
            else:
                return self._send()
        return False

    def _send(self):
        """
        const tx = {
          data: this.contract.methods.batchSend(targets, values, datas).encodeABI(),
          to: this.contract.options.address,
          value
        }
        return this.web3.eth.sendTransaction(tx, callback)
        :return:
        """

        max_priority_fee_per_gas, max_fee_per_gas, _est = gas_estimator(self.web3, to_checksum_address(
            self.contract.address), to_checksum_address(self.account.address),
                                                                        from_wei(self.value, 'ether'), 'LOW', )
        # gas = self.contract.functions.batchSend(self.targets, self.values, self.datas).estimateGas()
        raw_txn = {
            "from": to_checksum_address(self.account.address),
            "gas": 5000000,
            'maxPriorityFeePerGas': to_wei(max_priority_fee_per_gas, 'gwei'),
            'maxFeePerGas': to_wei(max_fee_per_gas, 'gwei'),
            "to": to_checksum_address(self.contract.address),
            "value": self.value,
            "data": self.contract.encodeABI('batchCall', args={'calls': self.calls}),
            "nonce": self.web3.eth.get_transaction_count(to_checksum_address(self.account.address)),
            "chainId": self.web3.eth.chain_id
        }
        pprint.pprint(raw_txn)
        signed_txn = self.web3.eth.account.signTransaction(raw_txn, self.account.key)
        try:
            ret = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        except ValueError as err:
            print(f'[!] Error sending: {err}')
        else:
            hextx = to_hex(ret)

            self.reset()
            return hextx
        return False

    def call(self, dest, value, data):
        return encode_abi(['address', 'uint256', 'bytes'], [dest, value, data])

    def add_call(self, _recipient: str, raw_amount: int, data: bytes = b""):
        """
        Abi encodes a call and appends it to the queue.
        :param _recipient: string or checsum address
        :param raw_amount: int wei quantity for message value
        :param data: arbitrary data for call
        """
        self.calls.append(self.call(to_checksum_address(_recipient), raw_amount, data))
        self.value += raw_amount

    def reset(self):
        """
        Clear the pending call queue.
        """
        self.calls = []
        self.value = 0


if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('-w', '--wallet', type=str, default='keys/default_wallet.json', help='Path to JSON wallet file.')
    args.add_argument('-n', '--network', type=str, default='goerli', choices=['ethereum', 'arbitrum', 'goerli'],
                      help='EVM chain to connect to.')
    args.add_argument('-f', '--file', type=str, help='List of: `address,amount` : one per line.')
    args.add_argument('-t', '--targets', type=str, nargs='+', help='Specify targets on CLI.')
    args.add_argument('-b', '--batch_size', type=int, default=20, help='Max txs per batch.')
    args.add_argument('-q', '--quantity', type=float, default=0, help='Quantity of Ether to send to recipients.')
    args = args.parse_args()
    dotenv.load_dotenv()
    if os.path.exists(args.wallet):
        sw3 = sw3.WalletManager(args.wallet)
    else:
        print('[!] Please specify --wallet')
        exit(1)
    endpoint = os.environ.get(f'{args.network}_http_endpoint')
    contract_address = os.environ.get(f'{args.network}_batcher_contract_address')
    if not endpoint or not contract_address:
        print('[!] Please ensure that your .env file is properly configured. (See docs). ')
        exit(1)
    w3 = web3.Web3(web3.HTTPProvider(endpoint))

    # privkey = '0x97c10b5c18a24a69e171a58df71a69a1d43ed3845cc5983e03162231088c0da6'
    privkey, config = sw3.decrypt_load_wallet()
    batcher = BatchSender(w3, contract_address, privkey, args.batch_size)
    # print(batcher.contract.functions.__dict__)
    inputs = []
    if args.file:
        with open(args.file, 'r') as f:
            f = f.readlines()
            for line in f:
                line = line.strip('\r\n').split(',')
                print(line)
                if len(line) == 1:
                    qty = args.quantity
                else:
                    qty = float(line[1])
                recipient = line[0]
                print(f'[+] Encoding call to {recipient} for {qty} ETH ... ')
                batcher.add_call(recipient, to_wei(qty, 'ether'))
    if args.targets:
        for recipient in args.targets:
            print(f'[+] Encoding call to {recipient} for {args.quantity} ETH ... ')
            batcher.add_call(recipient, to_wei(args.quantity, 'ether'))

    print(f'[+] Transaction will execute  {len(batcher.calls)} internal calls.')
    ret = batcher.send()
    print(f'Result: {ret}')

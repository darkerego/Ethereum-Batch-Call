#!/usr/bin/env python3
import json
import math
import os
import pprint

import dotenv
import eth_abi
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address, to_wei, to_hex, from_wei

import web3
import argparse
# PLEASE GO THROUGH THE README.md FILE BEFORE RUNNING THE CODE ##

# import Web3 class from web3 module
import decimal

from eth_utils import to_wei, from_wei

from lib.abi_lib import EIP20_ABI
from web3 import Web3, HTTPProvider
# import the in-built statistics module
import statistics




def gas_estimator(web3, from_account, to_account, eth_value, priority='low', contract_address=None):
    
    if priority == 'polygon':
        priority = 'high'
        poly_fix = True
    else:
        poly_fix = False
    basefee_percentage_multiplier = {
        "low": 1.10,  # 10% increase
        "medium": 1.20,  # 20% increase
        "high": 1.25  # 25% increase
    }

    priority_fee_percentage_multiplier = {
        "low": .94,  # 6% decrease
        "medium": .97,  # 3% decrease
        "high": .98  # 2% decrease
    }

    # the minimum PRIORITY FEE that should be payed,
    #  corresponding to the user priority (in WEI denomination)
    minimum_fee = {
        "low": 10000000,
        "medium": 15000000,
        "high": 20000000

    }

    #  a dictionary for storing the sorted priority fee
    fee_by_priority = {
        "low": [],
        "medium": [],
        "high": []
    }


    w3 = web3


    fee_history = w3.eth.fee_history(5, 'latest', [10, 20, 30])
    latest_base_fee_per_gas = fee_history["baseFeePerGas"][-1]
    if contract_address is None:
        estimate_gas_used = w3.eth.estimate_gas(
            {'to': to_account, 'from': from_account,
             'value': to_wei(int(eth_value), "ether")})
    else:

        _abi = EIP20_ABI
        unicorns = web3.eth.contract(address=contract_address, abi=_abi)
        estimate_gas_used = unicorns.functions.transfer(to_account, int(eth_value)).estimate_gas(
            {'from': from_account})
        #estimate_gasUsed = w3.eth.estimate_gas(
    for feeList in fee_history["reward"]:
        # 10 percentile values - low fees
        fee_by_priority["low"].append(feeList[0])
        # 20 percentile value - medium fees
        fee_by_priority["medium"].append(feeList[1])
        # 30 percentile value - high fees
        fee_by_priority["high"].append(feeList[2])

    # Take each of the sorted arrays in the feeByPriority dictatory and
    # calculate the gas estimate, based on the priority level
    # which is given as the key in the feeByPriority dictatory
    for key in fee_by_priority:
        # adjust the basefee,
        # use the multiplier value corresponding to the key
        adjusted_base_fee = latest_base_fee_per_gas * basefee_percentage_multiplier[key]

        # get the median of the priority fee based on the key
        median_of_fee_list = statistics.median(fee_by_priority[key])

        # adjust the median value,
        # use the multiplier value corresponding to the key
        adjusted_fee_median = (
                median_of_fee_list * priority_fee_percentage_multiplier[key])

        # if the adjusted_fee_median falls below the MINIMUM_FEE,
        # use the MINIMUM_FEE value,
        adjusted_fee_median = adjusted_fee_median if adjusted_fee_median > minimum_fee[
            key] else minimum_fee[key]

        suggested_max_priority_fee_per_gas_gwei = from_wei(adjusted_fee_median, "gwei")
        if poly_fix:
            suggested_max_priority_fee_per_gas_gwei = suggested_max_priority_fee_per_gas_gwei * 5
        # [optional] round the amount
        suggested_max_priority_fee_per_gas_gwei = round(
            suggested_max_priority_fee_per_gas_gwei, 5)
        # calculate the Max fee per gas
        suggested_max_fee_per_gas = (adjusted_base_fee + adjusted_fee_median)
        # convert to gwei denomination
        suggested_max_fee_per_gas_gwei = from_wei(suggested_max_fee_per_gas, "gwei")
        if poly_fix:
            suggested_max_fee_per_gas_gwei = suggested_max_fee_per_gas_gwei * 3
        # [optional] round the amount to the given decimal precision
        suggested_max_fee_per_gas_gwei = round(suggested_max_fee_per_gas_gwei, 9)
        # calculate the total gas fee
        total_gas_fee = suggested_max_fee_per_gas_gwei * estimate_gas_used
        # convert the value to gwei denomination
        total_gas_fee_gwei = from_wei(total_gas_fee, "gwei")
        # [optional] round the amount
        total_gas_fee_gwei = round(total_gas_fee_gwei, 8)
        pr = f"PRIORITY: {key.upper()}\nMAX PRIORITY FEE (GWEI): {suggested_max_priority_fee_per_gas_gwei}"
        pr += f"\nMAX FEE (GWEI) : {suggested_max_fee_per_gas_gwei}\nGAS PRICE (ETH): {total_gas_fee_gwei}, wei: {total_gas_fee}"
        print(pr)
        print("=" * 80)  # guess what this does ?

        if key.upper() == priority.upper():
            # print()
            return suggested_max_priority_fee_per_gas_gwei, suggested_max_fee_per_gas_gwei, total_gas_fee






"""
Gas usage:
Recipients per batch: 
10: 13,714 gas per transfer
20: 11,523 gas per transfer
60: 9961.1 gas per transfer
100: 9648.8 gas per transfer
"""
batcher_abi = json.loads('''[
	{
		"inputs": [
			{
				"internalType": "bytes[]",
				"name": "_calls",
				"type": "bytes[]"
			}
		],
		"name": "batchArbitraryCalls",
		"outputs": [],
		"stateMutability": "payable",
		"type": "function"
	},
	{
		"inputs": [],
		"stateMutability": "nonpayable",
		"type": "constructor"
	}
]''')

class BatchSender:
    def __init__(self, w3: web3.Web3, contract_address: str|ChecksumAddress, private_key: str | hex , batch_size: int = 80):
        self.batch_size = batch_size
        self.account = web3.Account.from_key(private_key)
        self.web3: web3.Web3 = w3
        self.contract = self.web3.eth.contract(
            address=to_checksum_address(contract_address), abi=batcher_abi)
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
            # "gas": 5000000,
            'maxPriorityFeePerGas': to_wei(max_priority_fee_per_gas, 'gwei'),
            'maxFeePerGas': to_wei(max_fee_per_gas, 'gwei'),
            "to": to_checksum_address(self.contract.address),
            "value": self.value,
            "data": self.contract.encode_abi('batchCalls', args=(self.calls, )),
            "nonce": self.web3.eth.get_transaction_count(to_checksum_address(self.account.address)),
            "chainId": self.web3.eth.chain_id
        }
        eth_est = self.web3.eth.estimate_gas(raw_txn)
        raw_txn.update({'gas': int(math.ceil(eth_est*1.01))})
        pprint.pprint(raw_txn)
        if hasattr(self.web3, 'signTransaction'):
            signed_txn = self.web3.eth.account.signTransaction(raw_txn, self.account.key)
        else:
            signed_txn = self.web3.eth.account.sign_transaction(raw_txn, self.account.key)
        try:
            ret = self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        except ValueError as err:
            print(f'[!] Error sending: {err}')
        else:
            hextx = to_hex(ret)

            self.reset()
            return hextx
        return False

    def call(self, dest, value, data):
        return eth_abi.encode(['address', 'uint256', 'bytes'], [dest, value, data])

    def add_call(self, _recipient: str, raw_amount: int, data: bytes = b"", protect_zero: bool = False):
        """
        Abi encodes a call and appends it to the queue.
        :param _recipient: string or checsum address
        :param raw_amount: int wei quantity for message value
        :param data: arbitrary data for call
        """
        if protect_zero and raw_amount == 0:
            return
        else:
            print(f'[batcher] adding call: {raw_amount}')
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
    args.add_argument('-w', '--wallet', type=str, default='keys/wallet.json', help='Path to JSON wallet file.')
    args.add_argument('-n', '--network', type=str, default='goerli', choices=['ethereum', 'arbitrum', 'goerli'],
                      help='EVM chain to connect to.')
    args.add_argument('-f', '--file', type=str, help='List of: `address,amount` : one per line.')
    args.add_argument('-t', '--targets', type=str, nargs='+', help='Specify targets on CLI.')
    args.add_argument('-b', '--batch_size', type=int, default=20, help='Max txs per batch.')
    args.add_argument('-q', '--quantity', type=float, default=0, help='Quantity of Ether to send to recipients.')
    args = args.parse_args()
    dotenv.load_dotenv()
    if os.path.exists(args.wallet):
        with open(args.wallet, 'r') as f:
            privkey = json.loads(f.read()).get('wallet').get('private_key')
    else:
        print('[!] Please specify --wallet')
        exit(1)
    endpoint = os.environ.get(f'{args.network}_http_endpoint')
    contract_address = os.environ.get(f'{args.network}_batcher_contract_address')
    if not endpoint or not contract_address:
        print('[!] Please ensure that your .env file is properly configured. (See docs). ')
        exit(1)
    w3 = web3.Web3(web3.HTTPProvider(endpoint))

    # privkey, config = sw3.decrypt_load_wallet()
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

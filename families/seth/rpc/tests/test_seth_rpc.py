# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import unittest

from rpc_client import RpcClient
from mock_validator import MockValidator

from sawtooth_sdk.protobuf.validator_pb2 import Message
from sawtooth_sdk.protobuf.client_pb2 import ClientBlockListRequest
from sawtooth_sdk.protobuf.client_pb2 import ClientBlockListResponse
from sawtooth_sdk.protobuf.client_pb2 import ClientBlockGetRequest
from sawtooth_sdk.protobuf.client_pb2 import ClientBlockGetResponse
from sawtooth_sdk.protobuf.client_pb2 import ClientStateGetRequest
from sawtooth_sdk.protobuf.client_pb2 import ClientStateGetResponse
from sawtooth_sdk.protobuf.client_pb2 import ClientTransactionGetRequest
from sawtooth_sdk.protobuf.client_pb2 import ClientTransactionGetResponse
from sawtooth_sdk.protobuf.block_pb2 import Block
from sawtooth_sdk.protobuf.block_pb2 import BlockHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.txn_receipt_pb2 import ClientReceiptGetRequest
from sawtooth_sdk.protobuf.txn_receipt_pb2 import ClientReceiptGetResponse
from sawtooth_sdk.protobuf.txn_receipt_pb2 import TransactionReceipt
from protobuf.seth_pb2 import SethTransactionReceipt
from protobuf.seth_pb2 import EvmEntry
from protobuf.seth_pb2 import EvmStateAccount
from protobuf.seth_pb2 import EvmStorage
from protobuf.seth_pb2 import SethTransaction
from protobuf.seth_pb2 import CreateExternalAccountTxn
from protobuf.seth_pb2 import CreateContractAccountTxn
from protobuf.seth_pb2 import MessageCallTxn
from protobuf.seth_pb2 import SetPermissionsTxn


class SethRpcTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = MockValidator()
        cls.validator.listen("tcp://eth0:4004")
        cls.url = 'http://seth-rpc:3030/'
        cls.rpc = RpcClient(cls.url)
        cls.rpc.wait_for_service()

    # Network tests
    def test_net_version(self):
        """Test that the network id 19 is returned."""
        self.assertEqual("19", self.rpc.call("net_version"))

    def test_net_peerCount(self):
        """Test that 0 is returned as hex."""
        self.assertEqual("0x0", self.rpc.call("net_peerCount"))

    def test_net_listening(self):
        """Test that the True is returned."""
        self.assertEqual(True, self.rpc.call("net_listening"))

    # Block tests
    def test_block_number(self):
        """Test that the block number is extracted correctly and returned as
        hex."""
        self.rpc.acall("eth_blockNumber")
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_LIST_REQUEST)
        self.validator.respond(
            Message.CLIENT_BLOCK_LIST_RESPONSE,
            ClientBlockListResponse(
                status=ClientBlockListResponse.OK,
                blocks=[Block(
                    header=BlockHeader(block_num=15).SerializeToString(),
                )]),
            msg)
        self.assertEqual("0xf", self.rpc.get_result())

    def test_get_block_by_hash(self):
        """Test that a block is retrieved correctly, given a block id."""
        self._test_get_block(call="block", by="hash")

    def test_get_block_by_number(self):
        """Test that a block is retrieved correctly, given a block number."""
        self._test_get_block(call="block", by="number")

    def test_get_block_transaction_count_by_hash(self):
        """Test that a block transaction count is retrieved correctly, given a
        block id."""
        self._test_get_block(call="count", by="hash")

    def test_get_block_transaction_count_by_number(self):
        """Test that a block transaction count is retrieved correctly, given a
        block number."""
        self._test_get_block(call="count", by="number")

    def _test_get_block(self, call, by):
        block_id = "f" * 128
        block_num = 123
        prev_block_id = "e" * 128
        state_root = "d" * 64
        txn_id = "c" * 64
        gas = 456
        if call == "block":
            if by == "hash":
                self.rpc.acall("eth_getBlockByHash", ["0x" + block_id, False])
            elif by == "number":
                self.rpc.acall("eth_getBlockByNumber", [hex(block_num), False])
        elif call == "count":
            if by == "hash":
                self.rpc.acall(
                    "eth_getBlockTransactionCountByHash", ["0x" + block_id])
            elif by == "number":
                self.rpc.acall(
                    "eth_getBlockTransactionCountByNumber", [hex(block_num)])

        # Verify block get request
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_GET_REQUEST)
        request = ClientBlockGetRequest()
        request.ParseFromString(msg.content)
        if by == "hash":
            self.assertEqual(request.block_id, block_id)
        elif by == "number":
            self.assertEqual(request.block_num, block_num)

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(
                status=ClientBlockGetResponse.OK,
                block=Block(
                    header=BlockHeader(
                        block_num=block_num,
                        previous_block_id=prev_block_id,
                        state_root_hash=state_root
                    ).SerializeToString(),
                    header_signature=block_id,
                    batches=[Batch(transactions=[Transaction(
                        header=TransactionHeader(
                            family_name="seth",
                        ).SerializeToString(),
                        header_signature=txn_id,
                    )])],
                )
            ),
            msg)

        if call == "block":
            # Verify receipt get request
            msg = self.validator.receive()
            self.assertEqual(msg.message_type, Message.CLIENT_RECEIPT_GET_REQUEST)
            request = ClientReceiptGetRequest()
            request.ParseFromString(msg.content)
            self.assertEqual(request.transaction_ids[0], txn_id)

            self.validator.respond(
                Message.CLIENT_RECEIPT_GET_RESPONSE,
                ClientReceiptGetResponse(
                    status=ClientReceiptGetResponse.OK,
                    receipts=[TransactionReceipt(
                        data=[TransactionReceipt.Data(
                            data_type="seth_receipt",
                            data=SethTransactionReceipt(
                                gas_used=gas,
                            ).SerializeToString(),
                        )],
                        transaction_id=txn_id,
                    )]
                ),
                msg)

        result = self.rpc.get_result()
        if call == "block":
            self.assertEqual(result["number"], hex(block_num))
            self.assertEqual(result["hash"], "0x" + block_id)
            self.assertEqual(result["parentHash"], "0x" + prev_block_id)
            self.assertEqual(result["stateRoot"], "0x" + state_root)
            self.assertEqual(result["gasUsed"], hex(gas))
            self.assertEqual(result["transactions"][0], "0x" + txn_id)
        elif call == "count":
            self.assertEqual(result, "0x1")

    # Account tests
    def test_get_balance(self):
        """Test that an account balance is retrieved correctly."""
        self._test_get_account("balance")

    def test_get_code(self):
        """Test that an account's code is retrieved correctly."""
        self._test_get_account("code")

    def test_get_storage_at(self):
        """Test that an account's storage is retrieved correctly."""
        self._test_get_account("storage")

    def _test_get_account(self, call):
        account_address = "f" * 20 * 2
        balance = 123
        nonce = 456
        code_b = bytes([0xab, 0xcd, 0xef])
        code_s = "abcdef"
        position_b = bytes([0x01, 0x23, 0x45])
        position_s = "012345"
        stored_b = bytes([0x67, 0x89])
        stored_s = "6789"

        if call == "balance":
            self.rpc.acall(
                "eth_getBalance", ["0x" + account_address, "latest"])
        elif call == "code":
            self.rpc.acall(
                "eth_getCode", ["0x" + account_address, "latest"])
        elif call == "storage":
            self.rpc.acall(
                "eth_getStorageAt",
                ["0x" + account_address, "0x" + position_s, "latest"])
        elif call == "count":
            self.rpc.acall(
                "eth_getTransactionCount", ["0x" + account_address, "latest"])

        # Receive and validate the state request
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_STATE_GET_REQUEST)
        request = ClientStateGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.address,
            "a68b06" + account_address + "0" * 24)

        # Respond with state
        self.validator.respond(
            Message.CLIENT_STATE_GET_RESPONSE,
            ClientStateGetResponse(
                status=ClientStateGetResponse.OK,
                value=EvmEntry(
                    account=EvmStateAccount(
                        balance=balance,
                        nonce=nonce,
                        code=code_b),
                    storage=[EvmStorage(key=position_b, value=stored_b)],
                ).SerializeToString()),
            msg)

        # Validate response
        result = self.rpc.get_result()
        if call == "balance":
            self.assertEqual(hex(balance), result)
        elif call == "code":
            self.assertEqual("0x" + code_s, result)
        elif call == "storage":
            self.assertEqual("0x" + stored_s, result)
        elif call == "count":
            self.assertEqual(hex(nonce), result)

    def test_get_account_by_block_num(self):
        """Tests that account info is retrieved correctly when a block number
        is used as the block key.

        This requires an extra exchange with the validator to translate the
        block number into a block id, since it isn't possible to look up state
        based on a block number.
        """
        account_address = "f" * 20 * 2
        balance = 123
        block_num = 321
        block_id = "f" * 128

        self.rpc.acall(
            "eth_getBalance", ["0x" + account_address, hex(block_num)])

        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_GET_REQUEST)
        request = ClientBlockGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.block_num, block_num)

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(
                status=ClientBlockGetResponse.OK,
                block=Block(header_signature=block_id)
            ),
            msg)

        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_STATE_GET_REQUEST)
        request = ClientStateGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.head_id, block_id)
        self.assertEqual(request.address,
            "a68b06" + account_address + "0" * 24)

        self.validator.respond(
            Message.CLIENT_STATE_GET_RESPONSE,
            ClientStateGetResponse(
                status=ClientStateGetResponse.OK,
                value=EvmEntry(
                    account=EvmStateAccount(balance=balance),
                ).SerializeToString()),
            msg)

        result = self.rpc.get_result()
        self.assertEqual(hex(balance), result)

    def test_accounts(self):
        """Tests that account list is retrieved correctly."""
        address = "434d46456b6973a678b77382fca0252629f4389f"
        self.assertEqual(["0x" + address], self.rpc.call("eth_accounts"))

    # Transaction calls
    def test_get_transaction_by_hash(self):
        """Tests that a transaction is retrieved correctly given its hash."""
        block_id = "a" * 128
        block_num = 678
        txn_ids = [
            "0" * 64,
            "1" * 64,
            "2" * 64,
            "3" * 64,
        ]
        txn_idx = 2
        nonce = 4
        pub_key = "035e1de3048a62f9f478440a22fd7655b" + \
                  "80f0aac997be963b119ac54b3bfdea3b7"
        addr = "b4d09ca3c0bc538340e904b689016bbb4248136c"

        gas = 100
        to_b = bytes([0xab, 0xcd, 0xef])
        to_s = "abcdef"
        data_b = bytes([0x67, 0x89])
        data_s = "6789"

        self.rpc.acall(
            "eth_getTransactionByHash",
            ["0x" + txn_ids[txn_idx]])

        msg = self.validator.receive()
        self.assertEqual(
            msg.message_type, Message.CLIENT_TRANSACTION_GET_REQUEST)
        request = ClientTransactionGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.transaction_id, txn_ids[txn_idx])

        block = self._make_multi_txn_block(
            txn_ids, nonce, block_num, block_id, pub_key, gas, to_b,
            data_b)

        self.validator.respond(
            Message.CLIENT_TRANSACTION_GET_RESPONSE,
            ClientTransactionGetResponse(
                status=ClientBlockGetResponse.OK,
                transaction=block.batches[1].transactions[1],
                block=block_id),
            msg)

        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_GET_REQUEST)
        request = ClientBlockGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.block_id, block_id)

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(
                status=ClientBlockGetResponse.OK,
                block=block),
            msg)

        result = self.rpc.get_result()
        self.assertEqual(result["hash"], "0x" + txn_ids[txn_idx])
        self.assertEqual(result["nonce"], hex(nonce))
        self.assertEqual(result["blockHash"], "0x" + block_id)
        self.assertEqual(result["blockNumber"], hex(block_num))
        self.assertEqual(result["transactionIndex"], hex(txn_idx))
        self.assertEqual(result["from"], "0x" + addr)
        self.assertEqual(result["to"], "0x" + to_s)
        self.assertEqual(result["value"], "0x0")
        self.assertEqual(result["gasPrice"], "0x0")
        self.assertEqual(result["gas"], hex(gas))
        self.assertEqual(result["input"], "0x" + data_s)

    def test_get_transaction_by_block_hash_and_index(self):
        """Tests that a transaction is retrieved correctly given a block
        signature and transaction index."""
        self._test_get_transaction_by_idx(by="hash")

    def test_get_transaction_by_block_number_and_index(self):
        """Tests that a transaction is retrieved correctly given a block
        number and transaction index."""
        self._test_get_transaction_by_idx(by="number")

    def _test_get_transaction_by_idx(self, by):
        block_id = "a" * 128
        block_num = 678
        txn_ids = [
            "0" * 64,
            "1" * 64,
            "2" * 64,
            "3" * 64,
        ]
        txn_idx = 2
        nonce = 4
        pub_key = "035e1de3048a62f9f478440a22fd7655b" + \
                  "80f0aac997be963b119ac54b3bfdea3b7"
        addr = "b4d09ca3c0bc538340e904b689016bbb4248136c"

        gas = 100
        to_b = bytes([0xab, 0xcd, 0xef])
        to_s = "abcdef"
        data_b = bytes([0x67, 0x89])
        data_s = "6789"

        if by == "hash":
            self.rpc.acall(
                "eth_getTransactionByBlockHashAndIndex",
                ["0x" + block_id, hex(txn_idx)])
        elif by == "number":
            self.rpc.acall(
                "eth_getTransactionByBlockNumberAndIndex",
                [hex(block_num), hex(txn_idx)])

        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_GET_REQUEST)
        request = ClientBlockGetRequest()
        request.ParseFromString(msg.content)

        if by == "hash":
            self.assertEqual(request.block_id, block_id)
        elif by == "number":
            self.assertEqual(request.block_num, block_num)

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(
                status=ClientBlockGetResponse.OK,
                block=self._make_multi_txn_block(
                    txn_ids, nonce, block_num, block_id, pub_key, gas, to_b,
                    data_b)
            ),
            msg)

        result = self.rpc.get_result()
        self.assertEqual(result["hash"], "0x" + txn_ids[txn_idx])
        self.assertEqual(result["nonce"], hex(nonce))
        self.assertEqual(result["blockHash"], "0x" + block_id)
        self.assertEqual(result["blockNumber"], hex(block_num))
        self.assertEqual(result["transactionIndex"], hex(txn_idx))
        self.assertEqual(result["from"], "0x" + addr)
        self.assertEqual(result["to"], "0x" + to_s)
        self.assertEqual(result["value"], "0x0")
        self.assertEqual(result["gasPrice"], "0x0")
        self.assertEqual(result["gas"], hex(gas))
        self.assertEqual(result["input"], "0x" + data_s)

    def test_get_transaction_by_block_hash_and_index_no_block(self):
        """Tests that a transaction is retrieved correctly given a block
        signature and transaction index, where the block doesn't exist but the
        transaction does."""
        block_id = "a" * 128
        txn_idx = 2

        self.rpc.acall(
            "eth_getTransactionByBlockHashAndIndex",
            ["0x" + block_id, hex(txn_idx)])

        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_GET_REQUEST)
        request = ClientBlockGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.block_id, block_id)

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(status=ClientBlockGetResponse.NO_RESOURCE),
            msg)

        result = self.rpc.get_result()
        self.assertEqual(result, None)

    def _make_multi_txn_block(self, txn_ids, nonce, block_num, block_id,
                              pub_key, gas, to, data):
        txns = [
            Transaction(
                header=TransactionHeader(
                    family_name="seth",
                    signer_pubkey=pub_key,
                ).SerializeToString(),
                header_signature=txn_ids[i],
                payload=txn.SerializeToString())
            for i, txn in enumerate([
                SethTransaction(
                    transaction_type=SethTransaction.SET_PERMISSIONS,
                    set_permissions=SetPermissionsTxn()),
                SethTransaction(
                    transaction_type=SethTransaction.CREATE_EXTERNAL_ACCOUNT,
                    create_external_account=CreateExternalAccountTxn()),
                SethTransaction(
                    transaction_type=SethTransaction.MESSAGE_CALL,
                    message_call=MessageCallTxn(
                        nonce=nonce,
                        gas_limit=gas,
                        to=to,
                        data=data,
                )),
                SethTransaction(
                    transaction_type=SethTransaction.CREATE_CONTRACT_ACCOUNT,
                    create_contract_account=CreateContractAccountTxn()),
            ])
        ]

        return Block(
            header=BlockHeader(
                block_num=block_num,
            ).SerializeToString(),
            header_signature=block_id,
            batches=[
                Batch(transactions=txns[0:1]),
                Batch(transactions=txns[1:3]),
                Batch(transactions=txns[3:4]),
            ])
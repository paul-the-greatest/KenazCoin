#v2

import hashlib 
import json
from coin.core.wallet import Wallet
from coin.core.utxo import TxInput, TxOutput



class Transaction:
    def __init__(self, inputs, outputs, sender_public_key=None, block_index=None):
        #inputs: list of TxInput (empty for coinbase)
        #outputs: list of TxOutput
        #sender_public_key: tuple (e, n), needed to verify signature. None for coinbase

        self.inputs = inputs
        self.outputs = outputs
        self.sender_public_key = sender_public_key
        self.signature = None
        self.block_index = block_index
 
    def tx_id(self):
        #hash on input and output(signed)
        payload = {
            "inputs":  [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
        }
        if self.block_index is not None:
            payload["block_index"] = self.block_index
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
 
    def is_coinbase(self):
        return len(self.inputs) == 0
    

    def sign(self, sender_wallet):
        if self.is_coinbase():
            raise ValueError("Coinbase transactions are not signed.")
        self.signature = sender_wallet.sign(self.tx_id())

    def is_valid(self):
        #signature check only does NOT check UTXO existence
        #(that's the blockchain's job, since it requires global state)
 
        if self.is_coinbase():
            # coinbase has no signature to check, only structure
            if len(self.inputs) != 0:
                print("[INVALID] Coinbase has inputs.")
                return False
            return True
 
        if self.signature is None:
            print("[INVALID] Transaction is unsigned.")
            return False
 
        verifier = _PublicKeyVerifier(self.sender_public_key)
        if not verifier.verify(self.tx_id(), self.signature):
            print("[INVALID] Signature does not match.")
            return False
 
        return True


    
    #  construction helpers 
 
    @classmethod
    def new_coinbase(cls, miner_address, reward, block_index):
        output = TxOutput(address=miner_address, amount=reward)
        return cls(inputs=[], outputs=[output], block_index=block_index)
 
    @classmethod
    def new_transfer(cls, sender_wallet, receiver_address, amount, utxo_set, fee=0):

        total_needed = amount + fee
        spendable = utxo_set.get_spendable_outputs(sender_wallet.address)
 
        inputs = []
        total_collected = 0
 
        for key, output in spendable:
            inputs.append(TxInput(tx_id=key[0], output_index=key[1]))
            total_collected += output.amount
            if total_collected >= total_needed:
                break
 
        if total_collected < total_needed:
            raise ValueError(
                f"Insufficient funds: have {total_collected}, need {total_needed} ({amount} + {fee} fee)"
            )
 
        outputs = [TxOutput(address=receiver_address, amount=amount)]
 
        change = total_collected - total_needed  # fee stays out (goes to miner)
        if change > 0:
            outputs.append(TxOutput(address=sender_wallet.address, amount=change))
 
        tx = cls(inputs=inputs, outputs=outputs, sender_public_key=sender_wallet.public_key)
        tx.sign(sender_wallet)
        return tx
 
 
    # serialisation 
 
    def to_string(self):
        #canonical str representation when hashed into a block/merkle tree
        d = {
            "tx_id":     self.tx_id(),
            "inputs":    [i.to_dict() for i in self.inputs],
            "outputs":   [o.to_dict() for o in self.outputs],
            "sender_public_key": list(self.sender_public_key) if self.sender_public_key else None,
            "signature": self.signature,
        }
        if self.block_index is not None:
            d["block_index"] = self.block_index
        return json.dumps(d, sort_keys=True)

    @classmethod
    def from_string(cls, tx_str):
        raw = json.loads(tx_str)

        inputs = [
            TxInput(tx_id=i["tx_id"], output_index=i["output_index"])
            for i in raw.get("inputs", [])
        ]
        outputs = [
            TxOutput(address=o["address"], amount=o["amount"])
            for o in raw.get("outputs", [])
        ]

        public_key = raw.get("sender_public_key")
        if public_key is not None:
            public_key = tuple(public_key)

        tx = cls(inputs=inputs, outputs=outputs, sender_public_key=public_key, block_index=raw.get("block_index"))

        signature = raw.get("signature")
        if signature is not None:
            tx.signature = int(signature)

        return tx
 
    def __repr__(self):
        if self.is_coinbase():
            out = self.outputs[0]
            return f"Transaction(COINBASE) -> {out.address[:8]}... | {out.amount} Coin"
 
        status = "signed" if self.signature else "UNSIGNED"
        total_out = sum(o.amount for o in self.outputs)
        return (
            f"Transaction({status}) "
            f"{len(self.inputs)} input(s) -> {len(self.outputs)} output(s) "
            f"| total {total_out} Coin"
        )
 
 
class _PublicKeyVerifier:
    def __init__(self, public_key):
        self.public_key = public_key
 
    def verify(self, message, signature):
        def sha256_int(msg):
            return int(hashlib.sha256(msg.encode()).hexdigest(), 16)
 
        e, n = self.public_key
        msg_hash = sha256_int(message) % n
        decrypted = pow(signature, e, n)
        return decrypted == msg_hash
 
 
#
#testing
#
 
if __name__ == "__main__":
    #alice,bob,charles,david,ferdnand ... bullshitnames 
    from coin.core.utxo import UTXOSet
 
    print("Creating wallets…")
    alice = Wallet(key_bits=512)
    bob = Wallet(key_bits=512)
    print(f"Alice: {alice}")
    print(f"Bob: {bob}\n")
 
    utxo_set = UTXOSet()
 
    # give Alice some coins via coinbase
    print("--- Coinbase: Alice mines a block, gets 50 coins ---")
    coinbase = Transaction.new_coinbase(alice.address, reward=50, block_index=1)
    print(coinbase)
    utxo_set.apply_coinbase(coinbase)
    print(f"Alice balance: {utxo_set.get_balance(alice.address)}\n")
 
    # Alice pays Bob 10
    print("--- Alice pays Bob 10 ---")
    tx = Transaction.new_transfer(alice, bob.address, 10, utxo_set)
    print(tx)
    print(f"Valid? {tx.is_valid()}")
    utxo_set.apply_transaction(tx)
 
    print(f"\nAlice balance: {utxo_set.get_balance(alice.address)}")
    print(f"Bob balance  : {utxo_set.get_balance(bob.address)}")
 
    print(f"\n{utxo_set}")
 
    # Alice tries to spend more than she has
    print("\n--- Alice tries to pay Bob 1000 (insufficient funds) ---")
    try:
        Transaction.new_transfer(alice, bob.address, 1000, utxo_set)
    except ValueError as e:
        print(f"[REJECTED] {e}")




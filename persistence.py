import json
import os
from block import Block
from blockchain import Blockchain
from transaction import Transaction
from utxo import TxInput, TxOutput
from wallet import Wallet


#blockchain
def save_chain(blockchain, path="chain.json"):
    data = []
    for block in blockchain.chain:
        data.append({
            "index":         block.index,
            "timestamp":     block.timestamp,
            "data":          block.data,
            "previous_hash": block.previous_hash,
            "nonce":         block.nonce,
            "hash":          block.hash,
        })
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2) #indent=2 is to simplify reading
    print(f"[persistence] chain saved → {path} ({len(data)} blocks)")
 
def load_chain(blockchain, path="chain.json"):
    #loads blocks from disk then replays then all transactions to rebuild the utxo from scratch
    #valueerror if the loaded chain fails integrity check 
    if not os.path.exists(path):
        print(f"[persistence] no chain file at {path}, starting fresh")
        return
 
    with open(path) as f:
        data = json.load(f)
    #apaga tudo before
    blockchain.chain.clear()
    blockchain.utxo_set.utxos.clear()

    #
    for entry in data:
        block = Block(
            index=entry["index"],
            data=entry["data"],
            previous_hash=entry["previous_hash"],
            nonce=entry["nonce"],
        )

        #restore exact timestamp and hash, recomputing 'would' differ
        block.timestamp = entry["timestamp"]
        block.hash= entry["hash"]
        blockchain.chain.append(block)

    if not blockchain.is_valid():
        raise ValueError("[persistence] loaded chain failed integrity check!")
 
    _rebuild_utxo(blockchain)
    print(f"[persistence] chain loaded ← {path} ({len(blockchain.chain)} blocks)")



def _rebuild_utxo(blockchain):
    #replay every tx in every block to reconstruct the UTXO set
    #json doesnot contain any balance data, balance is the consequence
    for block in blockchain.chain[1:]:  # skip genesis, no real tx
        for tx_str in block.data.get("transactions", []):
            tx = _deserialize_tx(tx_str)
            if tx.is_coinbase():
                blockchain.utxo_set.apply_coinbase(tx)
            else:
                blockchain.utxo_set.apply_transaction(tx)



def _deserialize_tx(tx_str):
    #reconstruct a Transaction from its JSON string (inputs + outputs only)
    #present balance 
    raw = json.loads(tx_str)
 
    inputs = [
        TxInput(tx_id=i["tx_id"], output_index=i["output_index"])
        for i in raw.get("inputs", [])
    ]
    outputs = [
        TxOutput(address=o["address"], amount=o["amount"])
        for o in raw.get("outputs", [])
    ]
 
    return Transaction(inputs=inputs, outputs=outputs)



#wallet

def save_wallet(wallet, directory="."):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"wallet_{wallet.address}.json")
    #RSA COMPONENTS RSA wikipedia page is trustable. read about it there.
    e, n = wallet.public_key
    d, _ = wallet.private_key # _ is a discart
 
    with open(path, "w") as f:
        json.dump({
            "address":     wallet.address,
            "public_key":  {"e": e, "n": n},
            "private_key": {"d": d, "n": n},
        }, f, indent=2)
    print(f"[persistence] wallet saved → {path}")
 
 
def load_wallet(address, directory="."):
    path = os.path.join(directory, f"wallet_{address}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no wallet file for address {address}")
 
    with open(path) as f:
        data = json.load(f)
    
    #__new__// init would erase the old address. so _new_ puts manually the old keys read on json
    wallet = Wallet.__new__(Wallet)
    wallet.address= data["address"]
    wallet.public_key = (data["public_key"]["e"],  data["public_key"]["n"])
    wallet.private_key = (data["private_key"]["d"], data["private_key"]["n"])
 
    print(f"[persistence] wallet loaded ← {wallet}")
    return wallet



#if main
if __name__ == "__main__":
    CHAIN_FILE = "/tmp/ncoin_chain.json"
    WALLET_DIR = "/tmp/ncoin_wallets"
 
    # build a small chain
    print("=== building chain ===")
    alice = Wallet(key_bits=512)
    bob   = Wallet(key_bits=512)
 
    bc = Blockchain(difficulty=3)
    bc.mine_block(transactions=[], miner_address=alice.address)
 
    tx = Transaction.new_transfer(alice, bob.address, 10, bc.utxo_set)
    bc.mine_block(transactions=[tx], miner_address=bob.address)
 
    print(f"Alice: {bc.utxo_set.get_balance(alice.address)}")
    print(f"Bob  : {bc.utxo_set.get_balance(bob.address)}")
 
    # save
    print("\n=== saving ===")
    save_chain(bc, CHAIN_FILE)
    save_wallet(alice, WALLET_DIR)
    save_wallet(bob,   WALLET_DIR)
 
    # load into a fresh blockchain
    print("\n=== loading into fresh blockchain ===")
    bc2 = Blockchain(difficulty=3)
    load_chain(bc2, CHAIN_FILE)
 
    alice2 = load_wallet(alice.address, WALLET_DIR)
    bob2   = load_wallet(bob.address,   WALLET_DIR)
 
    print(f"\nAlice: {bc2.utxo_set.get_balance(alice2.address)}")
    print(f"Bob  : {bc2.utxo_set.get_balance(bob2.address)}")
    print(f"Chain valid? {bc2.is_valid()}")
 
    # alice2 can still spend after reload
    print("\n=== alice spends from loaded wallet ===")
    tx2 = Transaction.new_transfer(alice2, bob2.address, 5, bc2.utxo_set)
    block = bc2.mine_block(transactions=[tx2], miner_address=bob2.address)
    print(f"Mined block {block.index}")
    print(f"Alice: {bc2.utxo_set.get_balance(alice2.address)}")
    print(f"Bob  : {bc2.utxo_set.get_balance(bob2.address)}")
 
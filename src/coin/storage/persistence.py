import json
import os
import hashlib
from coin.core.block import Block
from coin.core.blockchain import Blockchain
from coin.core.transaction import Transaction
from coin.core.utxo import TxInput, TxOutput
from coin.core.wallet import Wallet

import sys
import hmac
 
 
#  encryption primitives 
# XOR stream cipher built from chained SHA-256 blocks.
# not production-grade, but honest stdlib-only crypto:
# key derivation : PBKDF2-HMAC-SHA256 (100k rounds, random salt)
# keystream: SHA-256(key || iv || block_counter) repeated until len(data)
# IV: 16 random bytes from os.urandom
 
def _derive_key(password, salt):
    #PBKDF2 turns a password into a strong 32-byte key
    #
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
 
def _xor_stream(data, key, iv):
    
    # generates keystream by hashing (key + iv + counter) in 32-byte chunks
    keystream = b""
    counter = 0
    while len(keystream) < len(data):
        block= hashlib.sha256(key + iv + counter.to_bytes(4, "big")).digest()
        keystream += block
        counter += 1
    #zip emparelha os bytes real com ruido
    # ^ = xor; NI subject, when xor is applied, the text is unreadable, when applied again it is readable
    return bytes(a ^ b for a, b in zip(data, keystream))  # XOR

#gonna add checksum rn, so wrong passwords fail
def _encrypt(plaintext, password):
    salt = os.urandom(16)
    iv= os.urandom(16)
    key= _derive_key(password, salt)
    mac = hmac.new(key, plaintext.encode(), hashlib.sha256).hexdigest()
    verified  = json.dumps({"mac": mac, "payload": plaintext})
    ciphertext = _xor_stream(verified.encode(), key, iv)
    return (salt + iv + ciphertext).hex()


def _decrypt(blob_hex, password):
    raw= bytes.fromhex(blob_hex)
    salt, iv= raw[:16], raw[16:32]
    ciphertext = raw[32:]
    key= _derive_key(password, salt)
    
    verified = json.loads(_xor_stream(ciphertext, key, iv).decode())
    mac = hmac.new(key, verified["payload"].encode(), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(mac, verified["mac"]):
        raise ValueError("wrong password or corrupted wallet")
    
    return verified["payload"]




def get_data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(base, "ncoin")

#blockchain
def save_chain(blockchain, path=None):
    if path is None:
        path = os.path.join(get_data_dir(), "chain.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
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
    print(f"[persistence] chain saved -> {path} ({len(data)} blocks)")
 
def load_chain(blockchain, path=None):
    if path is None:
        path = os.path.join(get_data_dir(), "chain.json")
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
    print(f"[persistence] chain loaded <- {path} ({len(blockchain.chain)} blocks)")



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
    return Transaction.from_string(tx_str)



#wallet

def list_wallets(directory=None):
    if directory is None:
        directory = os.path.join(get_data_dir(), "wallets")
    if not os.path.exists(directory):
        return []

    wallets = []
    for filename in os.listdir(directory):
        if not filename.startswith("wallet_") or not filename.endswith(".json"):
            continue

        path = os.path.join(directory, filename)
        address = filename[len("wallet_"):-len(".json")]

        try:
            with open(path) as f:
                data = json.load(f)
            encrypted = data.get("encrypted", False)
        except Exception:
            encrypted = None

        wallets.append({"address": address, "encrypted": encrypted, "path": path})

    return sorted(wallets, key=lambda w: w["address"])

def save_wallet(wallet, directory=None, password=None):
    if directory is None:
        directory = os.path.join(get_data_dir(), "wallets")
    os.makedirs(directory, exist_ok=True)
    path= os.path.join(directory, f"wallet_{wallet.address}.json")
    #rsa wikipedia is trustable
    e, n= wallet.public_key
    d, _= wallet.private_key  # _ discarded
 
    payload = json.dumps({
        "address":     wallet.address,
        "public_key":  {"e": e, "n": n},
        "private_key": {"d": d, "n": n},
    }, indent=2)
 
    if password:
        # store an encrypted blob instead of plaintext JSON
        out = {"encrypted": True, "data": _encrypt(payload, password)}
    else:
        out = {"encrypted": False, "data": json.loads(payload)}
 
    with open(path, "w") as f:
        json.dump(out, f, indent=2)


    lock = "encrypted" if password else "plain"
    print(f"[persistence] wallet saved {lock} -> {path}")
 
def load_wallet(address, directory=None, password=None):
    if directory is None:
        directory = os.path.join(get_data_dir(), "wallets")
    path = os.path.join(directory, f"wallet_{address}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no wallet file for address {address}")
 
    with open(path) as f:
        out = json.load(f)
 
    if out["encrypted"]:
        if password is None:
            raise ValueError("wallet is encrypted provide a password")
        raw= _decrypt(out["data"], password)
        data= json.loads(raw)
    else:
        data = out["data"]
 
    # __new__ skips __init__ so we don't generate a fresh key pair
    wallet= Wallet.__new__(Wallet)
    wallet.address= data["address"]
    wallet.public_key = (data["public_key"]["e"],  data["public_key"]["n"])
    wallet.private_key= (data["private_key"]["d"], data["private_key"]["n"])
 
    print(f"[persistence] wallet loaded <- {wallet}")
    return wallet
 
 




#peers

PEERS_FILE = "peers.json"

def save_peers(peers_dict, path=PEERS_FILE):
    data = [[h, p] for (h, p) in peers_dict]
    with open(path, "w") as f:
        json.dump(data, f)
    print(f"[persistence] peers saved -> {path} ({len(data)} known)")

def load_peers(path=PEERS_FILE):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    print(f"[persistence] peers loaded <- {path} ({len(data)} known)")
    return [(h, p) for h, p in data]


#if main
if __name__ == "__main__":
    CHAIN_FILE = "/tmp/ncoin_chain.json"
    WALLET_DIR = "/tmp/ncoin_wallets"
 
    # build a small chain
    print("=== building chain ===")
    alice = Wallet(key_bits=512)
    bob = Wallet(key_bits=512)
 
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
    save_wallet(bob, WALLET_DIR)
 
    # load into a fresh blockchain
    print("\n=== loading into fresh blockchain ===")
    bc2 = Blockchain(difficulty=3)
    load_chain(bc2, CHAIN_FILE)
 
    alice2 = load_wallet(alice.address, WALLET_DIR)
    bob2 = load_wallet(bob.address,   WALLET_DIR)
 
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
 

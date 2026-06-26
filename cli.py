import argparse
import os
import sys
import threading
 
from blockchain import Blockchain
from mempool import Mempool
from node import Node
from persistence import load_chain, save_chain, load_wallet, save_wallet
from transaction import Transaction
from wallet import Wallet
from message import make_new_tx, make_new_block

CHAIN_FILE = "chain.json"
WALLET_DIR = "wallet"

## helpers
 
def _load_or_create_wallet(address, password):
    # if address given, try to load from disk
    # otherwise generate a fresh wallet and save it
    os.makedirs(WALLET_DIR, exist_ok=True)
 
    if address:
        try:
            return load_wallet(address, WALLET_DIR, password)
        except FileNotFoundError:
            print(f"[cli] no wallet found for address {address}")
            sys.exit(1)
    else:
        print("[cli] no wallet specified — generating new wallet...")
        w = Wallet(key_bits=512)
        pw = input("Set wallet password (leave blank for unencrypted): ").strip() or None
        save_wallet(w, WALLET_DIR, pw)
        print(f"[cli] wallet created: {w.address}")
        return w
 
 
def _load_or_create_chain(difficulty):
    bc = Blockchain(difficulty=difficulty)
    if os.path.exists(CHAIN_FILE):
        try:
            load_chain(bc, CHAIN_FILE)
        except ValueError as e:
            print(f"[cli] chain file corrupt: {e} — starting fresh")
            bc = Blockchain(difficulty=difficulty)
    return bc

 
# command handlers
 
def cmd_balance(wallet, blockchain):
    bal = blockchain.utxo_set.get_balance(wallet.address)
    print(f"balance: {bal} NCoin  (address: {wallet.address})")
 
 
def cmd_send(args, wallet, blockchain, mempool, node):
    # usage: send <address> <amount>
    parts = args.strip().split()
    if len(parts) != 2:
        print("usage: send <address> <amount>")
        return
 
    receiver, amount = parts[0], int(parts[1])
 
    try:
        tx = Transaction.new_transfer(wallet, receiver, amount, blockchain.utxo_set)
    except ValueError as e:
        print(f"[cli] {e}")
        return
 
    with node._lock:
        accepted = mempool.add(tx)
 
    if accepted:
        # broadcast to all peers
        node.broadcast(make_new_tx(tx.to_string()))
        print(f"[cli] tx sent: {tx.tx_id()[:16]}...")
    else:
        print("[cli] tx rejected by mempool")
 
 
def cmd_mine(wallet, blockchain, mempool, node):
    print("[cli] mining...")
 
    with node._lock:
        block = blockchain.mine_block(
            miner_address=wallet.address,
            mempool=mempool,
        )
 
    if block is None:
        print("[cli] mining failed — invalid transactions in mempool")
        return
 
    print(f"[cli] mined block {block.index} | nonce={block.nonce}")
 
    # broadcast the new block to all peers
    from node import _serialize_block
    node.broadcast(make_new_block(_serialize_block(block)))
 
    # persist chain after every mined block
    save_chain(blockchain, CHAIN_FILE)
 
 
def cmd_peers(node):
    with node._lock:
        peers = list(node.peers.keys())
    if not peers:
        print("no peers connected")
    for p in peers:
        print(f"  {p[0]}:{p[1]}")
 
 
def cmd_chain(blockchain):
    print(blockchain)
 
 
def cmd_mempool(mempool):
    print(mempool)
 
 
def cmd_connect(args, node):
    # usage: connect <host> <port>
    parts = args.strip().split()
    if len(parts) != 2:
        print("usage: connect <host> <port>")
        return
    node.connect(parts[0], int(parts[1]))
 
 
def cmd_save(blockchain):
    save_chain(blockchain, CHAIN_FILE)
    print(f"[cli] chain saved to {CHAIN_FILE}")
 
 
HELP = """
commands:
  balance               show your balance
  send <addr> <amt>     send NCoin to an address
  mine                  mine a block with mempool txs
  connect <host> <port> connect to a peer
  peers                 list connected peers
  chain                 print the chain
  mempool               print pending transactions
  save                  save chain to disk
  help                  show this message
  exit                  quit
"""
 
 
# main loop
 
def main():
    parser = argparse.ArgumentParser(description="NCoin node + wallet CLI")
    parser.add_argument("--port",       type=int, default=5000,  help="TCP port to listen on")
    parser.add_argument("--host",       type=str, default="127.0.0.1")
    parser.add_argument("--connect",    type=str, default=None,  help="peer to connect to: host:port")
    parser.add_argument("--wallet",     type=str, default=None,  help="wallet address to load")
    parser.add_argument("--password",   type=str, default=None,  help="wallet password")
    parser.add_argument("--difficulty", type=int, default=3)
    args = parser.parse_args()
 
    # setup
    wallet     = _load_or_create_wallet(args.wallet, args.password)
    blockchain = _load_or_create_chain(args.difficulty)
    mempool    = Mempool()
    node       = Node(args.host, args.port, blockchain, mempool)
 
    node.start()
 
    # connect to a known peer if given
    if args.connect:
        host, port = args.connect.split(":")
        node.connect(host, int(port))
 
    print(f"\nNCoin node running on {args.host}:{args.port}")
    print(f"wallet: {wallet.address}")
    print(f"chain:  {len(blockchain.chain)} blocks")
    print('type "help" for commands\n')
 
    # command loop — runs on the main thread
    # the node server and peer handlers run on daemon threads in the background
    # all shared state (blockchain, mempool) is protected by node._lock
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[cli] shutting down")
            save_chain(blockchain, CHAIN_FILE)
            break
 
        if not line:
            continue
 
        cmd, _, rest = line.partition(" ")
 
        if   cmd == "balance":  cmd_balance(wallet, blockchain)
        elif cmd == "send":     cmd_send(rest, wallet, blockchain, mempool, node)
        elif cmd == "mine":     cmd_mine(wallet, blockchain, mempool, node)
        elif cmd == "connect":  cmd_connect(rest, node)
        elif cmd == "peers":    cmd_peers(node)
        elif cmd == "chain":    cmd_chain(blockchain)
        elif cmd == "mempool":  cmd_mempool(mempool)
        elif cmd == "save":     cmd_save(blockchain)
        elif cmd == "help":     print(HELP)
        elif cmd == "exit":
            save_chain(blockchain, CHAIN_FILE)
            break
        else:
            print(f"unknown command: {cmd}  (type 'help')")
 
 
if __name__ == "__main__":
    main()
 
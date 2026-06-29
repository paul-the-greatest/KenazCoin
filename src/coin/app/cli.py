import argparse
import os
import sys
import threading
 
from coin.core.blockchain import Blockchain
from coin.core.mempool import Mempool
from coin.network.node import Node
from coin.storage.persistence import load_chain, save_chain, load_wallet, save_wallet, list_wallets, load_peers, save_peers, get_data_dir
from coin.core.transaction import Transaction
from coin.core.wallet import Wallet
from coin.network.message import make_new_tx, make_new_block

CHAIN_FILE = os.path.join(get_data_dir(), "chain.json")
WALLET_DIR = os.path.join(get_data_dir(), "wallets")

## helpers
 
def _load_or_create_wallet(address, password):
    os.makedirs(WALLET_DIR, exist_ok=True)

    wallets = list_wallets(WALLET_DIR)
 
    if address:
        return _load_wallet_login(address, password)

    if wallets:
        print("[cli] saved wallets:")
        for w in wallets:
            lock = "encrypted" if w["encrypted"] else "plain"
            print(f"  {w['address']} ({lock})")

        address = input("wallet address (blank to create new): ").strip()
        if address:
            return _load_wallet_login(address, password)

    while True:
        print("[cli] creating new wallet...")
        pw = input("Set wallet password: ").strip()
        if not pw:
            print("[cli] wallet password is required")
            continue

        w = Wallet(key_bits=512)
        save_wallet(w, WALLET_DIR, pw)
        print(f"[cli] wallet created: {w.address}")
        return w


def _load_wallet_login(address, password):
    if password is None:
        password = input("wallet password: ").strip() or None

    try:
        return load_wallet(address, WALLET_DIR, password)
    except FileNotFoundError:
        print(f"[cli] no wallet found for address {address}")
        sys.exit(1)
    except ValueError as e:
        print(f"[cli] {e}")
        sys.exit(1)
 
 
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
        print("[cli] pending in mempool mine a block to confirm it")
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
    from coin.network.node import _serialize_block
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


def cmd_wallet(wallet, blockchain):
    balance = blockchain.utxo_set.get_balance(wallet.address)
    print(f"address: {wallet.address}")
    print(f"balance: {balance} NCoin")
    print(f"public key: {wallet.public_key}")


def cmd_wallets():
    wallets = list_wallets(WALLET_DIR)
    if not wallets:
        print("no wallets saved")
        return

    for w in wallets:
        lock = "encrypted" if w["encrypted"] else "plain"
        print(f"{w['address']} ({lock})")


def cmd_utxos(args, blockchain):
    address = args.strip() or None
    found = False

    for (tx_id, index), output in blockchain.utxo_set.utxos.items():
        if address and output.address != address:
            continue

        found = True
        print(f"{tx_id[:16]}...:{index} -> {output.address} | {output.amount} NCoin")

    if not found:
        if address:
            print(f"no utxos for {address}")
        else:
            print("no utxos")
 
 
def cmd_autominer(args, wallet, node):
    if args.strip() == "stop":
        node.stop_miner()
    else:
        node.start_miner(wallet.address)

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
 
#i know its not optimal, must fix it soon
HELP = """
commands:
  balance               show your balance
  send <addr> <amt>     send NCoin to an address
  mine                  mine a block with mempool txs
  autominer [stop]      start/stop background auto-miner
  connect <host> <port> connect to a peer
  peers                 list connected peers
  chain                 print the chain
  mempool               print pending transactions
  wallet                show current wallet info
  wallets               list saved wallets
  switch <address>      switch to another saved wallet
  new-wallet            create a new wallet and switch to it
  utxos [address]       show all utxos or filter by address
  save                  save chain to disk
  help                  show this message
  exit                  quit
"""
 
 
# main loop
 
def main():
    parser = argparse.ArgumentParser(description="NCoin node + wallet CLI")
    parser.add_argument("--port",       type=int, default=5000,  help="TCP port to listen on")
    parser.add_argument("--host",       type=str, default="127.0.0.1")
    parser.add_argument("--connect",    type=str, nargs="*", default=[],  help="peer(s) to connect: host:port [host:port ...]")
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
 
    # connect to known peers
    for peer in args.connect:
        host, port = peer.split(":")
        node.connect(host, int(port))

    known_peers = load_peers()
    explicit = set()
    for p in args.connect:
        h, p_ = p.split(":")
        explicit.add((h, int(p_)))
    for host, port in known_peers:
        if (host, port) not in explicit:
            node.connect(host, port)

    print(f"\nNCoin node running on {args.host}:{args.port}")
    print(f"wallet: {wallet.address}")
    print(f"chain:  {len(blockchain.chain)} blocks")
    print('type "help" for commands\n')
 
    # command loop  runs on the main thread
    # the node server and peer handlers run on daemon threads in the background
    # all shared state (blockchain, mempool) is protected by node._lock
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[cli] shutting down")
            save_chain(blockchain, CHAIN_FILE)
            with node._lock:
                save_peers(node.peers)
            break
 
        if not line:
            continue
 
        cmd, _, rest = line.partition(" ")
 
        if cmd == "balance":  cmd_balance(wallet, blockchain)
        elif cmd == "send":     cmd_send(rest, wallet, blockchain, mempool, node)
        elif cmd == "mine":     cmd_mine(wallet, blockchain, mempool, node)
        elif cmd == "autominer":  cmd_autominer(rest, wallet, node)
        elif cmd == "connect":  cmd_connect(rest, node)
        elif cmd == "peers":    cmd_peers(node)
        elif cmd == "chain":    cmd_chain(blockchain)
        elif cmd == "mempool":  cmd_mempool(mempool)
        elif cmd == "wallet":   cmd_wallet(wallet, blockchain)
        elif cmd == "wallets":  cmd_wallets()
        elif cmd == "switch":
            parts = rest.strip().split()
            if not parts:
                print("usage: switch <address> [password]")
            else:
                address = parts[0]
                password = parts[1] if len(parts) > 1 else None
                if password is None:
                    password = input("wallet password: ").strip() or None
                try:
                    wallet = load_wallet(address, WALLET_DIR, password)
                    print(f"[cli] switched to wallet {wallet.address}")
                except (FileNotFoundError, ValueError) as e:
                    print(f"[cli] {e}")
        elif cmd == "new-wallet":
            pw = rest.strip() or input("Set wallet password: ").strip()
            if not pw:
                print("[cli] password required for new wallet")
            else:
                w = Wallet(key_bits=512)
                save_wallet(w, WALLET_DIR, pw)
                wallet = w
                print(f"[cli] created and switched to wallet {w.address}")
        elif cmd == "utxos":    cmd_utxos(rest, blockchain)
        elif cmd == "save":     cmd_save(blockchain)
        elif cmd == "help":     print(HELP)
        elif cmd == "exit":
            save_chain(blockchain, CHAIN_FILE)
            with node._lock:
                save_peers(node.peers)
            break
        else:
            print(f"unknown command: {cmd}  (type 'help')")
 
 
if __name__ == "__main__":
    main()

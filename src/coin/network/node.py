import socket
import threading
import json
from coin.network.message import (     
    read_message, make_handshake, make_get_peers, make_peers,
    make_new_tx, make_new_block, make_blocks, make_get_blocks,
    HANDSHAKE, GET_BLOCKS, BLOCKS, NEW_TX, NEW_BLOCK, GET_PEERS, PEERS,
)

from coin.core.transaction import Transaction
from coin.core.utxo import TxInput, TxOutput


#each node is a tcp server and client at the same time accepts peers and connect to known peers 
# all peers 1/0 runs in its own thread
# bc and mempool are shares objs, all multations go through self._lock to avoind race 
#conditions across threads

class Node:
    def __init__(self, host, port, blockchain, mempool):
        self.host = host 
        self.port = port 
        self.blockchain = blockchain
        self.mempool = mempool

        #
        #act peer sockets. addr to socket

        self.peers={}
        self._lock = threading.Lock()

        self._abort_event = threading.Event()
        self._miner_wallet = None
        self._miner_thread = None

    #server

    def start(self):
        #opens the tcp server in a daemon thread, and dies when main exists

        t = threading.Thread(target=self._serve, daemon=True)
        t.start()
        print(f"[node] listening on {self.host}:{self.port}")
 
    def _serve(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(10)
 
        while True:
            conn, addr = srv.accept()
            print(f"[node] incoming connection from {addr}")
            t = threading.Thread(target=self._handle_peer, args=(conn, addr), daemon=True)
            t.start()

#client 
 
    def connect(self, host, port):
        # connects to a peer, sends handshake, then hands off to _handle_peer
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((host, port))
        except OSError as e:
            print(f"[node] could not connect to {host}:{port} — {e}")
            return
        addr = (host, port)
        with self._lock:
            self.peers[addr] = conn
 
        conn.sendall(make_handshake(self.host, self.port, len(self.blockchain.chain)))
        print(f"[node] connected to {host}:{port}")
 
        t = threading.Thread(target=self._handle_peer, args=(conn, addr), daemon=True)
        t.start()

    #peerloop

    def _handle_peer(self, conn, addr):
        # reads messages from a peer in a loop and dispatches to handlers
        with self._lock:
            self.peers[addr] = conn
 
        try:
            while True:
                msg = read_message(conn)
                if msg is None:
                    break  # peer disconnected cleanly
                self._dispatch(msg, conn, addr)
        except Exception as e:
            print(f"[node] peer {addr} error: {e}")
        finally:
            with self._lock:
                self.peers.pop(addr, None)
            conn.close()
            print(f"[node] peer {addr} disconnected")
 
    def _dispatch(self, msg, conn, addr):
        t = msg["type"]
        payload = msg["payload"]
 
        if t == HANDSHAKE:  self._on_handshake(payload, conn, addr)
        elif t == GET_BLOCKS: self._on_get_blocks(payload, conn)
        elif t == BLOCKS: self._on_blocks(payload)
        elif t == NEW_TX: self._on_new_tx(payload)
        elif t == NEW_BLOCK: self._on_new_block(payload)
        elif t == GET_PEERS: self._on_get_peers(conn)
        elif t == PEERS: self._on_peers(payload)
        else:
            print(f"[node] unknown message type: {t}")

    #handlers, manipulador de eventos 

    def _on_handshake(self, payload, conn, addr): #quando handshake
        their_length = payload["chain_length"]
        our_length = len(self.blockchain.chain)
        print(f"[node] handshake from {addr} — their chain: {their_length}, ours: {our_length}")
 
        # reply with our own handshake so they can compare chains too
        conn.sendall(make_handshake(self.host, self.port, our_length))
 
        # ask for their peer list
        conn.sendall(make_get_peers())
 
        # if they have more blocks, request what we're missing
        if their_length > our_length:
            conn.sendall(make_get_blocks(our_length))
 
    def _on_get_blocks(self, payload, conn):
        since = payload["since_index"]
        with self._lock:
            blocks_to_send = self.blockchain.chain[since:]
 
        serialized = [_serialize_block(b) for b in blocks_to_send]
        conn.sendall(make_blocks(serialized))
        print(f"[node] sent {len(serialized)} blocks (since index {since})")
 
    def _on_blocks(self, payload):
        from coin.network.sync import apply_blocks
        blocks_data = payload["blocks"]
        apply_blocks(self, blocks_data)
 
    def _on_new_tx(self, payload):
        tx = _deserialize_tx(payload["tx"])
        if tx is None:
            return
 
        with self._lock:
            accepted = self.mempool.add(tx)
 
        # rebroadcast only if it was new to us
        if accepted:
            self.broadcast(make_new_tx(payload["tx"]), exclude_origin=None)
 
    def _on_new_block(self, payload):
        self._abort_event.set()
        from coin.network.sync import apply_blocks
        apply_blocks(self, [payload["block"]])
 
    def _on_get_peers(self, conn):
        with self._lock:
            peer_list = [[addr[0], addr[1]] for addr in self.peers]
        conn.sendall(make_peers(peer_list))
 
    def _on_peers(self, payload):
        # try to connect to any peer we dont know yet
        #only connect to addresses that were advertised as server ports,
        # not ephemeral client ports avoids reconnection loop
        for host, port in payload["peers"]:
            addr = (host, port)
            with self._lock:
                already_known = addr in self.peers
            is_self = (host == self.host and port == self.port)
            if not already_known and not is_self:
                # only attempt connection if the port looks like a server port
                # (peers list only contains host:port from make_handshake)
                self.connect(host, port)

#breadcast

 
    def broadcast(self, msg_bytes, exclude_origin=None):
        # sends msg_bytes to all connected peers except exclude_origin
        with self._lock:
            targets = list(self.peers.items())
 
        for addr, conn in targets:
            if addr == exclude_origin:
                continue
            try:
                conn.sendall(msg_bytes)
            except OSError:
                pass  # dead socket. will be cleaned up by its _handle_peer thread
 

 
    # miner

    def start_miner(self, wallet_address):
        self._miner_wallet = wallet_address
        if self._miner_thread and self._miner_thread.is_alive():
            print("[node] miner already running")
            return
        self._abort_event.clear()
        self._miner_thread = threading.Thread(target=self._miner_loop, daemon=True)
        self._miner_thread.start()
        print(f"[node] auto-miner started")

    def stop_miner(self):
        self._miner_wallet = None
        self._abort_event.set()
        print(f"[node] auto-miner stopped")

    def _miner_loop(self):
        from coin.core.transaction import Transaction
        from coin.core.merkletree import MerkleTree
        from coin.core.block import Block
        from coin.storage.persistence import save_chain
        from coin.network.message import make_new_block

        while True:
            self._abort_event.clear()

            # build candidate under lock
            with self._lock:
                if self._miner_wallet is None:
                    break
                addr = self._miner_wallet
                bc = self.blockchain
                mp = self.mempool

                pulled = mp.get_all()
                reward = bc.get_coinbase_reward(len(bc.chain))
                coinbase = Transaction.new_coinbase(addr, reward, len(bc.chain))
                all_txs = [coinbase] + pulled

                if not bc._validate_transactions(all_txs):
                    self._abort_event.wait(1)
                    continue

                tx_strings = [tx.to_string() for tx in all_txs]
                merkle_root = MerkleTree(tx_strings).get_root()
                candidate = Block(
                    index=len(bc.chain),
                    data={"transactions": tx_strings, "merkle_root": merkle_root},
                    previous_hash=bc.last_block.hash,
                )

            # mine outside lock
            mined = bc.pow.mine(candidate, self._abort_event)
            if mined is None:
                continue  # aborted or chain changed

            # apply state under lock
            with self._lock:
                if len(self.blockchain.chain) != candidate.index:
                    continue  # chain tip changed while we mined

                for tx in all_txs:
                    if tx.is_coinbase():
                        self.blockchain.utxo_set.apply_coinbase(tx)
                    else:
                        self.blockchain.utxo_set.apply_transaction(tx)
                for tx in all_txs:
                    self.mempool.remove(tx.tx_id())

                self.blockchain.chain.append(mined)
                self.blockchain._adjust_difficulty()
                print(f"[miner] mined block {mined.index} | nonce={mined.nonce}")

            # broadcast & persist outside lock
            self.broadcast(make_new_block(_serialize_block(mined)))
            save_chain(self.blockchain)


#serialization helpers
def _serialize_block(block):
    return {
        "index": block.index,
        "timestamp": block.timestamp,
        "data": block.data,
        "previous_hash": block.previous_hash,
        "nonce": block.nonce,
        "hash": block.hash,
    }
 
def _deserialize_tx(tx_str):
    try:
        return Transaction.from_string(tx_str)
    except Exception as e:
        print(f"[node] failed to deserialize tx: {e}")
        return None
    

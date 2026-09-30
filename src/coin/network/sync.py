from coin.core.block import Block
from coin.core.transaction import Transaction
from coin.core.utxo import TxInput, TxOutput
import json
 

def apply_blocks(node, blocks_data):
    #Receives a list of serialized block dicts from a peer and tries to
    #append each one to the local chain in order.
    #Strategy (deliberate simplicity no orphan pool):
      # if the block's previous_hash doesn't match our last block, discard
      # everything and request a full sync from that peer.
      # if PoW or tx validation fails, drop the block silently.
      # if everything checks out, append and update UTXO.
    
    blocks = [_deserialize_block(d) for d in blocks_data]
    blocks = [b for b in blocks if b is not None]

    if not blocks:
        return

    with node._lock:
        bc = node.blockchain

        # case 1: blocks extend our chain cleanly — append one by one
        if blocks[0].index == len(bc.chain):
            for block in blocks:
                _try_append(node, block)
            return

        # case 2: peer sent blocks starting from 0 (or earlier than our tip)
        # this is a fork — build the candidate chain and let replace_chain decide
        if blocks[0].index == 0:
            candidate = _build_candidate_chain(bc, blocks)
            if candidate:
                replaced = bc.replace_chain(candidate)
                if replaced:
                    print(f"[sync] chain replaced, new length={len(bc.chain)}")
            return

        # case 3: we're missing the parent — full resync as before
        print(f"[sync] block {blocks[0].index} has unknown parent — requesting full sync")
        _request_full_sync(node)
 
def _try_append(node, block):
    bc = node.blockchain
 
    # block already known
    if block.index < len(bc.chain):
        return
 
    # out of order we're missing the parent, full resync
    if block.previous_hash != bc.last_block.hash:
        print(f"[sync] block {block.index} has unknown parent — requesting full sync")
        _request_full_sync(node)
        return
 
    # PoW check
    if not bc.pow.is_valid_proof(block):
        print(f"[sync] block {block.index} failed PoW check — discarded")
        return
 
    # reconstruct transactions and validate
    txs = _extract_transactions(block)
    if not bc._validate_transactions(txs):
        print(f"[sync] block {block.index} failed tx validation — discarded")
        return
 
    # apply UTXO changes
    for tx in txs:
        if tx.is_coinbase():
            bc.utxo_set.apply_coinbase(tx)
        else:
            bc.utxo_set.apply_transaction(tx)
 
    # evict confirmed txs from mempool
    for tx in txs:
        node.mempool.remove(tx.tx_id())

    bc.chain.append(block)
    node._abort_event.set()
    print(f"[sync] appended block {block.index} (hash={block.hash[:16]}...)")
 
 
def _request_full_sync(node):
    # ask all connected peers for everything we don't have
    from coin.network.message import make_get_blocks
    our_length = len(node.blockchain.chain)
    targets = list(node.peers.items())  

    for addr, conn in targets:
        try:
            conn.sendall(make_get_blocks(our_length))
        except OSError:
            pass

def _deserialize_block(data):
    # Block.__init__ calls compute_hash() which includes timestamp,
    # so we must restore timestamp and hash manually after construction
    # this shit has to work this way

    try:
        block= Block.__new__(Block)
        block.index= data["index"]
        block.timestamp= data["timestamp"]
        block.data= data["data"]
        block.previous_hash = data["previous_hash"]
        block.nonce= data["nonce"]
        block.hash= data["hash"]
        return block
    except Exception as e:
        print(f"[sync] failed to deserialize block: {e}")
        return None
 
 
def _extract_transactions(block):
    txs = []
    for tx_str in block.data.get("transactions", []):
        try:
            txs.append(Transaction.from_string(tx_str))
        except Exception as e:
            print(f"[sync] failed to deserialize tx in block: {e}")
    return txs


def _build_candidate_chain(bc, blocks):
    # validates a list of blocks as a self-consistent chain
    # returns the list if valid, None otherwise

    # must start with the same genesis
    if blocks[0].hash != bc.chain[0].hash:
        print("[sync] candidate chain has different genesis — rejected")
        return None

    for i in range(1, len(blocks)):
        b = blocks[i]
        prev = blocks[i - 1]

        if b.previous_hash != prev.hash:
            print(f"[sync] candidate chain broken at index {i}")
            return None

        if not bc.pow.is_valid_proof(b):
            print(f"[sync] candidate block {i} failed PoW")
            return None

    return blocks

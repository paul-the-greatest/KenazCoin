from block import Block
from transaction import Transaction
from utxo import TxInput, TxOutput
import json
 
 
def apply_blocks(node, blocks_data):
    #Receives a list of serialized block dicts from a peer and tries to
    #append each one to the local chain in order.
    #Strategy (deliberate simplicity no orphan pool):
      # if the block's previous_hash doesn't match our last block, discard
      # everything and request a full sync from that peer.
      # if PoW or tx validation fails, drop the block silently.
      # if everything checks out, append and update UTXO.
    
    for block_data in blocks_data:
        block = _deserialize_block(block_data)
        if block is None:
            continue
 
        with node._lock:
            _try_append(node, block)
 
 
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
    print(f"[sync] appended block {block.index} (hash={block.hash[:16]}...)")
 
 
def _request_full_sync(node):
    # ask all connected peers for everything we don't have
    from message import make_get_blocks
    our_length = len(node.blockchain.chain)
    with node._lock:
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
            raw     = json.loads(tx_str)
            inputs  = [TxInput(tx_id=i["tx_id"], output_index=i["output_index"]) for i in raw.get("inputs",  [])]
            outputs = [TxOutput(address=o["address"], amount=o["amount"])         for o in raw.get("outputs", [])]
            txs.append(Transaction(inputs=inputs, outputs=outputs))
        except Exception as e:
            print(f"[sync] failed to deserialize tx in block: {e}")
    return txs
 
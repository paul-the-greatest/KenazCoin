from coin.core.transaction import Transaction
 
 
class Mempool:
    # holds pending transactions waiting to be mined into a block
    # does NOT check UTXO validity that's the blockchain's job at mine time
 
    def __init__(self):
        # tx_id -> Transaction
        self.pending = {}
 
    #  mutations
 
    def add(self, tx):
        # rejects coinbase (those are created by the miner, not broadcast)
        # rejects duplicates and unsigned/malformed transactions
        if tx.is_coinbase():
            print("[mempool] rejected: coinbase transactions are not broadcast")
            return False
 
        if not tx.is_valid():
            print("[mempool] rejected: invalid signature or structure")
            return False
 
        tx_id = tx.tx_id()
        if tx_id in self.pending:
            print(f"[mempool] duplicate: {tx_id[:16]}... already in pool")
            return False
 
        self.pending[tx_id] = tx
        print(f"[mempool] accepted: {tx_id[:16]}... ({len(self.pending)} in pool)")
        return True
 
    def remove(self, tx_id):
        # called after a block confirms a transaction
        removed = self.pending.pop(tx_id, None)
        return removed is not None
 
    def clear(self):
        self.pending.clear()
 
    # queries 
 
    def get_all(self):
        # returns a snapshot list — safe to iterate while mining
        return list(self.pending.values())
 
    def size(self):
        return len(self.pending)
 
    def __repr__(self):
        lines = [f"Mempool ({len(self.pending)} pending):"]
        for tx_id, tx in self.pending.items():
            lines.append(f"  {tx_id[:16]}... | {tx}")
        return "\n".join(lines)
 

# test
 
if __name__ == "__main__":
    from coin.core.wallet import Wallet
    from coin.core.utxo import UTXOSet
    from coin.core.blockchain import Blockchain
 
    alice = Wallet(key_bits=512)
    bob = Wallet(key_bits=512)
    bc = Blockchain(difficulty=3)
    pool  = Mempool()
 
    # give alice some coins
    bc.mine_block(miner_address=alice.address)
 
    tx = Transaction.new_transfer(alice, bob.address, 10, bc.utxo_set)
    pool.add(tx)
    pool.add(tx)  # duplicate, should be rejected
 
    print(pool)
 
    bc.mine_block(miner_address=bob.address, mempool=pool)
    print(f"\nAfter mining pool size: {pool.size()}")
    print(f"Bob balance: {bc.utxo_set.get_balance(bob.address)}")

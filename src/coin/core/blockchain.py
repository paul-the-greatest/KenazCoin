from coin.core.block import Block
from coin.core.merkletree import MerkleTree
from coin.core.pow import Proofofwork
from coin.core.transaction import Transaction
from coin.core.utxo import UTXOSet

RETARGET_INTERVAL=5 #RECALCULATE DIFFICULTY EVERY N BLOCKS
TARGET_BLOCK_TIME=50 # SECONDS PER BLOCK (TARGET)


class Blockchain:
    

    def __init__(self, difficulty=3):
        self.chain = []
        self.utxo_set = UTXOSet()
        self.pow = Proofofwork(difficulty)
        self._create_genesis_block()

    def _create_genesis_block(self): #genesisblock
        genesis = Block(index=0, data={"transactions": [], "merkle_root": "0" * 64}, previous_hash="0" * 64)
        genesis.timestamp = 0 # fixed, now every node must produce the same genesis hash
        genesis.hash = genesis.compute_hash()
        self.chain.append(genesis)
 
    @property
    def last_block(self):
        return self.chain[-1] #lastblock
    
    #difficulty adjustment 
 
    def _adjust_difficulty(self):
        if len(self.chain) % RETARGET_INTERVAL != 0:
            return
 
        last = self.chain[-1]
        previous = self.chain[-RETARGET_INTERVAL]
 
        actual_time = last.timestamp - previous.timestamp
        target_time = TARGET_BLOCK_TIME * RETARGET_INTERVAL
 
        ratio = target_time / max(actual_time, 1)
        new_difficulty = max(1, round(self.pow.difficulty * ratio))
 
        if new_difficulty != self.pow.difficulty:
            print(f"[difficulty] {self.pow.difficulty} -> {new_difficulty} "
                  f"(actual {actual_time:.1f}s, target {target_time}s)")
            self.pow.difficulty = new_difficulty
            self.pow.target = "0" * new_difficulty
 
 

    #validation 
        """
        #Checks each tx in order: if
          1 signature is valid (or it's a well-formed coinbase)
          2 every input exists in the UTXO set
          3 no input is reused twice within the same (double-spend)
          4 inputs cover outputs (no minting out of thin air, except coinbase)
        it returns T/F. raises nothing, just reports.
        """
    
    def _validate_transactions(self, transactions):
        spent_in_this_block = set()
        coinbase_count = 0
 
        for tx in transactions:
            if not tx.is_valid():
                print("[INVALID] Transaction failed signature/structure check.")
                return False
 
            if tx.is_coinbase():
                coinbase_count += 1
                if coinbase_count > 1:
                    print("[INVALID] More than one coinbase transaction.")
                    return False
                continue
 
            total_in = 0
            for tx_input in tx.inputs:
                key = tx_input.key()
 
                if key in spent_in_this_block:
                    print(f"[INVALID] Double-spend within block: {key}")
                    return False
 
                if not self.utxo_set.is_unspent(tx_input):
                    print(f"[INVALID] Input references unknown/spent output: {key}")
                    return False
 
                total_in += self.utxo_set.utxos[key].amount
                spent_in_this_block.add(key)
 
            total_out = sum(o.amount for o in tx.outputs)
            if total_out > total_in:
                print(f"[INVALID] Outputs ({total_out}) exceed inputs ({total_in}).")
                return False
 
        return True
    

#mining 

    HALVING_INTERVAL = 100
    INITIAL_REWARD = 50

    def get_coinbase_reward(self, block_index):
        halvings = block_index // self.HALVING_INTERVAL
        return max(1, self.INITIAL_REWARD >> halvings)
    
 
    def mine_block(self, miner_address, transactions=None, mempool=None, abort_event=None):
        # transactions: explicit list of Transaction objects (optional)
        # mempool: Mempool instance  if provided, pulls all pending txs
        # both can be combined, explicit transactions take priority (prepended)

        pulled = mempool.get_all() if mempool else []
        explicit = transactions or []
        user_txs = explicit + [tx for tx in pulled if tx not in explicit]

        reward  = self.get_coinbase_reward(len(self.chain))  # <-- linha nova
        coinbase = Transaction.new_coinbase(miner_address, reward, len(self.chain))  # <-- passa reward
        all_txs = [coinbase] + user_txs

        if not self._validate_transactions(all_txs):
            return None

        tx_strings = [tx.to_string() for tx in all_txs]
        merkle_root = MerkleTree(tx_strings).get_root()

        candidate = Block(
            index = len(self.chain),
            data = {"transactions": tx_strings, "merkle_root": merkle_root},
            previous_hash = self.last_block.hash,
        )
        mined = self.pow.mine(candidate, abort_event)
        if mined is None:
            return None

        # apply state changes only after the block is fully valid + mined
        for tx in all_txs:
            if tx.is_coinbase():
                self.utxo_set.apply_coinbase(tx)
            else:
                self.utxo_set.apply_transaction(tx)
 
        # evict confirmed transactions from the mempool
        if mempool:
            for tx in user_txs:
                mempool.remove(tx.tx_id())
 
        self.chain.append(mined)
        return mined


#integrity 

    def is_valid(self):
        for i in range(1, len(self.chain)): #starts in 1 becuase the last block is genesis
            current = self.chain[i]
            previous = self.chain[i - 1]
 
            if current.hash != current.compute_hash(): #check hash
                print(f"[INVALID] Block {i} hash mismatch.")
                return False
 
            if current.previous_hash != previous.hash: #check the last block along
                print(f"[INVALID] Block {i} broken link to block {i-1}.")
                return False
 
            if not self.pow.is_valid_proof(current): #check pow
                print(f"[INVALID] Block {i} does not satisfy PoW target.")
                return False
            
        return True
 



    def chain_work(self):
        # total accumulated work: sum of 16^difficulty for each block
        # each leading zero = 1/16 chance, so difficulty d = 16^d expected hashes
        return sum(16 ** self.pow.difficulty for _ in self.chain[1:])

    def replace_chain(self, new_chain):
        # accepts a list of Block objects already validated by the caller
        # replaces self.chain if new_chain has more accumulated work
        # rebuilds UTXO from scratch on replacement (safe but slow — fine for edu)

        from coin.storage.persistence import _rebuild_utxo  # local import avoids circular dep

        if len(new_chain) <= 1:
            return False  # peer sent only genesis or empty

        # compare work: rough proxy longer valid chain usually wins;
        # for correctness we use block count * difficulty (uniform difficulty here)
        new_work = sum(16 ** self.pow.difficulty for _ in new_chain[1:])
        our_work  = self.chain_work()

        if new_work <= our_work:
            print(f"[consensus] peer chain rejected (work {new_work} <= ours {our_work})")
            return False

        print(f"[consensus] replacing chain (their work {new_work} > ours {our_work})")
        self.chain = new_chain
        self.utxo_set.utxos.clear()
        _rebuild_utxo(self)
        return True

    def __repr__(self): #report
        lines = [f"Blockchain ({len(self.chain)} blocks):"]
        for block in self.chain:
            tx_count = len(block.data.get("transactions", []))
            lines.append(
                f"  [{block.index}] hash={block.hash[:16]}... "
                f"txs={tx_count} nonce={block.nonce}"
            )
        return "\n".join(lines)
 
 




#
# test

if __name__ == "__main__":
    from coin.core.wallet import Wallet
 
    alice = Wallet(key_bits=512)
    bob= Wallet(key_bits=512)
 
    bc = Blockchain(difficulty=3)
 
    print("--- Block 1: Alice mines, gets coinbase reward ---")
    block1 = bc.mine_block(transactions=[], miner_address=alice.address)
    print(f"Mined block {block1.index} | nonce={block1.nonce}")
    print(f"Alice balance: {bc.utxo_set.get_balance(alice.address)}\n")
 
    print("--- Block 2: Alice pays Bob 10, Bob mines ---")
    tx = Transaction.new_transfer(alice, bob.address, 10, bc.utxo_set)
    block2 = bc.mine_block(transactions=[tx], miner_address=bob.address)
    print(f"Mined block {block2.index} | nonce={block2.nonce}")
    print(f"Alice balance: {bc.utxo_set.get_balance(alice.address)}")
    print(f"Bob balance  : {bc.utxo_set.get_balance(bob.address)}")
 
    print(f"\n{bc}")
    print(f"\nChain valid? {bc.is_valid()}")
 
    print("\n--- Bob tries to spend more than he has ---")
    try:
        bad_tx = Transaction.new_transfer(bob, alice.address, 999, bc.utxo_set)
    except ValueError as e:
        print(f"[REJECTED] {e}")


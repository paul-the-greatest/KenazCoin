from block import Block
from blockchain import Blockchain

class Proofofwork:
    def __init__(self, difficulty: int=3):
        #difficulty = number of leading zeros required in a valid hash
        # higher = harder (exponentially) (each 0 = ~16x more work)
        self.difficulty = difficulty
        self.target = "0" * difficulty

    
    def mine(self, block: Block):
        block.nonce=0
        block.hash = block.compute_hash()

        while not block.hash.startswith(self.target):
            block.nonce += 1
            block.hash = block.compute_hash()
        return block
    
    def is_valid_proof(self, block: Block): #check if it satisfies pow target
        return (
            block.hash == block.compute_hash()
            and block.hash.startswith(self.target)
        )
    
class Minedblockchain(Blockchain):
    #bc that requires every new block to be mined before appending

    def __init__(self, difficulty: int = 3):
        self.pow = Proofofwork(difficulty)
        super().__init__()
 
    def add_block(self, data):
        candidate = Block(
            index=len(self.chain),
            data=data,
            previous_hash=self.last_block.hash,
        )
        mined = self.pow.mine(candidate)
        self.chain.append(mined)
        return mined
 
 

#testing
if __name__ == "__main__":
    import time
 
    DIFFICULTY = 4  # change to 5+ to feel the exponential cost
    print(f"Mining with difficulty={DIFFICULTY} (target: {'0'*DIFFICULTY}...)\n")
    bc = Minedblockchain(difficulty=DIFFICULTY)
 
    for payload in ["P1 >> P2: 10", "P2 >> P3: 5", "P3 >> P4: 2"]:
        t0 = time.time()
        block = bc.add_block(payload)
        elapsed = time.time() - t0
        print(
            f"Block {block.index} mined in {elapsed:.3f}s | "
            f"nonce={block.nonce:,} | hash={block.hash[:20]}..."
        )
 
    print(f"\nChain valid? {bc.is_valid()}")
    
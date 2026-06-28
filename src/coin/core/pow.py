from coin.core.block import Block

class Proofofwork:
    def __init__(self, difficulty: int=3):
        #difficulty = number of leading zeros required in a valid hash
        # higher = harder (exponentially) (each 0 = around16x more work)
        self.difficulty = difficulty
        self.target = "0" * difficulty

    
    def mine(self, block: Block, abort_event=None):
        block.nonce=0
        block.hash = block.compute_hash()

        while not block.hash.startswith(self.target):
            if abort_event and abort_event.is_set():
                return None
            block.nonce += 1
            block.hash = block.compute_hash()
        return block
    
    def is_valid_proof(self, block: Block): #check if it satisfies pow target
        return (
            block.hash == block.compute_hash()
            and block.hash.startswith(self.target)
        )

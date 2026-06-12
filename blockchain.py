from block import Block


class Blockchain:
    pass

    def __init__(self):
        self.chain: list[Block] = []
        self._create_genesis_block()

    
    def _create_genesis_block(self): #intern
        genesis = Block(index=0, data="Genesis Block", previous_hash='O'*64)
        self.chain.append(genesis)

    #api

    @property
    def last_block(self):
        return self.chain[-1] #self.chain[len(self.chain) - 1]
    
    def add_block(self, data):
        #creates a new block and appends it
        #future = new_block.mine_block(difficulty)

        new_block = Block(
            index=len(self.chain),
            data=data,
            previous_hash=self.last_block.hash,
        )
        self.chain.append(new_block)
        return new_block 
    
    def is_valid(self):
        #walk the chain and verify if its stores hash matches and previous

        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            if current.previous_hash != current.compute_hash():
                print(f'[INVALID] Block {i} hash mismatch.')
                return False
            
            if current.previous_hash != previous.hash:
                print(f"[INVALID] Block {i} broken link to block {i-1}.")
                return False
            
        return True
    
    def __repr__(self):
        lines = [f'Blockchain ({len(self.chain)}) blocks): ']
    
        for b in self.chain:
            lines.append(
                f" [{b.index}] hash={b.hash[:16]}... "
                f" prev={b.previous_hash[:16]}.."
            )
            
        return '\n'.join(lines)
    

#quick gigga test

if __name__ =='__main__':
    blockchain = Blockchain()
    bc = blockchain
    bc.add_block('P1 pays P3 10 coins')
    bc.add_block('P2 pays P4 5 coins')

        
    print(bc)
    print(f"\nChain valid? {bc.is_valid()}")
 
    # Tamper with block 1 and re-check
    print("\n--- Tampering with block 1 ---")
    bc.chain[1].data = "Alice pays Eve 999 coins"
    # Note: we do NOT recompute bc.chain[1].hash  a real attacker might,
    # but then block 2's previous_hash would still point to the old hash.
    print(f"Chain valid? {bc.is_valid()}")

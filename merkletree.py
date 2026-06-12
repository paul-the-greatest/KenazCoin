import hashlib

def sha256(data):
    return hashlib.sha256(data.encode()).hexdigest()

class MerkleTree:
    def __init__(self, transactions: list[str]):
        #transactions: list of string representations of transactions.

        if not transactions:
            raise ValueError("Cannot build a Merkle tree from an empty list.")
 
        self.transactions = transactions
        self.leaves: list[str] = [sha256(tx) for tx in transactions]
        self.root = self._build(self.leaves)

    def _build(self, level: list[str]):

        if len(level) == 1:
            return level[0]
    
        #duplicate the last element if the lever has an odd count

        if len(level) % 2 != 0:
            level = level + [level[-1]]
        parent_level=[]
        for i in range(0, len(level), 2):
            combined=level[i] + level[i+1]
            parent_hash = sha256(combined)
            parent_level.append(parent_hash)
 
        return self._build(parent_level)
 
    def get_root(self):
        return self.root
    
    def printtree(self):
        #print all levels from up to the root

        level = self.leaves[:]
        depth = 0 
        print(f" Level {depth} (leaves): {[h[:8]+'...' for h in level]}")

        while len(level) > 1:
            if len(level) % 2 != 0:
                level=level + [level[-1]]
            level = [sha256(level[i] + level[i+1]) for i in range(0, len(level), 2)]
            depth+=1
            print(f"Level {depth}: {[h[:8] +'...' for h in level]}")
            print(f'Root: {level[0]}')


#testing

if __name__ == "__main__":
    pass

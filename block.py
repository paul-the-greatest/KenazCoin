import time
import hashlib
import json

class Block:
    def __init__(self, index: int, data, previous_hash: str, nonce: int=0):
        self.index = index
        self.timestamp = time.time()
        self.data = data
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.compute_hash()

    def compute_hash(self):
        block_content = json.dumps({
            'index': self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        },
        sort_keys = True)

        return hashlib.sha256(block_content.encode()).hexdigest()
    
    def __repr__(self): #no need for .info anymore
        return (
            f"Block(\n"
            f"index         = {self.index}\n"
            f"timestamp     = {self.timestamp}\n"
            f"data          = {self.data}\n"
            f"previous_hash = {self.previous_hash[:16]}...\n"
            f"nonce         = {self.nonce}\n"
            f"hash          = {self.hash[:16]}...\n"
            f")\n"
        )
    

#test

if __name__ == '__main__':
    I = Block(index=0, data="Genesis Block", previous_hash="0" * 64)
    print(I)

    II = Block(index=2, data="Exodus Block", previous_hash=I.hash)
    print(II)

    #tamper

    print('Tamper detection')
    original_hash = II.hash
    II.data = 'Apocalipse data'
    recomputed = II.compute_hash()
    print(f"Stored hash : {original_hash[:32]}...")
    print(f"Recomputed  : {recomputed[:32]}...")
    print(f"Tampered?   : {original_hash != recomputed}")


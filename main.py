#end to end demo
#wallets -> transactions -> merkletree -> mined block -> blockchain

import time
from wallet import Wallet
from transaction import Transaction
from merkletree import MerkleTree
from PoW import Minedblockchain

def main():
    print('='*60)
    print(' Coin Blockchain demo')
    print('='*60)

    #wallets
    print("\n[1] Generating wallets (RSA 512-bit) ...")
    P1 = Wallet(key_bits=512) #alice 
    P2 = Wallet(key_bits=512) #bob
    P3 = Wallet(key_bits=512) #charlie
    print(f"  P1: {P1}")
    print(f"  P2: {P2}")
    print(f"  P3: {P3}")

    #signed transactions
    tx1 = Transaction(P1, P2.address,   10.0)
    tx2 = Transaction(P2, P3.address,  4.0)
    tx3 = Transaction(P3, P1.address,  1.5)
 
    tx1.sign(P1)
    tx2.sign(P2)
    tx3.sign(P3)
 
    transactions = [tx1, tx2, tx3]
    for tx in transactions:
        print(f"  {tx}  valid={tx.is_valid()}")

    print("\n[3] Building Merkle tree ...")
    tx_strings = [tx.to_string() for tx in transactions]
    tree = MerkleTree(tx_strings)
    print(f"  Merkle root : {tree.get_root()}")


    print("\n[4] Mining block (difficulty=3) ...")
    bc = Minedblockchain(difficulty=3)
 
    t0 = time.time()
    block = bc.add_block({
        "merkle_root":    tree.get_root(),
        "tx_count":       len(transactions),
        "transactions":   tx_strings,
    })
    print(f"  Block {block.index} mined in {time.time()-t0:.3f}s")
    print(f"  Nonce : {block.nonce:,}")
    print(f"  Hash  : {block.hash}")

    # validate the chain
    print(f"\n[5] Chain integrity check … {bc.is_valid()}")
    print("\n" + str(bc))
 
 
if __name__ == "__main__":
    main()

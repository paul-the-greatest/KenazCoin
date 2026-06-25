#wallets -> transactions -> merkletree -> mined block -> blockchain
#using alice, bob, carol, david etc... this time to make it clearer

from wallet import Wallet
from transaction import Transaction
from blockchain import Blockchain
 
 
def main():
    print("=" * 60)
    print("  NCoin / UTXO Demo")
    print("=" * 60)
 
    print("\n[1] Generating wallets …")
    alice = Wallet(key_bits=512)
    bob = Wallet(key_bits=512)
    carol = Wallet(key_bits=512)
    print(f"Alice: {alice}")
    print(f"Bob  : {bob}")
    print(f"Carol: {carol}")
 
    bc = Blockchain(difficulty=3)
 
    print("\n[2] Block 1 / Alice mines (coinbase reward) …")
    block1 = bc.mine_block(transactions=[], miner_address=alice.address)
    print(f"mined block {block1.index} | nonce={block1.nonce}")
    print(f"Alice balance: {bc.utxo_set.get_balance(alice.address)}")
 
    print("\n[3] Block 2 / Alice pays Bob 20, Carol mines …")
    tx1 = Transaction.new_transfer(alice, bob.address, 20, bc.utxo_set)
    block2 = bc.mine_block(transactions=[tx1], miner_address=carol.address)
    print(f"mined block {block2.index} | nonce={block2.nonce}")
    print(f"Alice balance: {bc.utxo_set.get_balance(alice.address)}")
    print(f"Bob balance  : {bc.utxo_set.get_balance(bob.address)}")
    print(f"Carol balance: {bc.utxo_set.get_balance(carol.address)}")
 
    print("\n[4] Block 3 / Bob pays Carol 5, Bob mines …")
    tx2 = Transaction.new_transfer(bob, carol.address, 5, bc.utxo_set)
    block3 = bc.mine_block(transactions=[tx2], miner_address=bob.address)
    print(f"mined block {block3.index} | nonce={block3.nonce}")
    print(f"Alice balance: {bc.utxo_set.get_balance(alice.address)}")
    print(f"Bob balance  : {bc.utxo_set.get_balance(bob.address)}")
    print(f"Carol balance: {bc.utxo_set.get_balance(carol.address)}")
 
    print(f"\n[5] Chain valid? {bc.is_valid()}")
    print(f"\n{bc}")
    print(f"\n{bc.utxo_set}")
 
 
if __name__ == "__main__":
    main()

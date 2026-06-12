import hashlib 
import json
from wallet import Wallet

class Transaction:
    def __init__(self, sender: Wallet, receiver_address: str, amount: float):
        #sender: Wallet object (we need the private key to sign)
        #receiver_address : the target wallet's address string
        #amount: how many coins to transfer
        
        self.sender_address = sender.address
        self.sender_public_key = sender.public_key   # needed for verification
        self.receiver_address = receiver_address
        self.amount = amount
        self.signature = None
 
    def _payload(self):
        return f"{self.sender_address}:{self.receiver_address}:{self.amount}"
    
    def sign (self, sender_wallet: Wallet):
        if sender_wallet.address != self.sender_address:
            raise ValueError("Cannot sign: wallet address does not match sender.")
        self.signature = sender_wallet.sign(self._payload())
 
    def is_valid(self) -> bool:
        if self.signature is None:
            print("[INVALID] Transaction is unsigned.")
            return False

        # Reconstruct a temporary wallet shell just to call verify()
        # its only needed the public key, no private key involved

        verifier = _PublicKeyVerifier(self.sender_public_key)
        if not verifier.verify(self._payload(), self.signature):
            print("[INVALID] Signature does not match.")
            return False
        return True

    def to_string(self):
        #canonical str representation when hashed into a block
        return json.dumps({
            "from":      self.sender_address,
            "to":        self.receiver_address,
            "amount":    self.amount,
            "signature": str(self.signature),
        }, sort_keys=True)
 
    def __repr__(self):
        status = "signed" if self.signature else "UNSIGNED"
        return (
            f"Transaction({status}) "
            f"{self.sender_address[:8]}... -> {self.receiver_address[:8]}... "
            f"| {self.amount} Coin"
        )
    
class _PublicKeyVerifier:
    def __init__(self, public_key: tuple):
        self.public_key = public_key
 
    def verify(self, message: str, signature: int):
        import hashlib
        def sha256_int(msg):
            return int(hashlib.sha256(msg.encode()).hexdigest(), 16)
 
        e, n = self.public_key
        msg_hash  = sha256_int(message) % n
        decrypted = pow(signature, e, n)
        return decrypted == msg_hash


#
#testing
#

if __name__ == "__main__":
    print("Creating wallets…")
    alice = Wallet(key_bits=512)
    bob   = Wallet(key_bits=512)
    print(f"Alice: {alice}")
    print(f"Bob  : {bob}\n")
 
    tx = Transaction(sender=alice, receiver_address=bob.address, amount=10.0)
    print(f"Before signing : {tx}")
    print(f"Valid?         : {tx.is_valid()}\n")
 
    tx.sign(alice)
    print(f"After signing  : {tx}")
    print(f"Valid?         : {tx.is_valid()}\n")
 
    # Tampering demo change the amount after signing
    print("--- Tampering: change amount after signing ---")
    tx.amount = 999.0
    print(f"Valid after tamper? {tx.is_valid()}")

    
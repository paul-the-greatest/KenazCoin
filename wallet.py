import hashlib
import random
import math


# RSA primitive helpers 
def _is_prime(n: int, rounds: int = 20):
    #miller rabin primality test
    if n < 2:
        return False
    if n == 2 or n == 3:
        return True
    if n % 2 == 0:
        return False
 
    # Write n-1 as 2^r * d
    r, d = 0, n - 1
    while d % 2 == 0:
        r += 1
        d //= 2 #d = d//2
 
    for _ in range(rounds):
        a = random.randrange(2, n - 1)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True
 
 
def _generate_prime(bits: int):
    #return a random prime
    while True:
        candidate = random.getrandbits(bits) | (1 << bits - 1) | 1  # odd, top bit set
        if _is_prime(candidate):
            return candidate
 
 
def _mod_inverse(e: int, phi: int):
    #Extended Euclidean algorithm e^-1 mod phi.
    old_r, r = e, phi
    old_s, s = 1, 0
    while r != 0:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
    return old_s % phi
 
 
def _sha256_int(message: str):
    digest = hashlib.sha256(message.encode()).hexdigest()
    return int(digest, 16)
 
 
#wallet
#Holds a public/private RSA key pair and provides sign/verify methods.
#key_bits: size of each prime p and q (real RSA uses 1024+ per prime).
#Keep this at 512 for fast demo generation; use 1024 for realism.
#claude code signed ->

 
class Wallet:

 
    def __init__(self, key_bits: int = 512):
        self.public_key, self.private_key = self._generate_key_pair(key_bits)
        # Friendly "address" just the last 16 hex chars of the public key hash
        self.address = hashlib.sha256(
            str(self.public_key).encode()
        ).hexdigest()[-16:]
 
    # key generation 
 
    def _generate_key_pair(self, bits: int) -> tuple[tuple, tuple]:
        p = _generate_prime(bits)
        q = _generate_prime(bits)
        while q == p:
            q = _generate_prime(bits)
 
        n= p * q
        phi = (p - 1) * (q - 1)
        e= 65537 # standard public exponent
        d= _mod_inverse(e, phi)
 
        public_key  = (e, n)
        private_key = (d, n)
        return public_key, private_key
 
    # signing n verification 
    def sign(self, message: str):
        d, n = self.private_key
        msg_hash = _sha256_int(message) % n   # ensure hash < n
        return pow(msg_hash, d, n) # Python's built-in fast modexp
 
    def verify(self, message: str, signature: int) -> bool:

        e, n = self.public_key
        msg_hash = _sha256_int(message) % n
        decrypted = pow(signature, e, n)
        return decrypted == msg_hash
 
    def __repr__(self) -> str:
        e, n = self.public_key
        return f"Wallet(address={self.address}, e={e}, n_bits={n.bit_length()})"
 
 
# quick smoke test 
if __name__ == "__main__":
    print("Generating wallet (this takes a few seconds for prime generation)…")
    alice = Wallet(key_bits=512)
    print(f"Alice: {alice}\n")
 
    message = "Alice pays Bob 10 PyCoin"
    sig     = alice.sign(message)
    print(f"Message   : {message}")
    print(f"Signature : {str(sig)[:40]}…")
 
    valid = alice.verify(message, sig)
    print(f"\nSignature valid?  {valid}")
 
    # Tamper demo
    tampered = "Alice pays Eve 999 PyCoin"
    print(f"Tampered valid?   {alice.verify(tampered, sig)}")
 
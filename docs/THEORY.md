# KenazCoin theory

The ideas behind the code, explained like a human. Each section maps a
concept to the file that implements it.

## UTXO, unspent transaction outputs

There are no accounts in this coin. Money is a set of notes, and each note
is an output sitting on some address, waiting to be spent. Spending a note
means proving you own its public key, deleting it, and creating new notes
for whoever receives the money.

A `TxInput` is a reference to an old note, a transaction id plus an output
index. A `TxOutput` is a new note with an address and an amount. The UTXO
set is just a dictionary from input keys to outputs. Your balance is the
sum of every output in the set that points to your address.

When a transaction is applied, its inputs are deleted from the set and its
outputs are added. This lives in `utxo.py`.

## RSA wallets

A wallet is a pair of primes. The code generates two 512 bit primes, p and
q, multiplies them into n, and picks the standard exponent e = 65537. The
public key is (e, n). The private key is (d, n), where d is the modular
inverse of e.

To prove you own a key you sign the transaction id. You raise the hash to
the power d. Anyone can check by raising the signature to the power e. If
the results match, the signature is real. The address is the last 16 hex
characters of the SHA-256 of the public key.

The primes are found with the Miller Rabin test, a fast probabilistic
primality check. The `_generate_prime` function keeps making random odd
candidates with the top bit set until one passes the test. This lives in
`wallet.py`.

## Proof of work

To add a block you need a hash that starts with a certain number of zeros.
The only thing you can change is the nonce, so the miner tries nonce 0, 1,
2, and so on until a hash matches. Each extra zero multiplies the work by
about 16, because a zero appears by chance one in sixteen times.

The target is just the string "0" times the difficulty. The search and the
check live in `pow.py`.

## Difficulty adjustment

The chain aims for one block every 50 seconds. Every 5 blocks the node
looks at how long those 5 blocks actually took. If they were faster than
the target, the difficulty goes up. If slower, it goes down. The difficulty
stays between 1 and 5 so the search stays feasible in Python.

## Halving

The coinbase reward starts at 50 coins and halves every 100 blocks. After
100 blocks it is 25, after 200 it is 12, and so on. It never goes below 1.

## The merkle tree

A block can hold many transactions. Instead of putting all of them in the
header, the transactions are hashed in pairs, and those hashes are hashed
in pairs again, until one root hash remains. The block stores only this
root. Changing any transaction changes its hash, the hashes above it, and
the whole root, so one hash protects the entire list. If there is an odd
count, the last hash is duplicated. This lives in `merkletree.py`.

## The mempool

Transactions you create or receive go into the mempool until a miner puts
them in a block. The mempool rejects coinbase transactions, transactions
with a bad signature, and duplicates. It does not check the UTXO set, that
is the chain's job at mining time. This lives in `mempool.py`.

## Persistence

The chain is saved as a list of serialized blocks in `chain.json`. The UTXO
set is not saved. On load, the node clears everything, reads the blocks,
checks the whole chain with `is_valid()`, and rebuilds the UTXO set by
replaying every transaction. This way a tampered file cannot fake a
balance, because the balance is always a consequence of the history.

Wallets are saved as `wallet_<address>.json`. They can be plain or
encrypted. The encryption is an honest stdlib mix. The password becomes a
key with PBKDF2, 100 thousand rounds and a random salt. The data is XORed
with a keystream made of chained SHA-256 blocks, and an HMAC checksum makes
wrong passwords fail cleanly. It is not production crypto, it is honest
stdlib crypto. This lives in `persistence.py`.

## Networking

Nodes talk over TCP with JSON messages. Every message starts with a 4 byte
big endian length, so the receiver knows exactly how many bytes to read,
and TCP fragmentation is not a problem.

The messages are a small set. A handshake says hello and shares the chain
length. Blocks and peers are requested and answered. New transactions and
new blocks are broadcast. This lives in `message.py` and `node.py`.

When a node hears about another chain it compares work. A chain's work is
the sum of 16 to the power of the difficulty for each block. The chain with
more work wins. On a swap, the UTXO set is rebuilt from scratch. This
lives in `sync.py`.

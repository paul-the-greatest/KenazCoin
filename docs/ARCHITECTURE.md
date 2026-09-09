# KenazCoin architecture

This is the map of the toy cryptocurrency. It explains the modules, how a
wallet is created, how a transaction is built and signed, how a block is
mined, and how blocks and transactions travel between nodes.

## The one-line summary

KenazCoin is a proof of work cryptocurrency written with the Python
standard library only. It uses the UTXO model: there are no accounts, only
unspent outputs that belong to a public key. Wallets hold RSA keys and
prove ownership with signatures. A node keeps a chain of blocks in RAM,
persists it to disk, and talks to other nodes over TCP.

## The pieces

```
app/              entry points
  cli.py          interactive node with a command prompt
  main.py         quick demo script
core/             blockchain primitives
  wallet.py       RSA keys, sign and verify
  transaction.py  building, signing and serializing transactions
  utxo.py         TxInput, TxOutput, the UTXO set
  mempool.py      pool of pending transactions
  block.py        block structure and hashing
  merkletree.py   transaction summary for block headers
  pow.py          proof of work, the nonce search
  blockchain.py   chain, validation, mining, difficulty, halving
network/          P2P layer
  message.py      wire protocol, JSON over TCP with a length prefix
  node.py         TCP server and client, peer handling, broadcasting
  sync.py         applying blocks from peers, fork resolution
storage/          persistence
  persistence.py  save and load chain, wallets and peers
```

## The modules

| Module | File | Responsibility |
| --- | --- | --- |
| Wallet | `core/wallet.py` | Generates RSA keys, makes addresses, signs and verifies. |
| Transaction | `core/transaction.py` | Builds transfers and coinbases, signs them, serializes them. |
| UTXO set | `core/utxo.py` | Tracks every unspent output in the chain. |
| Mempool | `core/mempool.py` | Holds pending transactions until a miner picks them up. |
| Block | `core/block.py` | Block structure and SHA-256 hashing. |
| Merkle tree | `core/merkletree.py` | Turns a list of transactions into one root hash. |
| Proof of work | `core/pow.py` | Searches for a nonce that satisfies the target. |
| Blockchain | `core/blockchain.py` | The chain, validation, mining, difficulty, halving, chain swaps. |
| Wire protocol | `network/message.py` | Frames JSON messages over TCP. |
| Node | `network/node.py` | TCP server and client, peer loop, broadcasting, auto miner. |
| Sync | `network/sync.py` | Applies blocks from peers, resolves forks. |
| Persistence | `storage/persistence.py` | Saves and loads chain, wallets and peers. |

## How a transaction is born

1. The user types `send <address> <amount>` in the CLI.
2. `Transaction.new_transfer` looks at the sender's unspent outputs in the
   UTXO set and picks enough of them to cover the amount.
3. Each picked output becomes a `TxInput`. New `TxOutput`s are created for
   the receiver and, if there is change, for the sender.
4. The transaction signs its own `tx_id`, which is the hash of the inputs
   and outputs. The public key and the signature ride along.
5. The transaction goes into the local mempool and is broadcast to peers.

## How a block is mined

1. The miner pulls the pending transactions from the mempool, or takes an
   explicit list.
2. A coinbase transaction is created first. It pays the miner the block
   reward, which halves every 100 blocks.
3. Every transaction is checked. No double spends inside the block, no
   unknown inputs, outputs never exceed inputs.
4. The transactions are hashed into a merkle tree and the root goes into
   the block data.
5. Proof of work searches for a nonce that makes the block hash start with
   the required number of zeros. The higher the difficulty, the more zeros.
6. Once a valid nonce is found, the UTXO set is updated and the block is
   appended to the chain. Difficulty is retargeted every 5 blocks.

## How a block travels to a peer

1. The mining node broadcasts the block with a `NEW_BLOCK` message.
2. Each peer tries to append it. If the block's parent is the peer's last
   block, it is appended after the same checks a miner does.
3. If the parent is missing, the peer asks for a full sync. There are
   orphan helpers in the code, but the active path just resyncs instead.
4. If a peer advertises a heavier chain, the node swaps its own chain for
   the candidate and rebuilds the UTXO set from scratch.

## The boot sequence

1. `cli.py` adds `src/` to the path and calls the CLI `main()`.
2. The wallet is loaded or created. If there is no wallet yet, the CLI asks
   for a password and makes a new one.
3. The chain is loaded from disk. If the file is corrupt, it starts fresh.
4. The node opens a TCP server on the chosen port.
5. The node connects to the peers given with `--connect` and to the saved
   peers in `peers.json`.
6. The command loop starts. Commands run on the main thread. The server
   and the peer handlers run on daemon threads, and everything shared goes
   through `node._lock`.
7. On exit the chain and the peer list are saved.

## Import direction

The modules are careful about who imports whom, mostly to avoid cycles:

- `blockchain.py` imports from `block`, `merkletree`, `pow`,
  `transaction` and `utxo`. It imports `persistence` locally, inside
  `replace_chain`, so the two never clash at import time.
- `transaction.py` imports `wallet` and `utxo` at the top.
- `sync.py` imports `block`, `transaction` and `utxo` at the top. The node
  imports `sync` locally, inside the message handlers, so a broken sync
  module does not stop the node from booting.

## What maps to a real blockchain

| KenazCoin | Real world |
| --- | --- |
| `wallet.py` | A wallet with an RSA keypair and an address. |
| `transaction.py` and `utxo.py` | UTXO transactions and the UTXO set. |
| `mempool.py` | The mempool, pending transactions waiting for a block. |
| `block.py` and `pow.py` | The block structure and the proof of work puzzle. |
| `blockchain.py` | The chain, validation, difficulty adjustment, halving. |
| `merkletree.py` | The merkle tree that summarizes transactions. |
| `message.py` and `node.py` | The P2P network and its gossip. |
| `sync.py` | Block propagation and fork resolution. |
| `persistence.py` | Saving the chain and wallets to disk. |

## Design principles

- Stdlib only. No pip packages anywhere.
- Simplicity over correctness. The code is meant to be read and learned
  from, not to survive the real internet.
- The UTXO set is never saved. It is always rebuilt by replaying every
  transaction, so it can never drift from the chain.
- State is protected by one lock. The shared objects are `blockchain` and
  `mempool`, and every mutation goes through `node._lock`.
- Mining happens outside the lock, so a busy miner does not block the
  network threads.

## Known quirks

- `sync.py` defines `apply_blocks`, `_try_append`, `_request_full_sync`
  and a few helpers twice. The second definition wins. It is ugly but it
  works, so it stays. The orphan pool helpers exist, but the active code
  path requests a full resync when a parent is missing instead of storing
  orphans.
- The difficulty is not saved with the chain. When a node loads, it uses
  the `--difficulty` value from the command line, default 3. A chain mined
  with a lower difficulty will fail the integrity check if you load it with
  a higher one.
- The mempool rejects coinbase transactions. Coinbases are only created by
  miners, inside a block.
- `main.py` is a demo script. It is not a real node.

# NCoin

A cryptocurrency built from scratch using only the Python stdlib.

This is an educational project, focousing on how a pow cryptocurrency actually works. UTXO model, Proof-of-Work, P2P networking, Merkle trees, and all the pieces that make a blockchain tick. The code is deliberately simple and readable, not production-ready (not intended).

---

## Features

- **UTXO based transactions** (unspend transaction output) there are no direct accounts. it is calc on inputs, outputs, coinbase, change addresses
- **RSA wallets**  key generation, signing, verification (pure Python). The coins exist only into the blockchain, the wallet proves that you are the owner. 
In a utxo bc, every utxo belongs to a public key. to spend this utxo you need to prove that you have the private key. I recommend reading the RSA wikipedia article to understand. 
- **Proof of work mining** configurable difficulty. to add a block in the bc. the miner needs to prove that he spent enough "energy" or "power". The lowest the target, more initial zeros the hash has.
- **Difficulty adjustment** retargets every N blocks toward a target block time
- **Coinbase halving** reward halves every 100 blocks (by now, may increase it later)
- **Merkle tree** transaction summarization for block headers
- **Mempool** pending transaction pool, rejects invalid/duplicate txs.  
- **P2P network** TCP nodes with handshake, block/tx broadcast, peer discovery
- **Chain sync** automatic fork resolution via chain-work comparison, orphan pool
- **Persistence** save/load chain and wallets to disk with optional PBKDF2 encryption
- **Interactive CLI** wallet management, mining, sending coins, connecting peers (will be updated soon. not the optimal v)

---

## Quick Start

main.py is only a quick demo. I do not recommend running. 

# Interactive CLI node
python cli.py --port 5000
```

To test P2P, open multiple terminals:

```bash
# Terminal 1
python cli.py --port 5000

# Terminal 2 connects to the first node
python cli.py --port 5001 --connect 127.0.0.1:5000

# Terminal 3 also connects
python cli.py --port 5002 --connect 127.0.0.1:5000
```

Mine on one node, send coins on another. Blocks and transactions propagate automatically.

---

## CLI Commands

In the future, there will be more commands and features.  

| Command | Description |
|---|---|
| `balance` | Show your wallet balance |
| `send <addr> <amt>` | Send NCoin to an address |
| `mine` | Mine a block with mempool transactions |
| `autominer [stop]` | Start/stop background auto-miner |
| `connect <host> <port>` | Connect to a peer |
| `peers` | List connected peers |
| `chain` | Print the blockchain |
| `mempool` | Show pending transactions |
| `wallet` | Display current wallet info |
| `wallets` | List all saved wallets |
| `switch <address>` | Switch to another saved wallet |
| `new-wallet` | Create and switch to a new wallet |
| `utxos [address]` | Show UTXOs, optionally filter by address |
| `save` | Save chain to disk |
| `help` | Show this message |
| `exit` | Quit |

---

## Project layout

```
src/coin/
 app/            # Entry points
|    cli.py      # Interactive CLI node
│    main.py     # Quick demo script
| core/           # Blockchain primitives
│    block.py          # Block structure, SHA-256 hashing
│    blockchain.py     # Chain management, validation, mining, difficulty, halving
│    mempool.py        # Pending transaction pool
│    merkletree.py     # Merkle tree
│    pow.py            # Proof-of-Work (leading-zero target)
│    transaction.py    # UTXO transactions, signing, serialization
│    utxo.py           # TxInput, TxOutput, UTXO set
│    wallet.py         # RSA key generation, signing, verification
| network/         # P2P networking
│    message.py   # Wire protocol (JSON over TCP)
│    node.py      # TCP server + client, peer management
│    sync.py      # Chain sync, orphan pool, fork resolution
| storage/         # Persistence
     persistence.py  # Save/load chain, wallets (with optional encryption), peers
```

---

## How It Works

- **Wallets** generate RSA key pairs (512-bit primes). The address is derived from the public key last 16 hex chars of SHA-256(pubkey). Coins live in the blockchain as UTXOs; the wallet only proves ownership via signatures.
- **Transactions** consume existing UTXOs as inputs and create new UTXOs as outputs. Each input references a previous output and carries a signature from its owner. The blockchain validates that inputs exist, aren't double-spent, and cover the outputs.
- **Blocks** bundle transactions into a Merkle tree and are mined via Proof-of-Work find a nonce such that SHA-256(block) starts with N leading zeros. The first miner to find one gets the coinbase reward.
- **Mining** picks pending transactions from the mempool, builds a candidate block, and iterates nonces until a valid proof is found. The miner receives the block subsidy plus any transaction fees.
- **Difficulty** adjusts every 5 blocks based on actual mining time, targeting ~50 seconds per block. Caps at difficulty 5 to keep mining feasible in Python.
- **Network** uses TCP with a simple length-prefixed JSON protocol. Nodes exchange handshakes, blocks, transactions, and peer lists. Each node runs a TCP server and connects to known peers concurrently.
- **Chain sync** compares accumulated work (16^difficulty per block). When a peer advertises a heavier chain, the node replaces its local chain and rebuilds the UTXO set from scratch. An orphan pool handles out-of-order blocks.
- **Persistence** stores the chain as JSON. Wallets can be saved in plaintext or encrypted with a password using PBKDF2 key derivation and an XOR stream cipher.

---

## Dependencies

None. Python 3.10+ standard library only.

---

## Status

Educational project, still in development. Not intended for production use.

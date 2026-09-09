# KenazCoin user guide

How to run a node, use the commands, and play with a few nodes on the same
machine. Written for a human.

## Running

```bash
python cli.py --port 5000
```

On first run the CLI asks for a wallet password and creates a wallet. If
you already have wallets it lists them and asks which one to load.

To test the network, open several terminals:

```bash
# terminal 1
python cli.py --port 5000

# terminal 2 connects to the first node
python cli.py --port 5001 --connect 127.0.0.1:5000

# terminal 3 too
python cli.py --port 5002 --connect 127.0.0.1:5000
```

Mine on one node, send coins on another. Blocks and transactions propagate
by themselves.

Useful flags: `--port`, `--host`, `--connect`, `--wallet <address>`,
`--password <pw>`, `--difficulty <n>`.

## Command reference

| Command | What it does |
| --- | --- |
| `balance` | Show your balance. |
| `send <addr> <amt>` | Send NCoin to an address. |
| `mine` | Mine a block with the pending mempool transactions. |
| `autominer [stop]` | Start or stop a background miner. |
| `connect <host> <port>` | Connect to a peer. |
| `peers` | List connected peers. |
| `chain` | Print the chain. |
| `mempool` | Show pending transactions. |
| `wallet` | Show the current wallet. |
| `wallets` | List saved wallets. |
| `switch <address>` | Switch to another saved wallet. |
| `new-wallet` | Create a wallet and switch to it. |
| `utxos [address]` | Show the UTXO set, optionally for one address. |
| `save` | Save the chain to disk. |
| `help` | Show the help message. |
| `exit` | Save and quit. |

## A small demo, two nodes

Node A (port 5000) mines. Node B (port 5001) connects and receives.

```bash
# node A
python cli.py --port 5000 --difficulty 2
```

```bash
# node B, in another terminal
python cli.py --port 5001 --connect 127.0.0.1:5000 --difficulty 2
```

Start by mining on node A so the miner has coins to spend:

```
# node A
mine
balance          # shows the coinbase reward
```

Now get an address from node B, because that is who will receive:

```
# node B
wallet           # copy the address printed here
```

Back on node A, send some coins to that address:

```
# node A
send <B address> 5
```

The transaction is now in the mempool. It is not money yet, nobody has
mined it. Mine it:

```
# node A
mine
```

Node A broadcasts the new block, node B syncs it by itself, and now node B
owns the coins:

```
# node B
balance          # shows 5
```

Check node A's utxos to see the receiver note:

```
# node A
utxos
```

## Running it from inside nOS

KenazCoin is also published as a package for nOS, the toy operating system
in the folder next to this one. nOS installs it over HTTP from a small repo
server and runs it as a child process, so the node keeps running while you
type other nOS commands.

First, publish this repo from a terminal (the path is absolute, so point it
at wherever KenazCoin lives):

```bash
# in the nOS folder
python tools/repo_server.py --add kenazcoin /path/to/KenazCoin --port 9001
```

Then, inside nOS:

```
repo http://127.0.0.1:9001     # point nOS at the repo server
packages                       # kenazcoin shows in the catalog
install kenazcoin              # downloads and verifies the files
run kenazcoin --port 9002      # boots cli.py as its own process
log 1                          # watch it boot
talk 1 minhasenha              # answer the wallet password prompt
talk 1 balance                 # the coin CLI is now interactive
talk 1 autominer               # mine in the background
kill 1                         # stop the node
uninstall kenazcoin            # clean up
```

`run kenazcoin` starts the real `cli.py` as a process. `log` shows what the
node prints, `talk` sends it a line like typing into its terminal, and
`kill` closes it. To connect two nOS nodes, boot a second one with another
port and `run kenazcoin --port 9003 --connect 127.0.0.1:9002`.

## Good to know

- Blocks take a while. With difficulty 3 you can wait tens of seconds for a
  block. The demo above uses difficulty 2 to keep it fast.
- The genesis block, index 0, is created in memory and is never mined. It
  has no transactions and no reward.
- A transaction is not money until a miner puts it in a block. You can see
  it waiting with `mempool`.
- The chain and the wallets live in `~/.local/share/ncoin` on Linux, or
  `%APPDATA%\ncoin` on Windows. Peers are saved to `peers.json` in the
  folder where you run the node.
- `autominer` mines in the background so you do not have to stare at the
  prompt. Use `autominer stop` to stop it.
- `main.py` is a demo script only. Use `cli.py`.
- The CLI is not optimal and is expected to change.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| Mining takes forever | Lower the difficulty with `--difficulty 2`. |
| Balance stays zero after sending | The transaction is still in the mempool. Mine a block. |
| "Insufficient funds" | The wallet has no UTXOs covering the amount. Mine a block to earn coins. |
| Chain file corrupt | The CLI notices and starts fresh. |
| Node cannot connect to a peer | Both nodes must be reachable. Connect from the other side too. |
| Wrong wallet password | The load fails cleanly. Try the right password. |

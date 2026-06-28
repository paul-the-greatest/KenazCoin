import json
import struct

# the message types
 
HANDSHAKE  = "HANDSHAKE"  # first message on connect: share version + chain length
GET_BLOCKS = "GET_BLOCKS" # request blocks starting from a given index
BLOCKS = "BLOCKS"# response carrying a list of serialized blocks
NEW_TX = "NEW_TX"# broadcast a new transaction to peers
NEW_BLOCK = "NEW_BLOCK"  # broadcast a newly mined block to peers
GET_PEERS = "GET_PEERS"  # request the peers known peer list
PEERS = "PEERS"# response carrying a list of (host, port) pairs
 
# framing
# wire format [4-byte big-endian length][JSON payload]
# the length prefix lets the receiver know exactly how many bytes to read
# before attempting to parse, avoids TCP stream fragmentation issues
 
HEADER_SIZE = 4 # bytes for the length prefix
 
 
def encode(msg_type, payload=None):
    # builds a framed bytes object ready to send over a socket
    packet = json.dumps({
        "type": msg_type,
        "payload": payload or {},
    }, separators=(",", ":")).encode()
 
    header = struct.pack(">I", len(packet))  # >I = big-endian unsigned int
    return header + packet
 
 
def decode(raw):
    # parses a raw bytes object (without the header) into a dict
    return json.loads(raw.decode())
 

def read_message(sock):
    #reads exactly one message, blocking until complete
    # returns the decoded dict, or None if the connection was closed
    header = _recv_exact(sock, HEADER_SIZE)
    if header is None:
        return None
 
    length = struct.unpack(">I", header)[0]
    raw = _recv_exact(sock, length)
    if raw is None:
        return None
 
    return decode(raw)
 
 
def _recv_exact(sock, n):
    # reads exactly n bytes from sock TCP may deliver them in chunks
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf)) #se pedir 1000 bytes, mas so 200 forem enttreges, continua codigo
        if not chunk: #if chunk retornar vazio, o outro maquina desconectou
            return None  # connection closed cleanly
        buf += chunk
    return buf
 
 
# convenience constructors 
def make_handshake(host, port, chain_length):
    #
    return encode(HANDSHAKE, {"host": host, "port": port, "chain_length": chain_length})

def make_get_blocks(since_index):
    return encode(GET_BLOCKS, {"since_index": since_index})
 
def make_blocks(blocks_data):
    # blocks_data: list of block dicts (already serialized)
    return encode(BLOCKS, {"blocks": blocks_data})
 
def make_new_tx(tx_string):
    return encode(NEW_TX, {"tx": tx_string})
 
def make_new_block(block_data):
    return encode(NEW_BLOCK, {"block": block_data})
 
def make_get_peers():
    return encode(GET_PEERS)
 
def make_peers(peer_list):
    # peer_list: list of [host, port] pairs
    return encode(PEERS, {"peers": peer_list})
 
 
#  test 
 
if __name__ == "__main__":
    import socket
    import threading
 
    HOST, PORT = "127.0.0.1", 19999
 
    def server():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(1)
        conn, _ = srv.accept()
 
        msg = read_message(conn)
        print(f"[server] received: {msg}")
 
        # echo a PEERS response back
        conn.sendall(make_peers([["127.0.0.1", 20000], ["127.0.0.1", 20001]]))
        conn.close()
        srv.close()
 
    t = threading.Thread(target=server, daemon=True)
    t.start()
 
    # client side
    import time; time.sleep(0.1)  # let server start
 
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cli.connect((HOST, PORT))
    cli.sendall(make_handshake("127.0.0.1", 20000, chain_length=5))
 
    response = read_message(cli)
    print(f"[client] received: {response}")
    cli.close()

#utxo = unspent transaction output

class TxOutput:
    #chunk of coin sitting at some address, wait to be spent

    def __init__(self, address, amount):
        self.address = address
        self.amount = amount

    def to_dict(self):
        return {"address": self.address, "amount": self.amount}
        
    def __repr__(self):
        addr_short = f"{str(self.address)[:8]}..." if self.address else "None"
        return f"TxOutput(address='{addr_short}', amount={self.amount})"
    

class TxInput:
    #reference to a previous output being spent
 
    def __init__(self, tx_id, output_index):
        self.tx_id = tx_id
        self.output_index = output_index
 
    def to_dict(self):
        return {"tx_id": self.tx_id, "output_index": self.output_index}
 
    def key(self):
        #the lookup key used in the UTXO set
        return (self.tx_id, self.output_index)
 
    def __repr__(self):
        return f"TxInput(tx_id={self.tx_id[:8]}..., output_index={self.output_index})"
 
class UTXOSet:
    #tracks every unspent output across the whole chain
 
    def __init__(self):
        # key = (tx_id, output_index) -> TxOutput
        self.utxos = {}

    #querries

    def get_balance(self, address): #chekc if it is the right address
        total = 0
        for output in self.utxos.values(): #dict.values() method to extract values from dict
            if output.address == address:
                total += output.amount
        return total
 
    def get_spendable_outputs(self, address):
        #returns list of (key, TxOutput) owned by address
        result = []
        for key, output in self.utxos.items():
            if output.address == address:
                result.append((key, output))
        return result
 
    def is_unspent(self, tx_input):
        return tx_input.key() in self.utxos

    #mutations

    def apply_transaction(self, tx):
        #when its used, it is deleted
        for tx_input in tx.inputs:
            del self.utxos[tx_input.key()]
 
        tx_id = tx.tx_id()
        for index, output in enumerate(tx.outputs):
            self.utxos[(tx_id, index)] = output
 
    def apply_coinbase(self, tx):
        #coinbase has no inputs to consume, only adds outputs
        tx_id = tx.tx_id()
        for index, output in enumerate(tx.outputs):
            self.utxos[(tx_id, index)] = output
 
    def __repr__(self):
        #report
        lines = [f"UTXOSet ({len(self.utxos)} unspent outputs):"]
        for (tx_id, index), output in self.utxos.items():
            lines.append(f"  ({tx_id[:8]}..., {index}) -> {output}")
        return "\n".join(lines)

    #UTXOSet (2 unspent outputs):
    #(a1b2c3d4..., 0) -> TxOutput(address='0x999...', amount=5.0)
    #(f8e7d6c5..., 1) -> TxOutput(address='0x123...', amount=0.5
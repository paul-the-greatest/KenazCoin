coin

// MUST MAKE IT SOON

Fase 1 — Estado real
  ├── UTXO set: saldos derivados do histórico de txs (não saldo arbitrário)
  ├── Coinbase tx: o minerador recebe recompensa por bloco
  └── Validação de gasto: não pode gastar o que não tem / já gastou

Fase 2 — Persistência
  ├── Salvar/carregar chain do disco
  └── Serializar/deserializar wallets (chaves PEM ou JSON)

Fase 3 — Rede
  ├── Node class: servidor TCP/HTTP simples
  ├── Peer discovery: lista de peers conhecidos
  ├── Broadcast: propagar txs e blocos recebidos
  └── Sync: novo nó baixa a chain do peer mais longo

Fase 4 — Consenso robusto
  ├── Fork detection: detectar quando recebe bloco com mesmo index
  ├── Chain replacement: substituir pela chain com mais trabalho
  └── Orphan blocks: guardar blocos cujo pai ainda não chegou

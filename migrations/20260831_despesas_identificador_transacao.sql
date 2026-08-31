-- Identificador da transacao no comprovante (E2E do Pix, numero do documento).
--
-- Serve para uma coisa so, e vale ser preciso: **comprovante repetido**. O
-- `comprovante_path` carrega timestamp e sufixo aleatorio, entao a mesma foto
-- mandada duas vezes gera dois caminhos diferentes e duas despesas. O E2E e o
-- unico dado do comprovante que se repete quando o documento e o mesmo.
--
-- Ele NAO desambigua comprovante contra nota fiscal: a nota nao tem E2E. Quem
-- faz isso e o CNPJ do recebedor, que nao precisa de coluna -- e comparado com
-- `giardini_estoque.fornecedores.cnpj` na hora do casamento.
--
-- Aditivo: coluna nula, nenhuma consulta existente muda de resultado. O indice
-- e parcial porque comprovante sem identificador legivel continua entrando --
-- so nao ganha a protecao.

ALTER TABLE giardini_financeiro.despesas
  ADD COLUMN IF NOT EXISTS identificador_transacao text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_despesas_identificador_transacao
  ON giardini_financeiro.despesas (identificador_transacao)
  WHERE identificador_transacao IS NOT NULL;

COMMENT ON COLUMN giardini_financeiro.despesas.identificador_transacao IS
  'E2E do Pix ou numero do documento, extraido do comprovante. Chave de '
  'idempotencia contra o mesmo comprovante enviado duas vezes.';

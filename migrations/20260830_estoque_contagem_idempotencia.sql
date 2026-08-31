-- Adendo ao 20260830_estoque_schema.sql.
--
-- POR QUE
--   A regra de idempotencia vale para toda operacao de escrita: compra pela
--   chave da NFC-e, documento pelo hash, movimento pela chave deterministica.
--   Contagem tinha ficado de fora -- sem chave, reenviar a mesma requisicao
--   criaria uma segunda contagem com os mesmos numeros.
--
--   Anulavel de proposito: contagem lancada pela mao no banco nao precisa de
--   chave, e o indice unico so vale onde ela existe.
--
-- Pode rodar junto com o schema ou depois; e aditivo e independente.

ALTER TABLE giardini_estoque.contagens
    ADD COLUMN IF NOT EXISTS chave_idempotencia text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_contagens_idempotencia
    ON giardini_estoque.contagens (chave_idempotencia)
    WHERE chave_idempotencia IS NOT NULL;

COMMENT ON COLUMN giardini_estoque.contagens.chave_idempotencia IS
    'Chave enviada por quem registra a contagem. Repetir a requisicao com a '
    'mesma chave devolve a contagem existente em vez de criar outra.';

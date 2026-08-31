-- Grava o identificador de produto do PDV no item de venda.
--
-- POR QUE
--   giardini_financeiro.receitas_transacao_itens nao tem identificador de produto:
--   so product_name, texto. A API do Eyemobile devolve product_id em 100% dos itens
--   (medido em 1.209 itens de 7 dias), e a sincronizacao descartava esse campo.
--
--   O nome nao serve de chave. No historico completo (43.238 linhas, 02/01 a 30/08)
--   ha 180 nomes distintos e apenas 171 depois de normalizar espacos: nove produtos
--   ja existem sob duas grafias ("FRANGO" e "FRANGO ", " ESPRESSO" e "ESPRESSO",
--   espaco duplo em "TAPIOCA OVOS CREMOSOS  FATIAS DE BACON"). Uma ficha tecnica
--   presa ao nome deixaria de baixar estoque em parte das vendas, sem erro nenhum.
--
--   sku vem sempre nulo e product_parent_id tambem: product_id e a unica chave estavel.
--
-- EFEITO SOBRE O QUE EXISTE
--   Nenhum. Colunas novas e anulaveis. Nenhuma consulta atual muda de resultado --
--   nem o relatorio diario, nem a Julia, nem o julia_consulta. O historico fica com
--   NULL ate um backfill, que e decisao separada.
--
-- DEPOIS DESTE ARQUIVO
--   O no receita_transacao_itens do workflow inserção_receitas passa a popular as
--   duas colunas. Sem essa mudanca no n8n as colunas ficam nulas para sempre.

ALTER TABLE giardini_financeiro.receitas_transacao_itens
    ADD COLUMN IF NOT EXISTS eye_product_id       text,
    ADD COLUMN IF NOT EXISTS eye_product_group_id text;

COMMENT ON COLUMN giardini_financeiro.receitas_transacao_itens.eye_product_id IS
    'product_id do item no PDV Eyemobile. Chave estavel do produto do cardapio; '
    'e por ela que giardini_estoque.ficha_tecnica se liga a venda. '
    'NULL nas linhas anteriores a 30/08/2026.';

COMMENT ON COLUMN giardini_financeiro.receitas_transacao_itens.eye_product_group_id IS
    'product_group_id do item no PDV Eyemobile. Agrupamento de cardapio, guardado '
    'para analise; nao e usado como chave.';

CREATE INDEX IF NOT EXISTS idx_receitas_itens_eye_product_id
    ON giardini_financeiro.receitas_transacao_itens (eye_product_id)
    WHERE eye_product_id IS NOT NULL;

-- Conferencia:
--
--   SELECT count(*) FILTER (WHERE eye_product_id IS NOT NULL) AS com_id,
--          count(*)                                          AS total
--   FROM giardini_financeiro.receitas_transacao_itens
--   WHERE transaction_time >= now() - interval '1 day';
--
-- Antes da proxima sincronizacao: com_id = 0.
-- Depois: com_id cresce a cada rodada do inserção_receitas (a cada 15 min, 7h-22h).

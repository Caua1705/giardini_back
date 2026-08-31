-- Dominio de estoque: schema, tipos, tabelas, gatilhos, indices e visao de saldo.
--
-- Modelo revisado e aprovado em 30/08/2026. O desenho e o porque de cada decisao
-- estao em giardini_n8n/docs/ESTOQUE.md.
--
-- COMO RODAR
--   Cole inteiro no SQL Editor do Supabase. E idempotente onde da (IF NOT EXISTS),
--   mas nao foi feito para rodar duas vezes: se falhar no meio, corrija e rode do
--   comeco numa base limpa, ou apague o schema com
--     DROP SCHEMA giardini_estoque CASCADE;
--   ATENCAO: esse DROP so e seguro enquanto nao houver dado.
--
-- ORDEM
--   As tabelas estao na ordem de dependencia. estoque_movimentos vem por ultimo
--   porque referencia compras_itens, contagens_itens e ficha_tecnica.

CREATE SCHEMA IF NOT EXISTS giardini_estoque;


-- ============================================================================
-- TIPOS
-- ============================================================================

-- Unidade em que o saldo e contado. Deliberadamente minima: tudo o que a nota
-- trouxer (CX, FD, PCT, KG, L) e convertido para uma destas pelo fator.
CREATE TYPE giardini_estoque.unidade_base AS ENUM ('UN', 'G', 'ML');

CREATE TYPE giardini_estoque.status_mapeamento  AS ENUM ('confirmado', 'sugerido', 'rejeitado');
CREATE TYPE giardini_estoque.origem_mapeamento  AS ENUM ('humano', 'ia', 'importacao');
CREATE TYPE giardini_estoque.status_compra      AS ENUM ('rascunho', 'revisao', 'aprovada', 'lancada', 'cancelada');
CREATE TYPE giardini_estoque.status_item_compra AS ENUM ('mapeado', 'precisa_mapeamento', 'ignorado');
CREATE TYPE giardini_estoque.tipo_movimento     AS ENUM ('compra', 'consumo', 'perda', 'ajuste_contagem');
CREATE TYPE giardini_estoque.tipo_documento     AS ENUM ('nfce', 'comprovante', 'outro');
CREATE TYPE giardini_estoque.status_documento   AS ENUM ('recebido', 'processado', 'erro', 'ignorado');
CREATE TYPE giardini_estoque.status_contagem    AS ENUM ('aberta', 'fechada', 'cancelada');


-- ============================================================================
-- FUNCOES DE GATILHO
-- ============================================================================

CREATE OR REPLACE FUNCTION giardini_estoque.toca_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Mapeamento e versionado: corrigir e fechar a linha vigente com valid_to e
-- inserir outra. Sobrescrever o fator reescreveria o custo de compras antigas.
--
-- ESCOTILHA: gatilho no Postgres dispara para qualquer role, inclusive o dono da
-- tabela e o superusuario -- nao ha privilegio que pule isto. Para correcao a mao,
-- declare a intencao dentro da transacao:
--
--   BEGIN;
--     SET LOCAL giardini.correcao_manual = 'on';
--     UPDATE giardini_estoque.mapeamento_fornecedor SET ... WHERE id = '...';
--   COMMIT;
--
-- O SET LOCAL morre no COMMIT: e impossivel esquecer a porta aberta. O backend
-- nunca seta essa variavel, entao para ele o bloqueio e absoluto.
CREATE OR REPLACE FUNCTION giardini_estoque.mapeamento_imutavel()
RETURNS trigger AS $$
BEGIN
    IF current_setting('giardini.correcao_manual', true) = 'on' THEN
        RETURN NEW;
    END IF;

    IF NEW.fornecedor_id   IS DISTINCT FROM OLD.fornecedor_id
    OR NEW.codigo_fiscal   IS DISTINCT FROM OLD.codigo_fiscal
    OR NEW.insumo_id       IS DISTINCT FROM OLD.insumo_id
    OR NEW.fator_conversao IS DISTINCT FROM OLD.fator_conversao
    OR NEW.unidade_fiscal  IS DISTINCT FROM OLD.unidade_fiscal
    OR NEW.valid_from      IS DISTINCT FROM OLD.valid_from THEN
        RAISE EXCEPTION
            'mapeamento_fornecedor e versionado: feche a linha vigente com valid_to e '
            'insira outra. Para corrigir a mao: SET LOCAL giardini.correcao_manual = ''on''';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Movimento de estoque e append-only: erro se corrige com movimento contrario,
-- nunca apagando. Mesma escotilha por transacao.
CREATE OR REPLACE FUNCTION giardini_estoque.movimento_append_only()
RETURNS trigger AS $$
BEGIN
    IF current_setting('giardini.correcao_manual', true) = 'on' THEN
        RETURN COALESCE(NEW, OLD);   -- NEW e NULL em DELETE
    END IF;

    RAISE EXCEPTION
        'estoque_movimentos e append-only: registre um ajuste_contagem com sinal '
        'contrario. Para corrigir a mao: SET LOCAL giardini.correcao_manual = ''on''';
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- 1. insumos
-- ============================================================================

CREATE TABLE giardini_estoque.insumos (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- slug interno estavel: e por ele que a planilha de ficha tecnica se liga,
    -- para que corrigir o `nome` nao quebre a importacao.
    codigo         text NOT NULL UNIQUE,
    nome           text NOT NULL,
    categoria      text,
    unidade_base   giardini_estoque.unidade_base NOT NULL,
    estoque_minimo numeric(14,4) CHECK (estoque_minimo IS NULL OR estoque_minimo >= 0),
    perecivel      boolean NOT NULL DEFAULT false,
    validade_dias  integer CHECK (validade_dias IS NULL OR validade_dias > 0),
    ativo          boolean NOT NULL DEFAULT true,
    observacao     text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_insumos_categoria ON giardini_estoque.insumos (categoria) WHERE ativo;
CREATE INDEX idx_insumos_nome      ON giardini_estoque.insumos (lower(nome));

CREATE TRIGGER trg_insumos_updated_at BEFORE UPDATE ON giardini_estoque.insumos
    FOR EACH ROW EXECUTE FUNCTION giardini_estoque.toca_updated_at();


-- ============================================================================
-- 2. fornecedores
-- ============================================================================

CREATE TABLE giardini_estoque.fornecedores (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cnpj          text CHECK (cnpj IS NULL OR cnpj ~ '^[0-9]{14}$'),  -- so digitos
    razao_social  text NOT NULL,
    nome_fantasia text,
    ativo         boolean NOT NULL DEFAULT true,
    observacao    text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- CNPJ e unico quando existe; feira e fornecedor informal entram sem.
CREATE UNIQUE INDEX uq_fornecedores_cnpj ON giardini_estoque.fornecedores (cnpj)
    WHERE cnpj IS NOT NULL;

CREATE TRIGGER trg_fornecedores_updated_at BEFORE UPDATE ON giardini_estoque.fornecedores
    FOR EACH ROW EXECUTE FUNCTION giardini_estoque.toca_updated_at();


-- ============================================================================
-- 3. mapeamento_fornecedor  (versionado)
-- ============================================================================
-- "Ovos Emape Film Verm, 1 UN" -> 30 unidades do insumo 'ovo-un'.
-- fator_conversao = quantidade na unidade base por 1 unidade fiscal.

CREATE TABLE giardini_estoque.mapeamento_fornecedor (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fornecedor_id    uuid NOT NULL REFERENCES giardini_estoque.fornecedores(id),
    codigo_fiscal    text NOT NULL,
    descricao_fiscal text,          -- literal da nota, para conferencia humana
    gtin             text,          -- quando a nota traz; cruza fornecedores
    insumo_id        uuid NOT NULL REFERENCES giardini_estoque.insumos(id),
    unidade_fiscal   text NOT NULL,
    fator_conversao  numeric(14,4) NOT NULL CHECK (fator_conversao > 0),
    status           giardini_estoque.status_mapeamento NOT NULL DEFAULT 'sugerido',
    origem           giardini_estoque.origem_mapeamento NOT NULL DEFAULT 'humano',
    valid_from       timestamptz NOT NULL DEFAULT now(),
    valid_to         timestamptz,
    confirmado_por   text,
    confirmado_em    timestamptz,
    observacao       text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    -- IA sugere, humano confirma. Sem quem confirmou, nao existe confirmado.
    CHECK (status <> 'confirmado' OR confirmado_por IS NOT NULL)
);

-- No maximo UM mapeamento confirmado vigente por (fornecedor, codigo).
CREATE UNIQUE INDEX uq_mapeamento_vigente
    ON giardini_estoque.mapeamento_fornecedor (fornecedor_id, codigo_fiscal)
    WHERE valid_to IS NULL AND status = 'confirmado';

CREATE INDEX idx_mapeamento_busca
    ON giardini_estoque.mapeamento_fornecedor (fornecedor_id, codigo_fiscal, status);
CREATE INDEX idx_mapeamento_insumo ON giardini_estoque.mapeamento_fornecedor (insumo_id);
CREATE INDEX idx_mapeamento_gtin   ON giardini_estoque.mapeamento_fornecedor (gtin)
    WHERE gtin IS NOT NULL;

CREATE TRIGGER trg_mapeamento_imutavel BEFORE UPDATE
    ON giardini_estoque.mapeamento_fornecedor
    FOR EACH ROW EXECUTE FUNCTION giardini_estoque.mapeamento_imutavel();


-- ============================================================================
-- 4. documentos
-- ============================================================================
-- hash unico e a primeira barreira contra processar o mesmo arquivo duas vezes.
-- Vale mesmo quando a nota ainda nao foi lida e a chave e desconhecida.

CREATE TABLE giardini_estoque.documentos (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    hash_sha256   text NOT NULL UNIQUE CHECK (hash_sha256 ~ '^[0-9a-f]{64}$'),
    tipo          giardini_estoque.tipo_documento NOT NULL,
    nome_arquivo  text,
    mime          text,
    tamanho_bytes integer CHECK (tamanho_bytes IS NULL OR tamanho_bytes >= 0),
    storage_path  text,
    chave_nfe     text CHECK (chave_nfe IS NULL OR chave_nfe ~ '^[0-9]{44}$'),
    status        giardini_estoque.status_documento NOT NULL DEFAULT 'recebido',
    erro          text,
    recebido_em   timestamptz NOT NULL DEFAULT now(),
    processado_em timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_documentos_chave_nfe ON giardini_estoque.documentos (chave_nfe)
    WHERE chave_nfe IS NOT NULL;
CREATE INDEX idx_documentos_status ON giardini_estoque.documentos (status, recebido_em DESC);


-- ============================================================================
-- 5. compras
-- ============================================================================

CREATE TABLE giardini_estoque.compras (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    documento_id   uuid REFERENCES giardini_estoque.documentos(id),
    fornecedor_id  uuid NOT NULL REFERENCES giardini_estoque.fornecedores(id),
    chave_nfe      text CHECK (chave_nfe IS NULL OR chave_nfe ~ '^[0-9]{44}$'),
    numero_nota    text,
    serie          text,
    emitida_em     timestamptz,
    valor_total    numeric(14,2) NOT NULL DEFAULT 0 CHECK (valor_total >= 0),
    valor_desconto numeric(14,2) NOT NULL DEFAULT 0 CHECK (valor_desconto >= 0),
    status         giardini_estoque.status_compra NOT NULL DEFAULT 'rascunho',
    lancada_em     timestamptz,
    -- Vinculo com a despesa avulsa da mesma compra, para nota e comprovante nao
    -- virarem dois lancamentos. despesas.id e integer, nao uuid.
    despesa_id     integer REFERENCES giardini_financeiro.despesas(id),
    observacao     text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CHECK (status <> 'lancada' OR lancada_em IS NOT NULL)
);

-- Chave de idempotencia da compra: reenviar a mesma nota nao cria uma segunda.
-- Compra manual (feira) entra com chave nula e nao colide.
CREATE UNIQUE INDEX uq_compras_chave_nfe ON giardini_estoque.compras (chave_nfe)
    WHERE chave_nfe IS NOT NULL;

CREATE INDEX idx_compras_fornecedor_data
    ON giardini_estoque.compras (fornecedor_id, emitida_em DESC);
CREATE INDEX idx_compras_status ON giardini_estoque.compras (status);
CREATE INDEX idx_compras_despesa ON giardini_estoque.compras (despesa_id)
    WHERE despesa_id IS NOT NULL;

CREATE TRIGGER trg_compras_updated_at BEFORE UPDATE ON giardini_estoque.compras
    FOR EACH ROW EXECUTE FUNCTION giardini_estoque.toca_updated_at();


-- ============================================================================
-- 6. compras_itens
-- ============================================================================

CREATE TABLE giardini_estoque.compras_itens (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    compra_id           uuid NOT NULL REFERENCES giardini_estoque.compras(id) ON DELETE CASCADE,
    ordem               integer NOT NULL CHECK (ordem > 0),

    -- o que a nota diz, literal, sem interpretacao
    descricao_fiscal    text NOT NULL,
    codigo_fiscal       text,
    ncm                 text,
    cfop                text,
    gtin                text,
    quantidade_fiscal   numeric(14,4) NOT NULL CHECK (quantidade_fiscal > 0),
    unidade_fiscal      text NOT NULL,
    valor_unitario      numeric(14,4) NOT NULL CHECK (valor_unitario >= 0),
    valor_total         numeric(14,2) NOT NULL CHECK (valor_total >= 0),

    -- o que a gente entendeu, se entendeu
    insumo_id           uuid REFERENCES giardini_estoque.insumos(id),
    mapeamento_id       uuid REFERENCES giardini_estoque.mapeamento_fornecedor(id),
    fator_aplicado      numeric(14,4) CHECK (fator_aplicado IS NULL OR fator_aplicado > 0),
    quantidade_base     numeric(14,4) CHECK (quantidade_base IS NULL OR quantidade_base > 0),
    custo_unitario_base numeric(14,4) CHECK (custo_unitario_base IS NULL OR custo_unitario_base >= 0),
    status              giardini_estoque.status_item_compra NOT NULL DEFAULT 'precisa_mapeamento',
    created_at          timestamptz NOT NULL DEFAULT now(),

    -- Item mapeado tem que estar completo; item pendente nao pode ter quantidade
    -- base. E o banco garantindo que item sem mapeamento nao gera movimento.
    CHECK (
        (status = 'mapeado'
            AND insumo_id IS NOT NULL AND mapeamento_id IS NOT NULL
            AND fator_aplicado IS NOT NULL AND quantidade_base IS NOT NULL)
        OR
        (status <> 'mapeado' AND quantidade_base IS NULL)
    )
);

-- Faz o registro dos N itens ser reexecutavel sem duplicar.
CREATE UNIQUE INDEX uq_compras_itens_ordem ON giardini_estoque.compras_itens (compra_id, ordem);

CREATE INDEX idx_compras_itens_insumo ON giardini_estoque.compras_itens (insumo_id);
CREATE INDEX idx_compras_itens_codigo ON giardini_estoque.compras_itens (codigo_fiscal);
CREATE INDEX idx_compras_itens_pendentes ON giardini_estoque.compras_itens (compra_id)
    WHERE status = 'precisa_mapeamento';


-- ============================================================================
-- 7. ficha_tecnica  (versionada)
-- ============================================================================
-- eye_product_id e a ligacao com a venda: product_id do PDV Eyemobile, gravado
-- em giardini_financeiro.receitas_transacao_itens.eye_product_id.
-- Ver docs/ESTOQUE.md secao A para por que nao e o nome do produto.

CREATE TABLE giardini_estoque.ficha_tecnica (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    eye_product_id text NOT NULL,
    nome_produto   text NOT NULL,   -- snapshot legivel; nao e chave
    rendimento     numeric(14,4) NOT NULL DEFAULT 1 CHECK (rendimento > 0),
    versao         integer NOT NULL DEFAULT 1 CHECK (versao > 0),
    valid_from     timestamptz NOT NULL DEFAULT now(),
    valid_to       timestamptz,
    observacao     text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);

-- Uma ficha vigente por produto. Mudar a receita em setembro nao pode mudar o
-- CMV de agosto: fecha-se a vigente e insere-se outra versao.
CREATE UNIQUE INDEX uq_ficha_vigente ON giardini_estoque.ficha_tecnica (eye_product_id)
    WHERE valid_to IS NULL;
CREATE INDEX idx_ficha_produto ON giardini_estoque.ficha_tecnica (eye_product_id);


CREATE TABLE giardini_estoque.ficha_tecnica_itens (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ficha_tecnica_id uuid NOT NULL REFERENCES giardini_estoque.ficha_tecnica(id) ON DELETE CASCADE,
    insumo_id        uuid NOT NULL REFERENCES giardini_estoque.insumos(id),
    quantidade_base  numeric(14,4) NOT NULL CHECK (quantidade_base > 0),
    -- rendimento liquido: a cebola que vira 80% de cebola picada
    perda_percentual numeric(14,4) NOT NULL DEFAULT 0
                       CHECK (perda_percentual >= 0 AND perda_percentual < 100),
    observacao       text
);

CREATE UNIQUE INDEX uq_ficha_item
    ON giardini_estoque.ficha_tecnica_itens (ficha_tecnica_id, insumo_id);
CREATE INDEX idx_ficha_item_insumo ON giardini_estoque.ficha_tecnica_itens (insumo_id);


-- ============================================================================
-- 8. contagens
-- ============================================================================

CREATE TABLE giardini_estoque.contagens (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    realizada_em timestamptz NOT NULL,
    responsavel  text NOT NULL,
    status       giardini_estoque.status_contagem NOT NULL DEFAULT 'aberta',
    fechada_em   timestamptz,
    observacao   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CHECK (status <> 'fechada' OR fechada_em IS NOT NULL)
);

CREATE INDEX idx_contagens_data ON giardini_estoque.contagens (realizada_em DESC);


CREATE TABLE giardini_estoque.contagens_itens (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contagem_id        uuid NOT NULL REFERENCES giardini_estoque.contagens(id) ON DELETE CASCADE,
    insumo_id          uuid NOT NULL REFERENCES giardini_estoque.insumos(id),
    quantidade_contada numeric(14,4) NOT NULL CHECK (quantidade_contada >= 0),
    quantidade_sistema numeric(14,4),   -- snapshot no fechamento
    diferenca          numeric(14,4) GENERATED ALWAYS AS
                         (quantidade_contada - quantidade_sistema) STORED,
    observacao         text
);

CREATE UNIQUE INDEX uq_contagem_item ON giardini_estoque.contagens_itens (contagem_id, insumo_id);
CREATE INDEX idx_contagem_item_insumo ON giardini_estoque.contagens_itens (insumo_id);


-- ============================================================================
-- 9. estoque_movimentos  (append-only)
-- ============================================================================

CREATE TABLE giardini_estoque.estoque_movimentos (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    insumo_id       uuid NOT NULL REFERENCES giardini_estoque.insumos(id),
    tipo            giardini_estoque.tipo_movimento NOT NULL,

    -- Assinada: entrada positiva, saida negativa. saldo = SUM(quantidade_base).
    quantidade_base numeric(14,4) NOT NULL CHECK (quantidade_base <> 0),

    -- SNAPSHOT do que valia no momento, nao referencia que pode mudar depois.
    -- Se amanha a caixa passar a ter 36 ovos, os movimentos antigos continuam
    -- dizendo 30 -- que e o que realmente entrou.
    unidade_base    giardini_estoque.unidade_base NOT NULL,
    fator_usado     numeric(14,4) CHECK (fator_usado IS NULL OR fator_usado > 0),
    custo_unitario  numeric(14,4) CHECK (custo_unitario IS NULL OR custo_unitario >= 0),
    valor_total     numeric(14,2),

    -- de onde veio
    compra_item_id   uuid REFERENCES giardini_estoque.compras_itens(id),
    contagem_item_id uuid REFERENCES giardini_estoque.contagens_itens(id),
    ficha_tecnica_id uuid REFERENCES giardini_estoque.ficha_tecnica(id),
    consumo_dia      date,
    eye_product_id   text,

    ocorreu_em      timestamptz NOT NULL,
    observacao      text,

    -- Chave deterministica por operacao. Rodar o baixa_estoque duas vezes no
    -- mesmo dia nao baixa duas vezes; reenviar a nota nao soma de novo.
    --   compra:<compra_item_id>
    --   consumo:<dia>:<eye_product_id>:<insumo_id>
    --   contagem:<contagem_item_id>
    --   perda:<uuid da requisicao>
    chave_idempotencia text NOT NULL UNIQUE,
    created_at      timestamptz NOT NULL DEFAULT now(),

    CHECK (tipo <> 'compra'  OR quantidade_base > 0),
    CHECK (tipo <> 'consumo' OR quantidade_base < 0),
    CHECK (tipo <> 'perda'   OR quantidade_base < 0)
    -- ajuste_contagem aceita os dois sinais, de proposito
);

CREATE INDEX idx_mov_insumo_data ON giardini_estoque.estoque_movimentos (insumo_id, ocorreu_em DESC);
CREATE INDEX idx_mov_tipo_data   ON giardini_estoque.estoque_movimentos (tipo, ocorreu_em DESC);
CREATE INDEX idx_mov_consumo_dia ON giardini_estoque.estoque_movimentos (consumo_dia)
    WHERE consumo_dia IS NOT NULL;
CREATE INDEX idx_mov_compra_item ON giardini_estoque.estoque_movimentos (compra_item_id)
    WHERE compra_item_id IS NOT NULL;

CREATE TRIGGER trg_movimento_append_only BEFORE UPDATE OR DELETE
    ON giardini_estoque.estoque_movimentos
    FOR EACH ROW EXECUTE FUNCTION giardini_estoque.movimento_append_only();


-- ============================================================================
-- 10. visao de saldo
-- ============================================================================
-- Cobertura em dias nao entra aqui: a janela de consumo medio e decisao da rota
-- do backend, nao do schema.

CREATE VIEW giardini_estoque.v_saldo_insumo AS
SELECT i.id           AS insumo_id,
       i.codigo,
       i.nome,
       i.categoria,
       i.unidade_base,
       i.estoque_minimo,
       COALESCE(SUM(m.quantidade_base), 0)                 AS saldo,
       MAX(m.ocorreu_em) FILTER (WHERE m.tipo = 'compra')  AS ultima_compra,
       MAX(m.ocorreu_em) FILTER (WHERE m.tipo = 'consumo') AS ultimo_consumo
FROM giardini_estoque.insumos i
LEFT JOIN giardini_estoque.estoque_movimentos m ON m.insumo_id = i.id
WHERE i.ativo
GROUP BY i.id, i.codigo, i.nome, i.categoria, i.unidade_base, i.estoque_minimo;


-- ============================================================================
-- 11. leitura para a julia_ro
-- ============================================================================
-- Somente SELECT. Toda escrita passa pelo backend.
-- RLS nao e habilitada: giardini_estoque nao e exposto via PostgREST. Se um dia
-- for, habilitar RLS aqui deixa de ser opcional.

GRANT USAGE ON SCHEMA giardini_estoque TO julia_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA giardini_estoque TO julia_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA giardini_estoque GRANT SELECT ON TABLES TO julia_ro;


-- ============================================================================
-- CONFERENCIA
-- ============================================================================
--
--   SELECT table_name FROM information_schema.tables
--   WHERE table_schema = 'giardini_estoque' ORDER BY 1;
--   -- 10 tabelas + v_saldo_insumo
--
--   SELECT tgname, tgrelid::regclass FROM pg_trigger
--   WHERE NOT tgisinternal AND tgrelid::regclass::text LIKE 'giardini_estoque%';
--   -- trg_insumos_updated_at, trg_fornecedores_updated_at, trg_compras_updated_at,
--   -- trg_mapeamento_imutavel, trg_movimento_append_only
--
--   SELECT has_schema_privilege('julia_ro','giardini_estoque','USAGE'),
--          has_table_privilege('julia_ro','giardini_estoque.insumos','SELECT'),
--          has_table_privilege('julia_ro','giardini_estoque.insumos','INSERT');
--   -- true, true, false

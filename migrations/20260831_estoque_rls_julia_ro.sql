-- Leitura da julia_ro no schema de estoque.
--
-- As 11 tabelas de giardini_estoque nasceram com RLS ligado e sem politica
-- nenhuma. O GRANT de SELECT ja existia, entao a julia_ro nao tomava erro de
-- permissao: ela simplesmente enxergava ZERO linha, em toda tabela, para
-- sempre. E o mesmo silencio que o giardini_site produziu antes.
--
-- Isso e pior do que um erro. As cinco rotas de leitura de estoque passam pelo
-- backend, com a credencial dele, e respondem certo; mas o `consultar_banco` da
-- Julia -- SQL direto pela julia_ro -- responderia "nao ha nada no estoque" com
-- cara de verdade, sem nada no log.
--
-- Politica identica a que ja vale em giardini_financeiro.receitas_transacoes e
-- receitas_transacao_itens: SELECT, para a role julia_ro, sem filtro de linha.
-- A restricao de escrita continua sendo o GRANT, que so da SELECT -- politica
-- de leitura nao afrouxa isso.
--
-- Idempotente: rodar de novo nao quebra.

DO $$
DECLARE
  tabela text;
  tabelas text[] := ARRAY[
    'compras',
    'compras_itens',
    'contagens',
    'contagens_itens',
    'documentos',
    'estoque_movimentos',
    'ficha_tecnica',
    'ficha_tecnica_itens',
    'fornecedores',
    'insumos',
    'mapeamento_fornecedor'
  ];
BEGIN
  FOREACH tabela IN ARRAY tabelas LOOP
    EXECUTE format(
      'DROP POLICY IF EXISTS julia_ro_leitura ON giardini_estoque.%I', tabela);
    EXECUTE format(
      'CREATE POLICY julia_ro_leitura ON giardini_estoque.%I '
      'FOR SELECT TO julia_ro USING (true)', tabela);
  END LOOP;
END $$;

-- Conferencia. Tem que devolver 11 linhas, uma por tabela.
--
--   SELECT tablename, policyname, cmd, roles::text
--     FROM pg_policies
--    WHERE schemaname = 'giardini_estoque'
--    ORDER BY tablename;
--
-- E, conectado como julia_ro, `SELECT count(*) FROM giardini_estoque.compras`
-- tem que parar de devolver 0 quando houver compra registrada.

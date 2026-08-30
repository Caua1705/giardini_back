-- Confirmacao de reserva por WhatsApp: dois estados novos no ciclo de vida.
--
--   confirmed --(lembrete enviado)--> reminded --+--> reconfirmed
--                                                +--> cancelled
--
-- Estado do enum ANTES desta migracao (consultado em 30/08/2026):
--   confirmed, cancelled, completed, no_show
--
-- COMO APLICAR
--   Rode os dois comandos soltos, sem BEGIN/COMMIT em volta.
--   Em PostgreSQL < 12, ALTER TYPE ... ADD VALUE nao roda dentro de um bloco de
--   transacao. Mesmo nas versoes novas, um rotulo recem-adicionado nao pode ser
--   usado na MESMA transacao em que foi criado -- por isso a migracao nao faz
--   UPDATE nenhum: ela so acrescenta os rotulos.
--
-- IRREVERSIVEL
--   Rotulo de enum nao pode ser removido. Se estes nomes mudarem, o tipo inteiro
--   precisa ser recriado (criar tipo novo, ALTER TABLE ... TYPE ... USING, dropar
--   o antigo). Nao renomeie sem migracao propria.

ALTER TYPE giardini_site.reservation_status
    ADD VALUE IF NOT EXISTS 'reminded' AFTER 'confirmed';

ALTER TYPE giardini_site.reservation_status
    ADD VALUE IF NOT EXISTS 'reconfirmed' AFTER 'reminded';

-- Conferencia (deve listar 6 rotulos, com reminded e reconfirmed logo apos confirmed):
--
--   SELECT e.enumlabel, e.enumsortorder
--   FROM pg_type t
--   JOIN pg_enum e ON e.enumtypid = t.oid
--   JOIN pg_namespace n ON n.oid = t.typnamespace
--   WHERE n.nspname = 'giardini_site' AND t.typname = 'reservation_status'
--   ORDER BY e.enumsortorder;

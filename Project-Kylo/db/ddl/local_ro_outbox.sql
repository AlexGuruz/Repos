-- Create least-privilege role for n8n to read and flip outbox delivery
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kylo_ro_outbox') THEN
    CREATE ROLE kylo_ro_outbox LOGIN PASSWORD 'change_me';
  END IF;
END
$$;

GRANT USAGE ON SCHEMA intake, core, control TO kylo_ro_outbox;

GRANT SELECT ON ALL TABLES IN SCHEMA intake TO kylo_ro_outbox;
GRANT SELECT ON core.transactions_unified TO kylo_ro_outbox;
GRANT SELECT ON control.company_feeds TO kylo_ro_outbox;
GRANT SELECT ON control.outbox_events TO kylo_ro_outbox;

ALTER DEFAULT PRIVILEGES IN SCHEMA intake GRANT SELECT ON TABLES TO kylo_ro_outbox;

GRANT UPDATE (delivered_at) ON control.outbox_events TO kylo_ro_outbox;



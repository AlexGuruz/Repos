-- control.triage_metrics: lightweight metrics for triage and replay performance
create table if not exists control.triage_metrics (
  id               bigserial primary key,
  company_id       text not null,
  batch_id         text,
  operation        text not null,  -- 'triage' | 'replay'
  matched_count    integer not null default 0,
  unmatched_count  integer not null default 0,
  resolved_count   integer not null default 0,
  total_time_ms    integer not null,
  load_time_ms     integer,
  match_time_ms    integer,
  update_time_ms   integer,
  created_at       timestamptz not null default now()
);

create index if not exists idx_triage_metrics_company_created on control.triage_metrics(company_id, created_at);
create index if not exists idx_triage_metrics_operation on control.triage_metrics(operation, created_at);

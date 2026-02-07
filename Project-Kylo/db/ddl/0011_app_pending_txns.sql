-- app.pending_txns: per-company pending items shown in "{CID} Pending" tab
create table if not exists app.pending_txns (
  txn_uid           text primary key,
  company_id        text not null,
  first_seen_batch  text not null,
  last_seen_batch   text not null,
  occurred_at       timestamptz not null,
  description_norm  text not null,
  amount_cents      bigint not null,
  target_header     text,
  status            text not null default 'open',  -- 'open'|'resolved'
  row_checksum      text not null,
  updated_at        timestamptz not null default now()
);

create index if not exists idx_pending_status on app.pending_txns(status);

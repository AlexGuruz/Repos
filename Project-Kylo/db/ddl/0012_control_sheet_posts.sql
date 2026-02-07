-- control.sheet_posts: dedupe idempotent Google Sheets batchUpdate posts
create table if not exists control.sheet_posts (
  id               bigserial primary key,
  company_id       text not null,
  tab_name         text not null,
  batch_signature  text not null unique,
  row_count        integer not null,
  created_at       timestamptz not null default now()
);

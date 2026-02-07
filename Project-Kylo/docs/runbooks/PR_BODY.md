What changed
- Replace named-constraint conflict with ON CONFLICT (txn_uid, reason).
- Aligns with existing unique index on app.sort_queue(txn_uid, reason).

Why
- Avoids runtime errors when the named constraint isn’t present.
- Keeps enqueue idempotency without depending on constraint names.

How to test
- Unit: pytest -q scaffold/tests/sheets/test_poster.py scaffold/tests/test_stub.py
- Integration (requires docker): pytest -q -k rules_snapshot -m integration

Risk/rollback
- Low risk; SQL semantics unchanged aside from conflict target.
- Rollback: revert this commit to restore prior ON CONFLICT clause.

Checklist
- [ ] Tests pass locally
- [ ] Lint is clean
- [ ] `config/kylo.config.yaml` updated if required and paths verified
- [ ] Posting toggle (`posting.sheets.apply`) set as intended for this environment
- [ ] Service account path resolved via YAML or `GOOGLE_APPLICATION_CREDENTIALS`
- [ ] DSN alignment: using `database.global_dsn` (or env override) consistently
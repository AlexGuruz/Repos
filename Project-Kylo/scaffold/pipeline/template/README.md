## Per-Company Pipeline Template (Scaffold)

Purpose: provide a reusable orchestrator shape for company pipelines. Replace Protocols with concrete implementations from project services.

### Roles
- Reader: fetch pending transactions(company)
- Normalizer: text/date/amount normalization + signature
- Rules provider: fetch active rules snapshot (immutable version)
- Matcher: return (matches with key K=(workbook,sheet), suggestions)
- Aggregator: buffer rows per K and flush by thresholds
- Poster: post batches with token bucket + per-workbook lock
- Auditor: mark processed, record suggestions, audit

### Usage (pseudo)
```
pipeline = CompanyPipeline(
  company_id="acme",
  reader=myReader,
  normalizer=myNormalizer,
  rules=myRulesProvider,
  matcher=myMatcher,
  aggregator=myAggregator,
  poster=myPoster,
  auditor=myAuditor,
)
pipeline.run_once()
```

See `config_schema.json` for per-company config fields.



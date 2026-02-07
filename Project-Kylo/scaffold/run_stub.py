from typing import List, Dict, Any, Iterable, Tuple
from scaffold.pipeline.template.company_pipeline import CompanyPipeline, TransactionsReader, Normalizer, RulesProvider, Matcher, Aggregator, Poster, Auditor


class DummyTxn:
    def __init__(self, id: int, company_id: str, raw_source: str, amount: float, date: str):
        self.id = id
        self.company_id = company_id
        self.raw_source = raw_source
        self.amount = amount
        self.date = date


class DummyReader(TransactionsReader):
    def fetch_pending_transactions(self, company_id: str, limit: int = 1000):
        return [DummyTxn(1, company_id, "coffee shop", 12.34, "2025-08-25")]


class DummyNormalizer(Normalizer):
    def normalize_transactions(self, transactions: Iterable[DummyTxn]) -> Iterable[DummyTxn]:
        return transactions


class DummyRules:
    def __init__(self, version: int):
        self.version = version


class DummyRulesProvider(RulesProvider):
    def get_active_rules(self, company_id: str):
        return DummyRules(version=1)


class DummyMatcher(Matcher):
    def match(self, rules: DummyRules, transactions: Iterable[DummyTxn]):
        matches = [{"key": ("workbook-1", "Cash"), "row": {"id": t.id, "amount": t.amount}} for t in transactions]
        return matches, []


class DummyAggregator(Aggregator):
    def __init__(self):
        self.buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    def add(self, key: Tuple[str, str], row: Dict[str, Any]) -> None:
        self.buckets.setdefault(key, []).append(row)

    def flush_due(self):
        items = list(self.buckets.items())
        self.buckets.clear()
        return items


class DummyPoster(Poster):
    def post_batch(self, key: Tuple[str, str], rows: List[Dict[str, Any]]) -> None:
        print(f"POST {key}: {len(rows)} rows")


class DummyAuditor(Auditor):
    def record_processed(self, company_id: str, rows: List[Dict[str, Any]], rules_version: int) -> None:
        print(f"PROCESSED {company_id}: {len(rows)} rows @ rules v{rules_version}")

    def record_suggestions(self, company_id: str, suggestions: List[Dict[str, Any]], rules_version: int) -> None:
        print(f"SUGGESTIONS {company_id}: {len(suggestions)} @ rules v{rules_version}")


def main():
    pipeline = CompanyPipeline(
        company_id="acme",
        reader=DummyReader(),
        normalizer=DummyNormalizer(),
        rules=DummyRulesProvider(),
        matcher=DummyMatcher(),
        aggregator=DummyAggregator(),
        poster=DummyPoster(),
        auditor=DummyAuditor(),
    )
    pipeline.run_once()


if __name__ == "__main__":
    main()



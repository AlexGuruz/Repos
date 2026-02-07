from typing import Protocol, List, Dict, Any, Iterable, Tuple


class Transaction(Protocol):
    id: int
    company_id: str
    raw_source: str
    amount: float
    date: str


class RulesSnapshot(Protocol):
    version: int
    # implementation-defined rule set


class TransactionsReader(Protocol):
    def fetch_pending_transactions(self, company_id: str, limit: int = 1000) -> List[Transaction]:
        ...


class Normalizer(Protocol):
    def normalize_transactions(self, transactions: Iterable[Transaction]) -> Iterable[Transaction]:
        ...


class RulesProvider(Protocol):
    def get_active_rules(self, company_id: str) -> RulesSnapshot:
        ...


class Matcher(Protocol):
    def match(self, rules: RulesSnapshot, transactions: Iterable[Transaction]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Returns (matches, suggestions)
        matches: items with key K=(workbook, sheet) and row payload
        suggestions: low-confidence or unmatched
        """
        ...


class Aggregator(Protocol):
    def add(self, key: Tuple[str, str], row: Dict[str, Any]) -> None:
        ...

    def flush_due(self) -> List[Tuple[Tuple[str, str], List[Dict[str, Any]]]]:
        ...


class Poster(Protocol):
    def post_batch(self, key: Tuple[str, str], rows: List[Dict[str, Any]]) -> None:
        ...


class Auditor(Protocol):
    def record_processed(self, company_id: str, rows: List[Dict[str, Any]], rules_version: int) -> None:
        ...

    def record_suggestions(self, company_id: str, suggestions: List[Dict[str, Any]], rules_version: int) -> None:
        ...


class CompanyPipeline:
    """Reusable per-company pipeline orchestrator (scaffold).

    Wires: reader -> normalizer -> rules provider -> matcher -> aggregator -> poster -> auditor
    """

    def __init__(
        self,
        company_id: str,
        reader: TransactionsReader,
        normalizer: Normalizer,
        rules: RulesProvider,
        matcher: Matcher,
        aggregator: Aggregator,
        poster: Poster,
        auditor: Auditor,
        fetch_limit: int = 1000,
    ) -> None:
        self.company_id = company_id
        self.reader = reader
        self.normalizer = normalizer
        self.rules = rules
        self.matcher = matcher
        self.aggregator = aggregator
        self.poster = poster
        self.auditor = auditor
        self.fetch_limit = fetch_limit

    def run_once(self) -> None:
        txns = self.reader.fetch_pending_transactions(self.company_id, limit=self.fetch_limit)
        if not txns:
            return
        normalized = list(self.normalizer.normalize_transactions(txns))
        snapshot = self.rules.get_active_rules(self.company_id)
        matches, suggestions = self.matcher.match(snapshot, normalized)

        if suggestions:
            self.auditor.record_suggestions(self.company_id, suggestions, snapshot.version)

        # Group into aggregator buckets
        for item in matches:
            key = item["key"]  # expected (workbook, sheet)
            row = item["row"]
            self.aggregator.add(key, row)

        # Flush due batches and post
        due = self.aggregator.flush_due()
        for key, rows in due:
            self.poster.post_batch(key, rows)
            self.auditor.record_processed(self.company_id, rows, snapshot.version)



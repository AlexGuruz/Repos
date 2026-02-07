#!/usr/bin/env python3
"""Find the transaction that's failing with LABS header issue."""
import sys
import os
sys.path.insert(0, '.')

from services.posting.jgdtruth_poster import load_config, fetch_rules_from_jgdtruth
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import parse_csv_transactions

os.environ.setdefault("KYLO_SECRETS_DIR", os.path.join(os.getcwd(), ".secrets"))
os.environ.setdefault("KYLO_ACTIVE_YEARS", "2026")

cfg = load_config()
rules = fetch_rules_from_jgdtruth('PUFFIN')

# Find the problematic rule
problem_rule = None
for r in rules.values():
    if r.target_header and 'LABS' in r.target_header.upper():
        if r.target_sheet and 'CASH EXPENSE' in r.target_sheet.upper():
            problem_rule = r
            break

if problem_rule:
    print(f"\n=== Problem Rule ===")
    print(f"Source: '{problem_rule.source}'")
    print(f"Target Sheet: '{problem_rule.target_sheet}'")
    print(f"Target Header: '{problem_rule.target_header}'")
    print(f"Approved: {problem_rule.approved}")
    
    # Try to find matching transactions
    print(f"\n=== Looking for matching transactions ===")
    try:
        csv_data = download_petty_cash_csv(cfg)
        txns = parse_csv_transactions(csv_data, company_id="PUFFIN")
        
        # Filter for 2026
        txns_2026 = [t for t in txns if str(t.get('posted_date', '')).startswith('2026')]
        print(f"Total 2026 transactions: {len(txns_2026)}")
        
        # Find matches
        source_match = problem_rule.source.strip()
        matches = []
        for t in txns_2026:
            desc = (t.get('description') or '').strip()
            if source_match.upper() in desc.upper() or desc.upper() in source_match.upper():
                matches.append(t)
        
        print(f"\nMatching transactions: {len(matches)}")
        for t in matches[:5]:
            print(f"  - Description: '{t.get('description')}'")
            print(f"    Date: {t.get('posted_date')}")
            print(f"    Amount: ${t.get('amount_cents', 0) / 100:.2f}")
            print(f"    Company: {t.get('company_id')}")
            print()
    except Exception as e:
        print(f"Error loading transactions: {e}")
        import traceback
        traceback.print_exc()

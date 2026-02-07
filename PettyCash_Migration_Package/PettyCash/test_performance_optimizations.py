#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to demonstrate performance optimizations in the petty cash sorter.
"""

import time
import logging
from pathlib import Path
from petty_cash_sorter_final import FinalPettyCashSorter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_cache_performance():
    """Test the performance improvement from using transaction cache."""
    print("🧪 TESTING CACHE PERFORMANCE OPTIMIZATION")
    print("=" * 60)
    
    sorter = FinalPettyCashSorter()
    
    # Test cache loading
    print("1. Testing cache loading...")
    start_time = time.time()
    sorter.load_existing_transactions_cache()
    cache_load_time = time.time() - start_time
    print(f"   Cache loaded {len(sorter.existing_transactions_cache)} transactions in {cache_load_time:.3f} seconds")
    
    # Test cache lookup performance
    print("\n2. Testing cache lookup performance...")
    test_transactions = [
        ("1", "TEST SOURCE 1", "$100.00", "01/01/2025"),
        ("2", "TEST SOURCE 2", "$200.00", "01/02/2025"),
        ("999", "NONEXISTENT", "$999.00", "01/99/2025"),
    ]
    
    cache_lookup_time = 0
    for row_num, source, amount, date in test_transactions:
        start_time = time.time()
        exists = sorter.transaction_exists_in_cache(row_num, source, amount, date)
        lookup_time = time.time() - start_time
        cache_lookup_time += lookup_time
        print(f"   Lookup '{source}': {exists} ({lookup_time:.6f} seconds)")
    
    print(f"   Total cache lookup time: {cache_lookup_time:.6f} seconds")
    print(f"   Average per lookup: {cache_lookup_time/len(test_transactions):.6f} seconds")
    
    return cache_load_time, cache_lookup_time

def test_sqlite_setup():
    """Test SQLite database setup for future scalability."""
    print("\n🗄️ TESTING SQLITE DATABASE SETUP")
    print("=" * 60)
    
    sorter = FinalPettyCashSorter()
    
    # Test database setup
    print("1. Testing SQLite database setup...")
    start_time = time.time()
    success = sorter.setup_sqlite_rules_database()
    setup_time = time.time() - start_time
    
    if success:
        print(f"   Database setup successful in {setup_time:.3f} seconds")
        
        # Check if database file was created
        db_path = Path("config/rules_database.db")
        if db_path.exists():
            print(f"   Database file created: {db_path}")
            print(f"   File size: {db_path.stat().st_size} bytes")
        else:
            print("   Warning: Database file not found")
    else:
        print("   Database setup failed")
    
    return success, setup_time

def test_ai_matcher_performance():
    """Test AI matcher performance with various source variations."""
    print("\n🤖 TESTING AI MATCHER PERFORMANCE")
    print("=" * 60)
    
    sorter = FinalPettyCashSorter()
    
    # Load some test rules
    test_rules = {
        'HIGH GUYS ORDER_NUGZ': {
            'source': 'HIGH GUYS ORDER',
            'target_sheet': 'NUGZ',
            'target_header': 'Wholesale',
            'jgd_sheet': 'NUGZ'
        },
        'SALE TO EMERALDS_NUGZ': {
            'source': 'SALE TO EMERALDS',
            'target_sheet': 'NUGZ',
            'target_header': 'Retail',
            'jgd_sheet': 'NUGZ'
        }
    }
    
    sorter.ai_matcher.rules_cache.update(test_rules)
    
    # Test various source variations
    test_sources = [
        ("HIGH GUYZ ORDER", "NUGZ"),  # Typo + word order
        ("ORDER HIGH GUYS", "NUGZ"),  # Word order
        ("HIGH GUYS  ORDER", "NUGZ"), # Extra spacing
        ("sale to emeralds", "NUGZ"), # Case variation
        ("SALE TO EMERALDS", "NUGZ"), # Exact match
        ("UNKNOWN SOURCE", "NUGZ"),   # No match
    ]
    
    print("Testing AI matcher with various source variations:")
    total_time = 0
    
    for source, company in test_sources:
        start_time = time.time()
        result = sorter.ai_matcher.find_best_match(source, company)
        match_time = time.time() - start_time
        total_time += match_time
        
        status = "✅ MATCH" if result.matched else "❌ NO MATCH"
        print(f"   '{source}' -> {status} (Confidence: {result.confidence:.2f}, Type: {result.match_type}) - {match_time:.6f}s")
        
        if result.suggestions:
            print(f"     Suggestions: {result.suggestions}")
    
    print(f"\nTotal AI matching time: {total_time:.6f} seconds")
    print(f"Average per match: {total_time/len(test_sources):.6f} seconds")
    
    return total_time

def main():
    """Run all performance tests."""
    print("🚀 PERFORMANCE OPTIMIZATION TESTS")
    print("=" * 60)
    print("Testing the optimizations implemented in petty_cash_sorter_final.py")
    print()
    
    # Test 1: Cache Performance
    cache_load_time, cache_lookup_time = test_cache_performance()
    
    # Test 2: SQLite Setup
    sqlite_success, sqlite_setup_time = test_sqlite_setup()
    
    # Test 3: AI Matcher Performance
    ai_match_time = test_ai_matcher_performance()
    
    # Summary
    print("\n📊 PERFORMANCE TEST SUMMARY")
    print("=" * 60)
    print(f"Cache loading time: {cache_load_time:.3f} seconds")
    print(f"Cache lookup time: {cache_lookup_time:.6f} seconds")
    print(f"SQLite setup time: {sqlite_setup_time:.3f} seconds")
    print(f"AI matching time: {ai_match_time:.6f} seconds")
    print()
    
    print("✅ PERFORMANCE OPTIMIZATIONS IMPLEMENTED:")
    print("   1. O(1) transaction lookups using Python sets")
    print("   2. SQLite database support for future rule scalability")
    print("   3. AI-enhanced fuzzy matching with learning")
    print("   4. Performance monitoring and metrics")
    print()
    
    print("🎯 BENEFITS:")
    print("   • Faster preprocessing as transaction history grows")
    print("   • Scalable rule storage for thousands of rules")
    print("   • Intelligent source matching with typo correction")
    print("   • Detailed performance tracking")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""Test hash deduplication system"""

from hash_deduplication import HashDeduplication

def test_hash_deduplication():
    """Test the hash deduplication system."""
    
    print("🧪 TESTING HASH DEDUPLICATION")
    print("=" * 50)
    
    # Create hash deduplication instance
    hash_dedup = HashDeduplication()
    
    # Create sample transactions
    sample_transactions = [
        {
            'date': '01/01/25',
            'source': 'REG 1 DEPOSIT',
            'company': 'NUGZ',
            'amount': 1269.94,
            'row_number': 10
        },
        {
            'date': '01/01/25',
            'source': 'REG 2 DEPOSIT',
            'company': 'NUGZ',
            'amount': 799.07,
            'row_number': 11
        },
        {
            'date': '01/01/25',
            'source': 'REG 3 DEPOSIT',
            'company': 'NUGZ',
            'amount': 314.00,
            'row_number': 12
        }
    ]
    
    print(f"📋 SAMPLE TRANSACTIONS:")
    for i, transaction in enumerate(sample_transactions, 1):
        print(f"  {i}. {transaction['source']} ({transaction['company']}) ${transaction['amount']:.2f}")
    
    # Test filtering new transactions
    print(f"\n🔍 FILTERING NEW TRANSACTIONS:")
    new_transactions = hash_dedup.filter_new_transactions(sample_transactions)
    print(f"  • New transactions: {len(new_transactions)}")
    print(f"  • Duplicates filtered: {len(sample_transactions) - len(new_transactions)}")
    
    # Mark transactions as processed
    if new_transactions:
        print(f"\n✅ MARKING TRANSACTIONS AS PROCESSED:")
        hash_dedup.mark_transactions_processed(new_transactions)
        print(f"  • Marked {len(new_transactions)} transactions as processed")
    
    # Test filtering again (should find no new transactions)
    print(f"\n🔄 TESTING DEDUPLICATION:")
    new_transactions_again = hash_dedup.filter_new_transactions(sample_transactions)
    print(f"  • New transactions on second run: {len(new_transactions_again)}")
    print(f"  • Expected: 0 (all should be filtered as duplicates)")
    
    if len(new_transactions_again) == 0:
        print(f"  ✅ DEDUPLICATION WORKING CORRECTLY!")
    else:
        print(f"  ❌ DEDUPLICATION NOT WORKING!")
    
    # Show hash file info
    hash_file = hash_dedup.hash_file_path
    if hash_file.exists():
        print(f"\n📁 HASH FILE CREATED:")
        print(f"  • Location: {hash_file}")
        print(f"  • Size: {hash_file.stat().st_size} bytes")
        print(f"  • Contains {len(hash_dedup.processed_hashes)} hashes")
    else:
        print(f"\n❌ HASH FILE NOT CREATED")
    
    return True

if __name__ == "__main__":
    test_hash_deduplication() 
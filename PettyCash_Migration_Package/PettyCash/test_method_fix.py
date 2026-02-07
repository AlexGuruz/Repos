#!/usr/bin/env python3
"""
Test Method Fix
Test that the get_matching_statistics method works correctly
"""

from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher

def test_get_matching_statistics():
    """Test the get_matching_statistics method."""
    print("🧪 TESTING get_matching_statistics METHOD")
    print("=" * 50)
    
    try:
        # Initialize the AI matcher
        matcher = AIEnhancedRuleMatcher()
        
        # Create sample match results
        sample_results = {
            'matched': [
                {'confidence': 0.85, 'match_type': 'exact', 'source': 'WALMART'},
                {'confidence': 0.72, 'match_type': 'fuzzy', 'source': 'REG 3 DEPOSIT'},
                {'confidence': 0.95, 'match_type': 'exact', 'source': 'PAYROLL'}
            ],
            'unmatched': [
                {'source': 'UNKNOWN SOURCE 1'},
                {'source': 'UNKNOWN SOURCE 2'}
            ]
        }
        
        # Test the method
        stats = matcher.get_matching_statistics(sample_results)
        
        print("✅ Method executed successfully!")
        print(f"📊 Results: {stats}")
        
        # Verify expected values
        expected_matches = 3
        expected_unmatched = 2
        expected_avg_confidence = (0.85 + 0.72 + 0.95) / 3
        
        print(f"\n🔍 VERIFICATION:")
        print(f"  Expected matches: {expected_matches}, Got: {stats['matched_count']}")
        print(f"  Expected unmatched: {expected_unmatched}, Got: {stats['unmatched_count']}")
        print(f"  Expected avg confidence: {expected_avg_confidence:.2f}, Got: {stats['average_confidence']:.2f}")
        print(f"  Expected match rate: 60.0%, Got: {stats['match_rate_percent']:.1f}%")
        
        if (stats['matched_count'] == expected_matches and 
            stats['unmatched_count'] == expected_unmatched and
            abs(stats['average_confidence'] - expected_avg_confidence) < 0.01 and
            abs(stats['match_rate_percent'] - 60.0) < 0.1):
            print("✅ All values match expected results!")
            return True
        else:
            print("❌ Some values don't match expected results")
            return False
            
    except Exception as e:
        print(f"❌ Error testing method: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_get_matching_statistics()
    if success:
        print("\n🎉 Method fix is working correctly!")
    else:
        print("\n❌ Method fix needs more work") 
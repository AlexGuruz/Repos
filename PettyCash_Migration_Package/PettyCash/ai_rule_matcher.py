#!/usr/bin/env python3
"""
AI Rule Matcher for Petty Cash Sorter
Matches transactions to rules with 1-10 confidence scoring
"""

import logging
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple
from database_manager import DatabaseManager

class AIRuleMatcher:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.rules_cache = []
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/ai_rule_matcher.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING AI RULE MATCHER")
        logging.info("=" * 50)
    
    def load_rules_from_database(self) -> bool:
        """Load rules from database into cache."""
        try:
            self.rules_cache = self.db_manager.get_all_rules()
            logging.info(f"Loaded {len(self.rules_cache)} rules into cache")
            return True
        except Exception as e:
            logging.error(f"Error loading rules from database: {e}")
            return False
    
    def match_transaction(self, transaction: Dict) -> Optional[Dict]:
        """Match a transaction to the best rule with confidence score."""
        try:
            if not self.rules_cache:
                logging.warning("No rules loaded in cache")
                return None
            
            source = transaction.get('source', '').strip()
            if not source:
                logging.warning(f"Transaction has no source: {transaction}")
                return None
            
            best_match = None
            best_confidence = 0
            
            for rule in self.rules_cache:
                rule_source = rule.get('source', '').strip()
                if not rule_source:
                    continue
                
                # Calculate confidence score (1-10)
                confidence = self._calculate_confidence(source, rule_source)
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = {
                        'rule': rule,
                        'confidence': confidence,
                        'matched_source': rule_source,
                        'transaction_source': source
                    }
            
            if best_match and best_match['confidence'] >= 5:  # Minimum threshold
                logging.info(f"Matched '{source}' to '{best_match['matched_source']}' with confidence {best_match['confidence']}")
                return best_match
            else:
                logging.info(f"No match found for '{source}' (best confidence: {best_confidence})")
                return None
                
        except Exception as e:
            logging.error(f"Error matching transaction: {e}")
            return None
    
    def _calculate_confidence(self, transaction_source: str, rule_source: str) -> float:
        """Calculate confidence score from 1-10."""
        try:
            # Normalize strings
            trans_norm = transaction_source.lower().strip()
            rule_norm = rule_source.lower().strip()
            
            # Exact match
            if trans_norm == rule_norm:
                return 10.0
            
            # Contains match (high confidence)
            if trans_norm in rule_norm or rule_norm in trans_norm:
                return 9.0
            
            # Sequence similarity
            similarity = SequenceMatcher(None, trans_norm, rule_norm).ratio()
            
            # Convert to 1-10 scale
            if similarity >= 0.9:
                return 8.0
            elif similarity >= 0.8:
                return 7.0
            elif similarity >= 0.7:
                return 6.0
            elif similarity >= 0.6:
                return 5.0
            elif similarity >= 0.5:
                return 4.0
            elif similarity >= 0.4:
                return 3.0
            elif similarity >= 0.3:
                return 2.0
            else:
                return 1.0
                
        except Exception as e:
            logging.error(f"Error calculating confidence: {e}")
            return 0.0
    
    def batch_match_transactions(self, transactions: List[Dict]) -> Dict:
        """Match multiple transactions and return results."""
        try:
            results = {
                'matched': [],
                'unmatched': [],
                'total_processed': len(transactions),
                'match_rate': 0.0
            }
            
            for transaction in transactions:
                match_result = self.match_transaction(transaction)
                
                if match_result:
                    results['matched'].append({
                        'transaction': transaction,
                        'match': match_result
                    })
                else:
                    results['unmatched'].append(transaction)
            
            # Calculate match rate
            if results['total_processed'] > 0:
                results['match_rate'] = len(results['matched']) / results['total_processed']
            
            logging.info(f"Batch matching complete: {len(results['matched'])} matched, {len(results['unmatched'])} unmatched")
            return results
            
        except Exception as e:
            logging.error(f"Error in batch matching: {e}")
            return {'matched': [], 'unmatched': transactions, 'total_processed': len(transactions), 'match_rate': 0.0}
    
    def suggest_new_rules(self, unmatched_transactions: List[Dict]) -> List[Dict]:
        """Suggest new rules for unmatched transactions."""
        try:
            suggestions = []
            
            # Group by similar sources
            source_groups = {}
            for transaction in unmatched_transactions:
                source = transaction.get('source', '').strip()
                if source:
                    # Find similar sources
                    grouped = False
                    for existing_source in source_groups:
                        if self._calculate_confidence(source, existing_source) >= 7:
                            source_groups[existing_source].append(transaction)
                            grouped = True
                            break
                    
                    if not grouped:
                        source_groups[source] = [transaction]
            
            # Create suggestions for groups with multiple transactions
            for source, transactions in source_groups.items():
                if len(transactions) >= 2:  # Only suggest for sources with multiple transactions
                    suggestion = {
                        'suggested_source': source,
                        'transaction_count': len(transactions),
                        'sample_transactions': transactions[:3],  # First 3 as examples
                        'total_amount': sum(t.get('amount', 0) for t in transactions),
                        'companies': list(set(t.get('company', '') for t in transactions if t.get('company')))
                    }
                    suggestions.append(suggestion)
            
            logging.info(f"Generated {len(suggestions)} rule suggestions")
            return suggestions
            
        except Exception as e:
            logging.error(f"Error suggesting new rules: {e}")
            return []
    
    def get_confidence_level_description(self, confidence: float) -> str:
        """Get human-readable description of confidence level."""
        if confidence >= 9:
            return "Exact Match"
        elif confidence >= 7:
            return "Close Match"
        elif confidence >= 5:
            return "Similar Match"
        else:
            return "Weak Match"
    
    def get_matching_statistics(self, match_results: Dict) -> Dict:
        """Get statistics about matching results."""
        try:
            stats = {
                'total_transactions': match_results['total_processed'],
                'matched_count': len(match_results['matched']),
                'unmatched_count': len(match_results['unmatched']),
                'match_rate_percent': round(match_results['match_rate'] * 100, 2),
                'confidence_distribution': {
                    'exact_matches': 0,    # 9-10
                    'close_matches': 0,    # 7-8
                    'similar_matches': 0,  # 5-6
                    'weak_matches': 0      # 1-4
                }
            }
            
            # Analyze confidence distribution
            for match in match_results['matched']:
                confidence = match['match']['confidence']
                if confidence >= 9:
                    stats['confidence_distribution']['exact_matches'] += 1
                elif confidence >= 7:
                    stats['confidence_distribution']['close_matches'] += 1
                elif confidence >= 5:
                    stats['confidence_distribution']['similar_matches'] += 1
                else:
                    stats['confidence_distribution']['weak_matches'] += 1
            
            return stats
            
        except Exception as e:
            logging.error(f"Error getting matching statistics: {e}")
            return {}

def main():
    """Test AI rule matcher."""
    print("AI RULE MATCHER TEST")
    print("=" * 50)
    
    matcher = AIRuleMatcher()
    
    # Load rules
    if matcher.load_rules_from_database():
        print(f"✅ Loaded {len(matcher.rules_cache)} rules")
        
        # Test with sample transactions
        test_transactions = [
            {'source': 'WALMART', 'amount': 25.50, 'company': 'TEST'},
            {'source': 'AMAZON', 'amount': 100.00, 'company': 'TEST'},
            {'source': 'UNKNOWN SOURCE', 'amount': 50.00, 'company': 'TEST'}
        ]
        
        # Test individual matching
        print(f"\nTesting individual matches:")
        for transaction in test_transactions:
            match = matcher.match_transaction(transaction)
            if match:
                confidence_desc = matcher.get_confidence_level_description(match['confidence'])
                print(f"  '{transaction['source']}' → '{match['matched_source']}' ({confidence_desc}: {match['confidence']})")
            else:
                print(f"  '{transaction['source']}' → No match")
        
        # Test batch matching
        print(f"\nTesting batch matching:")
        batch_results = matcher.batch_match_transactions(test_transactions)
        stats = matcher.get_matching_statistics(batch_results)
        
        print(f"  Total: {stats['total_transactions']}")
        print(f"  Matched: {stats['matched_count']}")
        print(f"  Unmatched: {stats['unmatched_count']}")
        print(f"  Match rate: {stats['match_rate_percent']}%")
        
        # Test rule suggestions
        if batch_results['unmatched']:
            print(f"\nTesting rule suggestions:")
            suggestions = matcher.suggest_new_rules(batch_results['unmatched'])
            for i, suggestion in enumerate(suggestions):
                print(f"  {i+1}. '{suggestion['suggested_source']}' ({suggestion['transaction_count']} transactions)")
        
    else:
        print("❌ Failed to load rules")

if __name__ == "__main__":
    main() 
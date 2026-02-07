#!/usr/bin/env python3
"""
Enhanced AI Rule Matcher for Petty Cash Sorter
Advanced matching with semantic understanding, pattern recognition, and learning
"""

import logging
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from database_manager import DatabaseManager
import time

@dataclass
class MatchResult:
    """Result of a rule matching attempt."""
    matched: bool
    confidence: float
    matched_rule: Optional[Dict] = None
    original_source: str = ""
    normalized_source: str = ""
    match_type: str = "none"
    suggestions: List[str] = None

class AIEnhancedRuleMatcher:
    """AI-enhanced rule matcher with fuzzy logic and intelligent corrections."""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.rules_cache = {}
        self.source_variations = {}
        self.confidence_threshold = 0.75  # Base threshold
        self.max_suggestions = 5
        
        # Dynamic confidence threshold system
        self.company_thresholds = {}  # Company-specific thresholds
        self.match_history = []  # Track match results for learning
        self.min_threshold = 0.5  # Minimum acceptable threshold
        self.max_threshold = 0.95  # Maximum threshold
        self.learning_rate = 0.05  # How much to adjust thresholds
        
        # Semantic understanding patterns
        self.semantic_patterns = {
            'payroll': ['salary', 'wage', 'paycheck', 'employee payment', 'payroll', 'pay'],
            'sales': ['revenue', 'income', 'customer payment', 'wholesale', 'sale', 'sales'],
            'expenses': ['cost', 'purchase', 'bill', 'payment', 'expense', 'buy'],
            'deposits': ['bank deposit', 'cash deposit', 'fund transfer', 'deposit'],
            'register': ['register', 'reg', 'cash register', 'pos'],
            'orders': ['order', 'purchase order', 'po', 'buy'],
            'lab': ['lab', 'laboratory', 'testing', 'test', 'analysis']
        }
        
        # Common patterns and corrections
        self.common_patterns = {
            # Word order variations
            r'^(ORDER|SALE TO|PAYROLL|REG)\s+(.+)$': r'\2 \1',
            r'^(.+)\s+(ORDER|SALE TO|PAYROLL|REG)$': r'\2 \1',
            
            # Common abbreviations
            r'\bINC\b': 'INCORPORATED',
            r'\bCO\b': 'COMPANY',
            r'\bLLC\b': 'LIMITED LIABILITY COMPANY',
            r'\bDIST\b': 'DISTRIBUTION',
            r'\bDISP\b': 'DISPENSARY',
            
            # Common typos
            r'\bGUYZ\b': 'GUYS',
            r'\bMARIJUANA\b': 'MARIJUANA',
            r'\bWHOLESALE\b': 'WHOLESALE',
            r'\bEMERALDS\b': 'EMERALDS',
            r'\bWELLNESS\b': 'WELLNESS',
        }
        
        # Company-specific patterns
        self.company_patterns = {
            'NUGZ': {
                'sale_patterns': [r'SALE TO (.+)', r'SALES TO (.+)', r'WHOLESALE (.+)'],
                'payroll_patterns': [r'PAYROLL (\d+)', r'PAYCHECK (\d+)'],
                'register_patterns': [r'REG (\d+)', r'REGISTER (\d+)'],
            },
            'JGD': {
                'sale_patterns': [r'SALE TO (.+)', r'SALES TO (.+)'],
                'payroll_patterns': [r'PAYROLL (\d+)', r'PAYCHECK (\d+)'],
            },
            'PUFFIN': {
                'order_patterns': [r'ORDER (.+)', r'PURCHASE (.+)'],
                'lab_patterns': [r'LAB (.+)', r'TESTING (.+)'],
            }
        }
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/ai_rule_matcher_enhanced.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING ENHANCED AI RULE MATCHER")
        logging.info("=" * 60)
        
        # Load learned variations
        self.load_learned_variations()
    
    def load_rules_from_database(self) -> bool:
        """Load rules from database into cache with company awareness."""
        try:
            rules = self.db_manager.get_all_rules()
            
            # Convert to dictionary format for faster lookup with company awareness
            for rule in rules:
                source = rule.get('source', '').strip()
                company = rule.get('company', 'Unknown')
                
                if source:
                    # Use source+company as the key to maintain company separation
                    key = f"{source}|{company}"
                    self.rules_cache[key] = rule
            
            logging.info(f"Loaded {len(self.rules_cache)} company-specific rules into enhanced cache")
            return True
        except Exception as e:
            logging.error(f"Error loading rules from database: {e}")
            return False
    
    def load_learned_variations(self):
        """Load previously learned source variations."""
        variations_file = Path("config/source_variations.json")
        if variations_file.exists():
            try:
                with open(variations_file, 'r') as f:
                    self.source_variations = json.load(f)
                logging.info(f"Loaded {len(self.source_variations)} learned source variations")
            except Exception as e:
                logging.warning(f"Could not load source variations: {e}")
    
    def save_learned_variations(self):
        """Save learned source variations for future use."""
        variations_file = Path("config/source_variations.json")
        variations_file.parent.mkdir(exist_ok=True)
        
        try:
            with open(variations_file, 'w') as f:
                json.dump(self.source_variations, f, indent=2)
            logging.info(f"Saved {len(self.source_variations)} source variations")
        except Exception as e:
            logging.error(f"Could not save source variations: {e}")
    
    def save_rule_suggestions(self, suggestions: List[Dict]):
        """Save rule suggestions to pending queue for user review."""
        suggestions_file = Path("config/pending_rule_suggestions.json")
        suggestions_file.parent.mkdir(exist_ok=True)
        
        try:
            # Load existing suggestions
            existing_suggestions = []
            if suggestions_file.exists():
                with open(suggestions_file, 'r') as f:
                    existing_suggestions = json.load(f)
            
            # Add new suggestions with timestamp
            for suggestion in suggestions:
                suggestion['timestamp'] = time.time()
                suggestion['status'] = 'pending'  # pending, approved, rejected
                suggestion['id'] = f"suggestion_{int(time.time())}_{hash(suggestion['source'])}"
            
            # Combine and save
            all_suggestions = existing_suggestions + suggestions
            
            with open(suggestions_file, 'w') as f:
                json.dump(all_suggestions, f, indent=2)
            
            logging.info(f"Saved {len(suggestions)} new rule suggestions (total: {len(all_suggestions)})")
            
        except Exception as e:
            logging.error(f"Could not save rule suggestions: {e}")
    
    def get_pending_rule_suggestions(self) -> List[Dict]:
        """Get all pending rule suggestions for user review."""
        suggestions_file = Path("config/pending_rule_suggestions.json")
        
        if not suggestions_file.exists():
            return []
        
        try:
            with open(suggestions_file, 'r') as f:
                suggestions = json.load(f)
            
            # Filter for pending suggestions only
            pending_suggestions = [s for s in suggestions if s.get('status') == 'pending']
            return pending_suggestions
            
        except Exception as e:
            logging.error(f"Could not load rule suggestions: {e}")
            return []
    
    def approve_rule_suggestion(self, suggestion_id: str) -> bool:
        """Approve a rule suggestion and add it to the database."""
        try:
            suggestions_file = Path("config/pending_rule_suggestions.json")
            if not suggestions_file.exists():
                return False
            
            # Load suggestions
            with open(suggestions_file, 'r') as f:
                suggestions = json.load(f)
            
            # Find and approve the suggestion
            for suggestion in suggestions:
                if suggestion.get('id') == suggestion_id:
                    suggestion['status'] = 'approved'
                    suggestion['approved_timestamp'] = time.time()
                    
                    # Add to database
                    rule_data = {
                        'source': suggestion['source'],
                        'target_sheet': suggestion['target_sheet'],
                        'target_header': suggestion['target_header'],
                        'confidence_threshold': 0.7
                    }
                    
                    if self.db_manager.add_rule(rule_data):
                        # Reload rules into cache
                        self.load_rules_from_database()
                        logging.info(f"Approved and added rule: {suggestion['source']} → {suggestion['target_sheet']}/{suggestion['target_header']}")
                        
                        # Save updated suggestions
                        with open(suggestions_file, 'w') as f:
                            json.dump(suggestions, f, indent=2)
                        
                        return True
                    else:
                        logging.error(f"Failed to add approved rule to database: {suggestion['source']}")
                        return False
            
            logging.warning(f"Rule suggestion not found: {suggestion_id}")
            return False
            
        except Exception as e:
            logging.error(f"Error approving rule suggestion: {e}")
            return False
    
    def reject_rule_suggestion(self, suggestion_id: str, reason: str = "") -> bool:
        """Reject a rule suggestion."""
        try:
            suggestions_file = Path("config/pending_rule_suggestions.json")
            if not suggestions_file.exists():
                return False
            
            # Load suggestions
            with open(suggestions_file, 'r') as f:
                suggestions = json.load(f)
            
            # Find and reject the suggestion
            for suggestion in suggestions:
                if suggestion.get('id') == suggestion_id:
                    suggestion['status'] = 'rejected'
                    suggestion['rejected_timestamp'] = time.time()
                    suggestion['rejection_reason'] = reason
                    
                    logging.info(f"Rejected rule suggestion: {suggestion['source']} (reason: {reason})")
                    
                    # Save updated suggestions
                    with open(suggestions_file, 'w') as f:
                        json.dump(suggestions, f, indent=2)
                    
                    return True
            
            logging.warning(f"Rule suggestion not found: {suggestion_id}")
            return False
            
        except Exception as e:
            logging.error(f"Error rejecting rule suggestion: {e}")
            return False
    
    def normalize_source(self, source: str) -> str:
        """Normalize source string for better matching."""
        if not source:
            return ""
        
        # Convert to string and strip whitespace
        normalized = str(source).strip()
        
        # Convert to uppercase for consistency
        normalized = normalized.upper()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Apply common pattern corrections
        for pattern, replacement in self.common_patterns.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        return normalized.strip()
    
    def calculate_similarity(self, source1: str, source2: str) -> float:
        """Calculate similarity between two source strings."""
        if not source1 or not source2:
            return 0.0
        
        # Normalize both strings
        norm1 = self.normalize_source(source1)
        norm2 = self.normalize_source(source2)
        
        # Exact match after normalization
        if norm1 == norm2:
            return 1.0
        
        # Use SequenceMatcher for fuzzy matching
        similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Boost similarity for partial matches
        if norm1 in norm2 or norm2 in norm1:
            similarity += 0.2
        
        # Boost for word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if len(words1) > 0 and len(words2) > 0:
            word_overlap = len(words1.intersection(words2)) / max(len(words1), len(words2))
            similarity += word_overlap * 0.3
        
        return min(similarity, 1.0)
    
    def find_best_match(self, source: str, company: str) -> MatchResult:
        """Find the best matching rule for a given source and company."""
        logging.debug(f"Finding match for source: '{source}' (Company: {company})")
        
        if not source or not company:
            logging.debug(f"Invalid input: source='{source}', company='{company}'")
            return MatchResult(matched=False, confidence=0.0, original_source=source)
        
        original_source = source
        normalized_source = self.normalize_source(source)
        
        # Get dynamic confidence threshold for this company and source
        dynamic_threshold = self.get_dynamic_threshold(company, source)
        
        # First, try exact match
        exact_match = self._find_exact_match(normalized_source, company)
        if exact_match:
            logging.debug(f"Exact match found: '{normalized_source}' -> '{exact_match['source']}'")
            return MatchResult(
                matched=True,
                confidence=1.0,
                matched_rule=exact_match,
                original_source=original_source,
                normalized_source=normalized_source,
                match_type="exact"
            )
        
        # Try learned variations
        variation_match = self._find_variation_match(source, company)
        if variation_match:
            logging.debug(f"Learned variation match found: '{source}' -> '{variation_match['source']}'")
            return MatchResult(
                matched=True,
                confidence=0.95,
                matched_rule=variation_match,
                original_source=original_source,
                normalized_source=normalized_source,
                match_type="learned_variation"
            )
        
        # Try fuzzy matching with dynamic threshold
        fuzzy_match = self._find_fuzzy_match(source, company)
        if fuzzy_match and fuzzy_match['confidence'] >= dynamic_threshold:
            logging.debug(f"Fuzzy match found: '{source}' -> '{fuzzy_match['rule']['source']}' (confidence: {fuzzy_match['confidence']:.2f} >= {dynamic_threshold:.3f})")
            return MatchResult(
                matched=True,
                confidence=fuzzy_match['confidence'],
                matched_rule=fuzzy_match['rule'],
                original_source=original_source,
                normalized_source=normalized_source,
                match_type="fuzzy"
            )
        elif fuzzy_match:
            logging.debug(f"Fuzzy match below dynamic threshold: '{source}' -> '{fuzzy_match['rule']['source']}' (confidence: {fuzzy_match['confidence']:.2f} < {dynamic_threshold:.3f})")
        
        # Generate adaptive suggestions for unmatched sources
        adaptive_suggestions = self.get_adaptive_suggestions(source, company)
        suggestions = [s['target_sheet'] + '/' + s['target_header'] for s in adaptive_suggestions]
        
        return MatchResult(
            matched=False,
            confidence=0.0,
            original_source=original_source,
            normalized_source=normalized_source,
            match_type="no_match",
            suggestions=suggestions
        )
    
    def _find_exact_match(self, normalized_source: str, company: str) -> Optional[Dict]:
        """Find exact match in rules cache with company awareness."""
        # Try exact match with company
        key = f"{normalized_source}|{company}"
        rule = self.rules_cache.get(key)
        
        if rule:
            return rule
        
        # Fallback: try without company (for backward compatibility)
        return self.rules_cache.get(normalized_source)
    
    def _find_variation_match(self, source: str, company: str) -> Optional[Dict]:
        """Find match using learned variations."""
        if source in self.source_variations:
            canonical_source = self.source_variations[source]
            return self.rules_cache.get(canonical_source)
        return None
    
    def _find_fuzzy_match(self, source: str, company: str) -> Optional[Dict]:
        """Find fuzzy match with highest confidence and company awareness."""
        best_match = None
        best_confidence = 0.0
        
        for rule_key, rule in self.rules_cache.items():
            # Extract source from rule key (format: "source|company")
            if '|' in rule_key:
                rule_source = rule_key.split('|')[0]
                rule_company = rule_key.split('|')[1]
            else:
                rule_source = rule_key
                rule_company = 'Unknown'
            
            # Calculate base similarity
            confidence = self.calculate_similarity(source, rule_source)
            
            # Apply semantic confidence boost
            semantic_boost = self._get_semantic_confidence_boost(source)
            confidence += semantic_boost
            
            # Apply company-specific adjustments
            if company in self.company_thresholds:
                confidence += self._get_history_adjustment(company)
            
            # Boost confidence for same company matches
            if rule_company == company:
                confidence += 0.2  # 20% boost for same company
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = {
                    'rule': rule,
                    'confidence': confidence
                }
        
        return best_match
    
    def _generate_suggestions(self, source: str, company: str) -> List[str]:
        """Generate rule suggestions based on semantic patterns."""
        suggestions = []
        
        # Analyze source for semantic patterns
        source_lower = source.lower()
        
        for category, patterns in self.semantic_patterns.items():
            for pattern in patterns:
                if pattern in source_lower:
                    suggestions.append(f"Consider {category} category")
                    break
        
        return suggestions
    
    def learn_variation(self, source: str, canonical_source: str):
        """Learn a new source variation."""
        self.source_variations[source] = canonical_source
        logging.info(f"Learned variation: '{source}' -> '{canonical_source}'")
    
    def auto_correct_source(self, source: str, company: str) -> str:
        """Auto-correct common issues in source strings."""
        corrected = source
        
        # Fix word order
        corrected = self._fix_word_order(corrected)
        
        # Fix typos
        corrected = self._fix_typos(corrected)
        
        # Fix spacing
        corrected = self._fix_spacing(corrected)
        
        # Apply company-specific corrections
        corrected = self._apply_company_corrections(corrected, company)
        
        return corrected
    
    def _fix_word_order(self, source: str) -> str:
        """Fix common word order issues."""
        # Common patterns for word order correction
        patterns = [
            (r'^(.+)\s+(SALE TO|PAYROLL|REG|ORDER)$', r'\2 \1'),
            (r'^(SALE TO|PAYROLL|REG|ORDER)\s+(.+)$', r'\1 \2'),
        ]
        
        for pattern, replacement in patterns:
            if re.match(pattern, source, re.IGNORECASE):
                return re.sub(pattern, replacement, source, flags=re.IGNORECASE)
        
        return source
    
    def _fix_typos(self, source: str) -> str:
        """Fix common typos in source strings."""
        typo_corrections = {
            'GUYZ': 'GUYS',
            'MARIJUANA': 'MARIJUANA',
            'WHOLESALE': 'WHOLESALE',
            'EMERALDS': 'EMERALDS',
            'WELLNESS': 'WELLNESS',
            'INCORPORATED': 'INC',
            'COMPANY': 'CO',
            'LIMITED LIABILITY COMPANY': 'LLC',
        }
        
        corrected = source
        for typo, correction in typo_corrections.items():
            corrected = re.sub(r'\b' + re.escape(typo) + r'\b', correction, corrected, flags=re.IGNORECASE)
        
        return corrected
    
    def _fix_spacing(self, source: str) -> str:
        """Fix spacing issues in source strings."""
        # Remove extra whitespace
        corrected = re.sub(r'\s+', ' ', source)
        return corrected.strip()
    
    def _apply_company_corrections(self, source: str, company: str) -> str:
        """Apply company-specific corrections."""
        if company in self.company_patterns:
            patterns = self.company_patterns[company]
            # Apply company-specific pattern corrections
            pass  # Implement company-specific corrections
        
        return source
    
    def get_match_statistics(self) -> Dict:
        """Get statistics about matching performance."""
        return {
            'total_rules': len(self.rules_cache),
            'learned_variations': len(self.source_variations),
            'company_thresholds': len(self.company_thresholds),
            'match_history_count': len(self.match_history)
        }
    
    def get_matching_statistics(self, match_results: Dict) -> Dict:
        """Get statistics from match results."""
        try:
            matched_transactions = match_results.get('matched', [])
            unmatched_transactions = match_results.get('unmatched', [])
            
            # Calculate confidence scores
            confidence_scores = []
            match_types = []
            
            for match in matched_transactions:
                if isinstance(match, dict):
                    confidence_scores.append(match.get('confidence', 0))
                    match_types.append(match.get('match_type', 'unknown'))
                elif hasattr(match, 'confidence'):
                    confidence_scores.append(match.confidence)
                    match_types.append(getattr(match, 'match_type', 'unknown'))
            
            total_transactions = len(matched_transactions) + len(unmatched_transactions)
            success_rate = len(matched_transactions) / total_transactions if total_transactions > 0 else 0
            
            return {
                'total_transactions': total_transactions,
                'matched_count': len(matched_transactions),
                'unmatched_count': len(unmatched_transactions),
                'match_rate_percent': success_rate * 100,
                'confidence_scores': confidence_scores,
                'match_types': match_types,
                'average_confidence': sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
                'success_rate': success_rate
            }
        except Exception as e:
            logging.error(f"Error calculating matching statistics: {e}")
            return {
                'total_transactions': 0,
                'matched_count': 0,
                'unmatched_count': 0,
                'match_rate_percent': 0,
                'confidence_scores': [],
                'match_types': [],
                'average_confidence': 0,
                'success_rate': 0,
                'error': str(e)
            }
    
    def get_dynamic_threshold(self, company: str, source: str) -> float:
        """Get dynamic confidence threshold based on company and source patterns."""
        base_threshold = self.confidence_threshold
        
        # Company-specific threshold
        if company in self.company_thresholds:
            base_threshold = self.company_thresholds[company]
        
        # Semantic confidence boost
        semantic_boost = self._get_semantic_confidence_boost(source)
        base_threshold += semantic_boost
        
        # History adjustment
        history_adjustment = self._get_history_adjustment(company)
        base_threshold += history_adjustment
        
        # Ensure threshold is within bounds
        return max(self.min_threshold, min(self.max_threshold, base_threshold))
    
    def _get_semantic_confidence_boost(self, source: str) -> float:
        """Get confidence boost based on semantic understanding."""
        source_lower = source.lower()
        boost = 0.0
        
        # Check for semantic patterns
        for category, patterns in self.semantic_patterns.items():
            for pattern in patterns:
                if pattern in source_lower:
                    boost += 0.1  # Small boost for semantic recognition
                    break
        
        return min(boost, 0.3)  # Cap at 0.3
    
    def _get_history_adjustment(self, company: str) -> float:
        """Get confidence adjustment based on historical match success."""
        if not self.match_history:
            return 0.0
        
        # Calculate success rate for this company
        company_matches = [m for m in self.match_history if m.get('company') == company]
        if not company_matches:
            return 0.0
        
        success_rate = sum(1 for m in company_matches if m.get('success', False)) / len(company_matches)
        
        # Adjust threshold based on success rate
        if success_rate > 0.8:
            return -0.1  # Lower threshold for high-success companies
        elif success_rate < 0.5:
            return 0.1   # Raise threshold for low-success companies
        
        return 0.0
    
    def update_threshold_from_match(self, company: str, source: str, confidence: float, success: bool):
        """Update dynamic threshold based on match result."""
        # Record match in history
        self.match_history.append({
            'company': company,
            'source': source,
            'confidence': confidence,
            'success': success,
            'timestamp': time.time()
        })
        
        # Keep only recent history (last 1000 matches)
        if len(self.match_history) > 1000:
            self.match_history = self.match_history[-1000:]
        
        # Update company threshold
        if company not in self.company_thresholds:
            self.company_thresholds[company] = self.confidence_threshold
        
        current_threshold = self.company_thresholds[company]
        
        if success:
            # Lower threshold slightly for successful matches
            new_threshold = current_threshold - (self.learning_rate * 0.1)
        else:
            # Raise threshold slightly for failed matches
            new_threshold = current_threshold + (self.learning_rate * 0.1)
        
        # Ensure threshold stays within bounds
        self.company_thresholds[company] = max(self.min_threshold, min(self.max_threshold, new_threshold))
    
    def get_adaptive_suggestions(self, source: str, company: str) -> List[Dict]:
        """Generate adaptive rule suggestions based on patterns and history."""
        suggestions = []
        
        # Analyze source for patterns
        source_lower = source.lower()
        
        # Check for semantic patterns
        for category, patterns in self.semantic_patterns.items():
            for pattern in patterns:
                if pattern in source_lower:
                    suggestions.append({
                        'target_sheet': category.upper(),
                        'target_header': 'GENERAL',
                        'confidence': 0.6,
                        'reason': f"Semantic pattern '{pattern}' detected"
                    })
                    break
        
        # Check company-specific patterns
        if company in self.company_patterns:
            company_patterns = self.company_patterns[company]
            
            for pattern_type, patterns in company_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, source, re.IGNORECASE):
                        suggestions.append({
                            'target_sheet': pattern_type.upper(),
                            'target_header': 'COMPANY_SPECIFIC',
                            'confidence': 0.7,
                            'reason': f"Company pattern '{pattern}' matched"
                        })
        
        return suggestions[:self.max_suggestions]
    
    def analyze_unmatched_transactions(self, unmatched_transactions: List[Dict], sheets_integration, db_manager=None) -> List[Dict]:
        """Analyze unmatched transactions and suggest new rules with sheet/header analysis and learning from processed transactions."""
        suggestions = []
        
        try:
            # Get available sheets and headers
            layout_map = sheets_integration.get_layout_map()
            if not layout_map:
                logging.warning("No layout map available for rule suggestions")
                return suggestions
            
            # Group unmatched transactions by company
            company_transactions = {}
            for transaction in unmatched_transactions:
                company = transaction.get('company', 'Unknown')
                if company not in company_transactions:
                    company_transactions[company] = []
                company_transactions[company].append(transaction)
            
            # Analyze each company's unmatched transactions
            for company, transactions in company_transactions.items():
                # Get available sheets for this company
                available_sheets = self._get_available_sheets_for_company(company, layout_map)
                
                for transaction in transactions:
                    source = transaction.get('source', '').strip()
                    if not source:
                        continue
                    
                    # Generate suggestions using multiple methods
                    transaction_suggestions = []
                    
                    # Method 1: Pattern-based suggestions
                    pattern_suggestions = self._generate_rule_suggestions_for_transaction(
                        source, company, available_sheets, layout_map
                    )
                    transaction_suggestions.extend(pattern_suggestions)
                    
                    # Method 2: Learning from similar processed transactions
                    if db_manager:
                        learning_suggestions = self._learn_from_processed_transactions(
                            source, company, db_manager, layout_map
                        )
                        transaction_suggestions.extend(learning_suggestions)
                    
                    suggestions.extend(transaction_suggestions)
            
            # Remove duplicates and sort by confidence
            unique_suggestions = self._deduplicate_suggestions(suggestions)
            unique_suggestions.sort(key=lambda x: x['confidence'], reverse=True)
            
            logging.info(f"Generated {len(unique_suggestions)} rule suggestions from {len(unmatched_transactions)} unmatched transactions")
            return unique_suggestions[:self.max_suggestions]
            
        except Exception as e:
            logging.error(f"Error analyzing unmatched transactions: {e}")
            return []
    
    def _learn_from_processed_transactions(self, source: str, company: str, db_manager, layout_map: Dict) -> List[Dict]:
        """Learn from similar processed transactions to suggest rules."""
        suggestions = []
        
        try:
            # Get processed transactions for this company
            processed_transactions = db_manager.get_processed_transactions_by_company(company)
            if not processed_transactions:
                return suggestions
            
            # Find similar processed transactions
            similar_transactions = self._find_similar_processed_transactions(source, processed_transactions)
            
            for similar_tx in similar_transactions:
                # Extract the rule that was used for this transaction
                rule_info = self._extract_rule_from_processed_transaction(similar_tx)
                if not rule_info:
                    continue
                
                # Calculate similarity score
                similarity = self.calculate_similarity(source, similar_tx.get('source', ''))
                
                # Only suggest if similarity is high enough
                if similarity >= 0.6:  # 60% similarity threshold
                    suggestion = {
                        'source': source,
                        'target_sheet': rule_info['target_sheet'],
                        'target_header': rule_info['target_header'],
                        'confidence': similarity * 0.9,  # Slightly reduce confidence for learned suggestions
                        'reason': f"Learned from similar processed transaction: '{similar_tx.get('source', '')}' → {rule_info['target_sheet']}/{rule_info['target_header']}",
                        'company': company,
                        'suggested_by': 'AI Learning from Processed Transactions',
                        'similarity_score': similarity,
                        'reference_transaction': similar_tx.get('transaction_id', '')
                    }
                    
                    suggestions.append(suggestion)
            
            logging.info(f"Generated {len(suggestions)} learning-based suggestions for '{source}'")
            return suggestions
            
        except Exception as e:
            logging.error(f"Error learning from processed transactions: {e}")
            return []
    
    def _find_similar_processed_transactions(self, source: str, processed_transactions: List[Dict]) -> List[Dict]:
        """Find processed transactions similar to the given source."""
        similar_transactions = []
        
        for tx in processed_transactions:
            tx_source = tx.get('source', '').strip()
            if not tx_source:
                continue
            
            # Calculate similarity
            similarity = self.calculate_similarity(source, tx_source)
            
            # Include if similarity is above threshold
            if similarity >= 0.5:  # 50% similarity threshold for learning
                similar_transactions.append({
                    **tx,
                    'similarity_score': similarity
                })
        
        # Sort by similarity and return top matches
        similar_transactions.sort(key=lambda x: x['similarity_score'], reverse=True)
        return similar_transactions[:5]  # Return top 5 similar transactions
    
    def _extract_rule_from_processed_transaction(self, transaction: Dict) -> Optional[Dict]:
        """Extract rule information from a processed transaction."""
        try:
            # Look for rule information in transaction data
            target_sheet = transaction.get('target_sheet')
            target_header = transaction.get('target_header')
            
            if target_sheet and target_header:
                return {
                    'target_sheet': target_sheet,
                    'target_header': target_header
                }
            
            # If not directly available, try to infer from status or notes
            status = transaction.get('status', '')
            notes = transaction.get('notes', '')
            
            # Look for sheet/header information in status or notes
            if 'sheet:' in notes.lower() and 'header:' in notes.lower():
                # Parse sheet and header from notes
                import re
                sheet_match = re.search(r'sheet:\s*([^\s,]+)', notes, re.IGNORECASE)
                header_match = re.search(r'header:\s*([^\s,]+)', notes, re.IGNORECASE)
                
                if sheet_match and header_match:
                    return {
                        'target_sheet': sheet_match.group(1).strip(),
                        'target_header': header_match.group(1).strip()
                    }
            
            return None
            
        except Exception as e:
            logging.error(f"Error extracting rule from transaction: {e}")
            return None
    
    def _get_available_sheets_for_company(self, company: str, layout_map: Dict) -> List[str]:
        """Get available sheets for a specific company."""
        available_sheets = []
        
        # Map company to potential sheets
        company_sheet_mapping = {
            'NUGZ': ['NUGZ C.O.G.', 'NUGZ EXPENSES'],
            'JGD': ['JGD'],
            'PUFFIN': ['PUFFIN C.O.G.', 'PUFFIN EXPENSES'],
            '710 EMPIRE': ['710 EMPIRE C.O.G.', '710 EMPIRE EXPENSES']
        }
        
        # Get company-specific sheets
        company_sheets = company_sheet_mapping.get(company, [])
        
        # Check which sheets actually exist in layout map
        for sheet in company_sheets:
            if sheet in layout_map:
                available_sheets.append(sheet)
        
        # Add general sheets that might be relevant
        general_sheets = ['PAYROLL', 'COMMISSION', 'BALANCE', 'INCOME', 'NON CANNABIS', 'ALLOCATED', 'CONSIGNMENT']
        for sheet in general_sheets:
            if sheet in layout_map:
                available_sheets.append(sheet)
        
        return available_sheets
    
    def _generate_rule_suggestions_for_transaction(self, source: str, company: str, available_sheets: List[str], layout_map: Dict) -> List[Dict]:
        """Generate rule suggestions for a specific transaction using ONLY actual available sheets and headers."""
        suggestions = []
        
        # Normalize source for analysis
        normalized_source = self.normalize_source(source)
        source_lower = normalized_source.lower()
        
        # Analyze source patterns and suggest appropriate sheets/headers
        for sheet in available_sheets:
            if sheet not in layout_map:
                continue
            
            # Get sheet data structure
            sheet_data = layout_map[sheet]
            if not isinstance(sheet_data, dict) or 'headers' not in sheet_data:
                continue
            
            # Get actual headers for this sheet
            sheet_headers = list(sheet_data['headers'].keys())
            if not sheet_headers:
                continue
            
            # Check if source matches any patterns for this sheet
            confidence, reason = self._analyze_source_for_sheet(source_lower, sheet, sheet_headers)
            
            if confidence > 0.3:  # Minimum confidence threshold for suggestions
                # Find the best matching header from actual headers
                best_header = self._find_best_header_for_source(source_lower, sheet_headers)
                
                # Validate that the best header actually exists in this sheet
                if best_header in sheet_headers:
                    suggestions.append({
                        'source': source,
                        'target_sheet': sheet,
                        'target_header': best_header,
                        'confidence': confidence,
                        'reason': reason,
                        'company': company,
                        'suggested_by': 'AI Analysis',
                        'available_headers': sheet_headers  # Include for transparency
                    })
        
        return suggestions
    
    def _analyze_source_for_sheet(self, source_lower: str, sheet: str, headers: List[str]) -> Tuple[float, str]:
        """Analyze if a source matches patterns for a specific sheet."""
        confidence = 0.0
        reason = ""
        
        # Sheet-specific pattern analysis
        if 'PAYROLL' in sheet.upper():
            if any(word in source_lower for word in ['payroll', 'pay', 'salary', 'wage', 'employee']):
                confidence = 0.8
                reason = "Payroll-related source detected"
        
        elif 'SALES' in sheet.upper() or 'C.O.G.' in sheet.upper():
            if any(word in source_lower for word in ['sale', 'revenue', 'income', 'customer', 'wholesale']):
                confidence = 0.7
                reason = "Sales/revenue pattern detected"
        
        elif 'EXPENSES' in sheet.upper():
            if any(word in source_lower for word in ['expense', 'cost', 'purchase', 'bill', 'payment']):
                confidence = 0.6
                reason = "Expense pattern detected"
        
        elif 'LAB' in sheet.upper():
            if any(word in source_lower for word in ['lab', 'test', 'testing', 'analysis']):
                confidence = 0.9
                reason = "Lab/testing pattern detected"
        
        elif 'REGISTER' in sheet.upper():
            if any(word in source_lower for word in ['reg', 'register', 'pos', 'cash']):
                confidence = 0.8
                reason = "Register/POS pattern detected"
        
        # Company-specific analysis
        if 'NUGZ' in sheet.upper():
            if any(word in source_lower for word in ['nugz', 'emeralds', 'guys', 'wholesale']):
                confidence = max(confidence, 0.6)
                reason = "NUGZ company pattern detected"
        
        elif 'JGD' in sheet.upper():
            if any(word in source_lower for word in ['jgd', 'cannabis', 'dist']):
                confidence = max(confidence, 0.6)
                reason = "JGD company pattern detected"
        
        return confidence, reason
    
    def _find_best_header_for_source(self, source_lower: str, headers: List[str]) -> str:
        """Find the best matching header for a source from actual available headers."""
        if not headers:
            return None  # No headers available
        
        best_header = headers[0]  # Default to first header if no better match
        best_score = 0.0
        
        for header in headers:
            header_lower = header.lower()
            
            # Calculate similarity score
            score = self.calculate_similarity(source_lower, header_lower)
            
            # Boost score for exact word matches
            source_words = set(source_lower.split())
            header_words = set(header_lower.split())
            word_overlap = len(source_words.intersection(header_words))
            if len(header_words) > 0:
                score += (word_overlap / len(header_words)) * 0.3
            
            if score > best_score:
                best_score = score
                best_header = header
        
        return best_header
    
    def get_available_headers_for_sheet(self, sheet_name: str, layout_map: Dict) -> List[str]:
        """Get all available headers for a specific sheet."""
        if sheet_name not in layout_map:
            return []
        
        sheet_data = layout_map[sheet_name]
        if not isinstance(sheet_data, dict) or 'headers' not in sheet_data:
            return []
        
        return list(sheet_data['headers'].keys())
    
    def get_available_sheets_and_headers(self, layout_map: Dict) -> Dict[str, List[str]]:
        """Get all available sheets and their headers for AI rule generation."""
        available_options = {}
        
        for sheet_name, sheet_data in layout_map.items():
            if isinstance(sheet_data, dict) and 'headers' in sheet_data:
                headers = list(sheet_data['headers'].keys())
                if headers:  # Only include sheets with headers
                    available_options[sheet_name] = headers
        
        return available_options
    
    def _deduplicate_suggestions(self, suggestions: List[Dict]) -> List[Dict]:
        """Remove duplicate suggestions and merge similar ones."""
        unique_suggestions = {}
        
        for suggestion in suggestions:
            key = f"{suggestion['source']}_{suggestion['target_sheet']}_{suggestion['target_header']}"
            
            if key not in unique_suggestions:
                unique_suggestions[key] = suggestion
            else:
                # Merge confidence scores for duplicate suggestions
                existing = unique_suggestions[key]
                existing['confidence'] = max(existing['confidence'], suggestion['confidence'])
                if suggestion['confidence'] > existing['confidence']:
                    existing['reason'] = suggestion['reason']
        
        return list(unique_suggestions.values())
    
    def match_transaction(self, transaction: Dict) -> Optional[Dict]:
        """Match a transaction to the best rule with confidence score (compatibility method)."""
        try:
            source = transaction.get('source', '').strip()
            company = transaction.get('company', '').strip()
            
            if not source:
                logging.warning(f"Transaction has no source: {transaction}")
                return None
            
            # Use enhanced matching
            match_result = self.find_best_match(source, company)
            
            if match_result.matched:
                return {
                    'rule': match_result.matched_rule,
                    'confidence': match_result.confidence,
                    'matched_source': match_result.matched_rule['source'],
                    'transaction_source': source,
                    'match_type': match_result.match_type
                }
            
            return None
            
        except Exception as e:
            logging.error(f"Error matching transaction: {e}")
            return None
    
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
                    
                    # Update learning from successful match
                    self.update_threshold_from_match(
                        transaction.get('company', ''),
                        transaction.get('source', ''),
                        match_result['confidence'],
                        True
                    )
                else:
                    results['unmatched'].append(transaction)
                    
                    # Update learning from failed match
                    self.update_threshold_from_match(
                        transaction.get('company', ''),
                        transaction.get('source', ''),
                        0.0,
                        False
                    )
            
            # Calculate match rate
            if results['total_processed'] > 0:
                results['match_rate'] = len(results['matched']) / results['total_processed']
            
            logging.info(f"Enhanced batch matching complete: {len(results['matched'])} matched, {len(results['unmatched'])} unmatched")
            return results
            
        except Exception as e:
            logging.error(f"Error in enhanced batch matching: {e}")
            return {'matched': [], 'unmatched': transactions, 'total_processed': len(transactions), 'match_rate': 0.0}

def main():
    """Test enhanced AI rule matcher."""
    print("ENHANCED AI RULE MATCHER TEST")
    print("=" * 60)
    
    matcher = AIEnhancedRuleMatcher()
    
    # Load rules
    if matcher.load_rules_from_database():
        print(f"✅ Loaded {len(matcher.rules_cache)} rules into enhanced cache")
        
        # Test with sample transactions
        test_transactions = [
            {'source': 'WALMART', 'amount': 25.50, 'company': 'JGD'},
            {'source': 'SALE TO LAUGHING HYENA', 'amount': 200.00, 'company': 'NUGZ'},
            {'source': 'PAYROLL 123', 'amount': 500.00, 'company': 'JGD'},
            {'source': 'UNKNOWN SOURCE', 'amount': 50.00, 'company': 'TEST'}
        ]
        
        # Test individual matching
        print(f"\nTesting enhanced individual matches:")
        for transaction in test_transactions:
            match = matcher.match_transaction(transaction)
            if match:
                print(f"  '{transaction['source']}' → '{match['matched_source']}' ({match['match_type']}: {match['confidence']:.2f})")
            else:
                print(f"  '{transaction['source']}' → No match")
        
        # Test batch matching
        print(f"\nTesting enhanced batch matching:")
        batch_results = matcher.batch_match_transactions(test_transactions)
        
        print(f"  Total: {batch_results['total_processed']}")
        print(f"  Matched: {len(batch_results['matched'])}")
        print(f"  Unmatched: {len(batch_results['unmatched'])}")
        print(f"  Match rate: {batch_results['match_rate']:.2%}")
        
        # Show statistics
        stats = matcher.get_match_statistics()
        print(f"\n📊 Enhanced Matcher Statistics:")
        print(f"  Total rules: {stats['total_rules']}")
        print(f"  Learned variations: {stats['learned_variations']}")
        print(f"  Company thresholds: {stats['company_thresholds']}")
        print(f"  Match history: {stats['match_history_count']}")
        
    else:
        print("❌ Failed to load rules")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
Rule Suggestion Review Interface
Allows users to review, approve, or reject AI-generated rule suggestions
"""

import json
import time
from pathlib import Path
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher

def display_suggestions(suggestions):
    """Display rule suggestions in a formatted way."""
    if not suggestions:
        print("📭 No pending rule suggestions found.")
        return
    
    print(f"\n📋 PENDING RULE SUGGESTIONS ({len(suggestions)} total)")
    print("=" * 80)
    
    for i, suggestion in enumerate(suggestions, 1):
        print(f"\n{i}. SUGGESTION ID: {suggestion.get('id', 'N/A')}")
        print(f"   Source: '{suggestion['source']}'")
        print(f"   Target: {suggestion['target_sheet']} → {suggestion['target_header']}")
        print(f"   Company: {suggestion.get('company', 'Unknown')}")
        print(f"   Confidence: {suggestion['confidence']:.2f}")
        print(f"   Reason: {suggestion.get('reason', 'N/A')}")
        print(f"   Suggested by: {suggestion.get('suggested_by', 'AI Analysis')}")
        
        # Show timestamp
        timestamp = suggestion.get('timestamp', 0)
        if timestamp:
            time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            print(f"   Generated: {time_str}")
        
        print("-" * 60)

def review_suggestions():
    """Main function to review rule suggestions."""
    print("🧠 AI RULE SUGGESTION REVIEW")
    print("=" * 50)
    
    try:
        # Initialize AI matcher
        ai_matcher = AIEnhancedRuleMatcher()
        
        # Get pending suggestions
        suggestions = ai_matcher.get_pending_rule_suggestions()
        
        if not suggestions:
            print("✅ No pending rule suggestions to review.")
            return
        
        # Display suggestions
        display_suggestions(suggestions)
        
        # Interactive review
        print(f"\n🎯 REVIEW OPTIONS:")
        print("  Enter suggestion number to approve (e.g., '1')")
        print("  Enter 'r1' to reject suggestion 1 (e.g., 'r1')")
        print("  Enter 'all' to approve all suggestions")
        print("  Enter 'skip' to skip all suggestions")
        print("  Enter 'quit' to exit")
        
        while True:
            choice = input("\nEnter your choice: ").strip().lower()
            
            if choice == 'quit':
                print("👋 Exiting review interface.")
                break
            
            elif choice == 'skip':
                print("⏭️ Skipping all suggestions.")
                break
            
            elif choice == 'all':
                print("✅ Approving all suggestions...")
                approved_count = 0
                for suggestion in suggestions:
                    if ai_matcher.approve_rule_suggestion(suggestion['id']):
                        approved_count += 1
                        print(f"  ✅ Approved: {suggestion['source']}")
                    else:
                        print(f"  ❌ Failed to approve: {suggestion['source']}")
                
                print(f"\n📊 Approved {approved_count}/{len(suggestions)} suggestions.")
                break
            
            elif choice.startswith('r') and choice[1:].isdigit():
                # Reject suggestion
                suggestion_num = int(choice[1:]) - 1
                if 0 <= suggestion_num < len(suggestions):
                    suggestion = suggestions[suggestion_num]
                    reason = input(f"Enter rejection reason for '{suggestion['source']}': ").strip()
                    
                    if ai_matcher.reject_rule_suggestion(suggestion['id'], reason):
                        print(f"❌ Rejected: {suggestion['source']}")
                        suggestions.pop(suggestion_num)  # Remove from display list
                        
                        if not suggestions:
                            print("📭 No more suggestions to review.")
                            break
                    else:
                        print(f"❌ Failed to reject: {suggestion['source']}")
                else:
                    print("❌ Invalid suggestion number.")
            
            elif choice.isdigit():
                # Approve suggestion
                suggestion_num = int(choice) - 1
                if 0 <= suggestion_num < len(suggestions):
                    suggestion = suggestions[suggestion_num]
                    
                    if ai_matcher.approve_rule_suggestion(suggestion['id']):
                        print(f"✅ Approved: {suggestion['source']} → {suggestion['target_sheet']}/{suggestion['target_header']}")
                        suggestions.pop(suggestion_num)  # Remove from display list
                        
                        if not suggestions:
                            print("📭 No more suggestions to review.")
                            break
                    else:
                        print(f"❌ Failed to approve: {suggestion['source']}")
                else:
                    print("❌ Invalid suggestion number.")
            
            else:
                print("❌ Invalid choice. Please try again.")
        
        print("\n🎉 Rule suggestion review completed!")
        
    except Exception as e:
        print(f"❌ Error during review: {e}")

def show_suggestion_stats():
    """Show statistics about rule suggestions."""
    suggestions_file = Path("config/pending_rule_suggestions.json")
    
    if not suggestions_file.exists():
        print("📊 No rule suggestions file found.")
        return
    
    try:
        with open(suggestions_file, 'r') as f:
            all_suggestions = json.load(f)
        
        pending = [s for s in all_suggestions if s.get('status') == 'pending']
        approved = [s for s in all_suggestions if s.get('status') == 'approved']
        rejected = [s for s in all_suggestions if s.get('status') == 'rejected']
        
        print("📊 RULE SUGGESTION STATISTICS")
        print("=" * 40)
        print(f"Total suggestions: {len(all_suggestions)}")
        print(f"Pending review: {len(pending)}")
        print(f"Approved: {len(approved)}")
        print(f"Rejected: {len(rejected)}")
        
        if approved:
            print(f"\n✅ Recently approved:")
            for suggestion in approved[-3:]:  # Show last 3 approved
                print(f"  • {suggestion['source']} → {suggestion['target_sheet']}")
        
    except Exception as e:
        print(f"❌ Error loading statistics: {e}")

def main():
    """Main function."""
    print("🧠 AI RULE SUGGESTION MANAGEMENT")
    print("=" * 50)
    
    while True:
        print("\n📋 OPTIONS:")
        print("  1. Review pending suggestions")
        print("  2. Show suggestion statistics")
        print("  3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == '1':
            review_suggestions()
        elif choice == '2':
            show_suggestion_stats()
        elif choice == '3':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    main() 
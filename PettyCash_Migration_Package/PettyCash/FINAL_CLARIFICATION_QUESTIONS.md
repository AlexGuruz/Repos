# Petty Cash Sorter - Final Clarification Questions

Based on your responses, I need a few final clarifications before implementing. Please respond to each section:

## 1. DATA COMPARISON LOGIC

**Your preference:** Compare existing data with new CSV data, only process new transactions

**Question:** How should we determine if a transaction is "new"?
- [ ] Compare by hash ID (Row+Date+Source+Amount+Company)
- [y] Compare by row number only
- [ ] Compare by date + source + amount
- [ ] Other: ________________

## 2. AI RULE SUGGESTIONS

**Your preference:** AI suggests new rules based on user and AI communications

**Questions:**
- When should AI suggest new rules?
- [y] Automatically for any unmatched transaction
- [ ] Only when user requests suggestions
- [ ] Only for high-frequency unmatched sources (appears 3+ times)
- [ ] Other: ________________

- How should you confirm new rules via Discord bot?
- [] Simple yes/no commands (`/confirm_rule yes` or `/confirm_rule no`)
- [y] Interactive prompts with rule details
- [y] Batch confirmation for multiple rules
- [ ] Other: ________________

## 3. CONFIDENCE SCORE THRESHOLDS

**Your preference:** 1-10 confidence score format

**Question:** What should trigger different confidence levels?
- [ ] 8-10: Exact match, 5-7: Fuzzy match, 1-4: Weak match
- [y] 9-10: Exact, 7-8: Close, 5-6: Similar, 1-4: Weak
- [ ] Custom thresholds: ________________

## 4. FAILURE ANALYSIS & ROUTING

**Your preference:** Flag failures for review, route to AI rule manager or user review

**Questions:**
- What types of failures should go to AI rule manager?
- [y] No matching rule found
- [ ] Low confidence matches (< 5/10)
- [ ] Both
- [ ] Other: ________________

- What types should go to user review?
- [ ] Data parsing errors (invalid dates, amounts)
- [ ] Google Sheets update failures
- [y] Both
- [ ] Other: ________________

## 5. DISCORD BOT COMMANDS

**Your preference:** Discord bots for AI rule manager

**Questions:**
- Which Discord commands do you want? im not sure yet lets make sure the script is working first before working on tying our script into discord bots
- [ ] `/review_unmatched` - Show unmatched transactions
- [ ] `/suggest_rules` - AI suggests new rules
- [ ] `/confirm_rule` - Confirm a suggested rule
- [ ] `/status` - Show processing status
- [ ] `/retry_failed` - Retry failed transactions
- [ ] Other: ________________

## 6. DATABASE QUERY FORMAT

**Your preference:** Unmatched transactions via database query

**Question:** What format should the query results be?
- [ ] Simple list of unmatched sources
- [y] Detailed transaction list with AI suggestions
- [y] Summary report with counts
- [ ] Other: ________________

## 7. WORKFLOW PROCESSING

**Questions:**
- Should the system process transactions in real-time as they're downloaded?
- [ ] Yes, process each transaction immediately
- [y] No, batch them first, then process
- [ ] Other: ________________

- How many transactions do you typically process per run? the first batch will be 2000 to get it caught up to the current transactions. later i will feed in older years of transactions which exceed 4000, but i dont mind if they are broken down to be handled in smaller batches. after the catch up process the script will run every night at midnight and should only have 10-20 transactions to handle
- [y] Less than 100
- [ ] 100-500
- [ ] 500-1000
- [ ] More than 1000
- [ ] Other: ________________

## 8. AI LEARNING

**Questions:**
- Should the AI learn from successful matches to improve future matching?
- [y] Yes, automatically adjust confidence thresholds
- [ ] Yes, but only with user confirmation
- [ ] No, keep rules static
- [ ] Other: ________________

- How detailed should the audit log be?
- [y] Every status change (downloaded → preprocessed → matched → processed)
- [ ] Only major events (start, complete, errors)
- [ ] Custom: ________________

## 9. ERROR HANDLING DETAILS

**Your preference:** Retry automatically, skip and log, ask user what to do

**Questions:**
- How many retries for network errors?
- [ ] 3 times
- [ ] 5 times
- [y] Infinite (until success)
- [ ] Other: ________________

- Should the system stop on first data parsing error?
- [ ] Yes, stop and ask user
- [y] No, skip and continue processing but be sure to log and send the data to user for review and changes needed
- [ ] Other: ________________

## 10. ADDITIONAL FEATURES

**Any other features or requirements you want?**




---

## 🎯 IMPLEMENTATION PLAN
Once you respond to these questions, I'll create:
- Complete database schema
- Detailed workflow steps
- Discord bot integration plan
- Error handling strategy
- File structure and naming conventions 
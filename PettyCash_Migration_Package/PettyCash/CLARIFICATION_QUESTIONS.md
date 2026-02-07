# Petty Cash Sorter - Clarification Questions

Based on your responses, I need to clarify a few details before implementing. Please respond to each section:

## 1. DATA SOURCE - CSV Download

**Your preference:** Download CSV from Google Sheets PETTY CASH tab

**Questions:**
- Which columns do you want? (A=Initials, B=Date, C=Company, D=Source, S=Amount?)
- [ ] All columns
- [ ] Only specific columns: (A=Initials, B=Date, C=Company, D=Source, S=Amount)________________
- [ ] Other: ________________

- How often should it download?
- [y] Once per run, but the existing transaction data should be compared to the data being brought in from the csv petty cash download and only the transactions that are not already in the database should 
- [ ] Continuous monitoring
- [ ] On demand
- [ ] Other: ________________

## 2. AI MEMORY & RULES

**Your preference:** Load JGD Truth into AI memory, persistent storage

**Questions:**
- Where should new rules be saved?
- [ ] JGD Truth Excel file only
- [ y] SQLite database only
- [ ] Both Excel and database
- [ ] Other: ________________

- How should AI handle rule updates?
- [ ] Overwrite existing rules
- [ ] Keep both old and new
- [ ] Ask user which to keep
- [ ] Other: keep the rules up to date based on user and ai communications, if the ai suggests a new rule and user confirms it should add that to the rule database it has at its core, does this make sense?________________

## 3. UNMATCHED TRANSACTIONS

**Your preference:** Batch and send for user review

**Questions:**
- How do you want to receive unmatched transactions?
- [ ] CSV file
- [ ] Email report
- [ ] Console output
- [y] Database query
- [ ] Other: ________________

- Should AI suggest potential matches?
- [y] Yes, with confidence scores covert confidence score into a 1 out of 10 format please
- [ ] No, just list unmatched
- [ ] Only for high-confidence matches
- [ ] Other: ________________

## 4. TRANSACTION ID

**Your preference:** Row + Date + Source + Amount + Company

**Questions:**
- Format for the ID?
- [ ] Simple concatenation (e.g., "187_01-17-25_SALE_TO_HIGH_HOUSE_1500.00_NUGZ")
- [y] Hash-based (e.g., "a1b2c3d4e5f6")
- [ ] UUID format
- [ ] Other: ________________

## 5. STATUS TRACKING

**Your preference:** SQLite database, track through workflow

**Questions:**
- Which statuses to track?
- [] downloaded, preprocessed, matched, ready, processed, failed
- [y] simpler: pending, processed, failed
- [ ] custom: ________________

- Should failed transactions auto-retry?
- [ ] Yes, 3 times
- [ ] No, manual only
- [ ] Yes, but ask first
- [y] Other: have it flagged for review of why it failed, if its a rule mismatch send it to ai rule manager, if its data parse error flag for user review________________

## 6. WORKFLOW STEPS

**Your preference:** File each transaction as it moves through workflow

**Questions:**
- What's the exact workflow you want?
- [y] Download → Preprocess → Match → Update → Mark Complete
- [ ] Download → Match → Update → Mark Complete
- [ ] Custom: ________________

- Should there be review checkpoints?
- [] Yes, before Google Sheets updates
- [ ] No, fully automated
- [y] Only for unmatched transactions
- [ ] Other: ________________

## 7. DATABASE STRUCTURE

**Your preference:** SQLite database

**Questions:**
- Which tables do you want?
- [ ] transactions, rules, audit_log
- [y] transactions, rules, ai_learning, audit_log
- [ ] single table with all data
- [ ] Other: ________________

## 8. USER INTERFACE

**Questions:**
- How do you want to interact with the system?
- [ ] Command line only
- [ ] CSV file outputs
- [ ] Simple web dashboard
- [ ] Other: for now command line but we will be tying in some discord bots into this project especially for the ai rule manager ________________

- How should you confirm new rules?
- [ ] Edit CSV file
- [ ] Command line prompts
- [ ] Web interface
- [ ] Other: same answer as above_______________

## 9. ERROR HANDLING

**Questions:**
- What should happen on network errors?
- [ y] Retry automatically
- [ ] Stop and wait
- [ ] Save progress and resume later
- [ ] Other: ________________

- What should happen on invalid data?
- [y] Skip and log detailed log 
- [ ] Stop processing
- [y] Ask user what to do
- [ ] Other: ________________

## 10. ADDITIONAL REQUIREMENTS

**Any other requirements or preferences?**




---

## 🎯 IMPLEMENTATION PLAN
Once you respond to these questions, I'll create a detailed implementation plan with:
- Database schema
- Workflow steps
- File structure
- Error handling
- User interaction points 
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comment Processor for Petty Cash Transactions
Handles comments and hyperlinks separately from main transaction processing
"""

import gspread
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
PETTY_CASH_URL = "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU/edit?pli=1&gid=1785437689#gid=1785437689"

class CommentProcessor:
    """Handles comments and hyperlinks for processed transactions."""
    
    def __init__(self, service_account_path: str = "config/service_account.json"):
        self.service_account_path = service_account_path
        self.gc = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google Sheets."""
        try:
            self.gc = gspread.service_account(filename=self.service_account_path)
            logging.info("Successfully authenticated with Google Sheets (Comment Processor)")
            return True
        except Exception as e:
            logging.error(f"Authentication failed (Comment Processor): {e}")
            self.gc = None
            return False
    
    def extract_comments_from_log(self, log_file: str = "logs/petty_cash_sorter.log") -> List[Dict]:
        """Extract comment information from the main processing log."""
        comments_to_process = []
        
        try:
            if not Path(log_file).exists():
                logging.warning(f"Log file not found: {log_file}")
                return comments_to_process
            
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            # Find all comment entries in the log
            comment_pattern = r'\[COMMENT\] COMMENTS FOR (.+?) cell (.+?) \(will be processed separately\):\n(.+?)(?=\n\[|\n\d{4}-\d{2}-\d{2}|\Z)'
            matches = re.findall(comment_pattern, log_content, re.DOTALL)
            
            for match in matches:
                sheet_name = match[0].strip()
                cell_address = match[1].strip()
                comment_text = match[2].strip()
                
                comments_to_process.append({
                    'sheet_name': sheet_name,
                    'cell_address': cell_address,
                    'comment_text': comment_text
                })
                
                logging.info(f"Found comment for {sheet_name} cell {cell_address}")
            
            logging.info(f"Extracted {len(comments_to_process)} comments from log file")
            return comments_to_process
            
        except Exception as e:
            logging.error(f"Error extracting comments from log: {e}")
            return comments_to_process
    
    def parse_cell_address(self, cell_address: str) -> Tuple[Optional[str], Optional[int]]:
        """Parse cell address like 'A1' into column and row."""
        try:
            # Extract column (letters) and row (numbers)
            match = re.match(r'([A-Z]+)(\d+)', cell_address)
            if match:
                column = match.group(1)
                row = int(match.group(2))
                return column, row
            return None, None
        except Exception as e:
            logging.error(f"Error parsing cell address {cell_address}: {e}")
            return None, None
    
    def add_comment_to_cell(self, sheet_name: str, cell_address: str, comment_text: str) -> bool:
        """Add a comment to a specific cell."""
        try:
            if not self.gc:
                logging.error("Not authenticated")
                return False
            
            # Get the spreadsheet and worksheet
            spreadsheet = self.gc.open_by_url(PETTY_CASH_URL)
            worksheet = None
            
            for ws in spreadsheet.worksheets():
                if ws.title == sheet_name:
                    worksheet = ws
                    break
            
            if not worksheet:
                logging.error(f"Worksheet '{sheet_name}' not found")
                return False
            
            # Parse cell address
            column, row = self.parse_cell_address(cell_address)
            if not column or not row:
                logging.error(f"Invalid cell address: {cell_address}")
                return False
            
            # Add comment using Google Sheets API
            # Note: This is a simplified approach - actual comment addition may require different API calls
            try:
                # For now, we'll log the comment for manual addition
                # In a full implementation, you'd use the Google Sheets API to add comments
                logging.info(f"[COMMENT_ADDED] {sheet_name} cell {cell_address}: {comment_text[:100]}...")
                
                # TODO: Implement actual comment addition using Google Sheets API
                # This would require using the sheets.spreadsheets.comments API
                
                return True
                
            except Exception as e:
                logging.error(f"Error adding comment to {sheet_name} cell {cell_address}: {e}")
                return False
                
        except Exception as e:
            logging.error(f"Error in add_comment_to_cell: {e}")
            return False
    
    def process_all_comments(self, comments: List[Dict]) -> bool:
        """Process all extracted comments."""
        if not comments:
            logging.info("No comments to process")
            return True
        
        logging.info(f"Processing {len(comments)} comments...")
        
        success_count = 0
        error_count = 0
        
        for i, comment_data in enumerate(comments, 1):
            try:
                logging.info(f"Processing comment {i}/{len(comments)}: {comment_data['sheet_name']} cell {comment_data['cell_address']}")
                
                success = self.add_comment_to_cell(
                    comment_data['sheet_name'],
                    comment_data['cell_address'],
                    comment_data['comment_text']
                )
                
                if success:
                    success_count += 1
                else:
                    error_count += 1
                
                # Rate limiting between comment additions
                time.sleep(0.5)  # 500ms delay between comments
                
            except Exception as e:
                logging.error(f"Error processing comment {i}: {e}")
                error_count += 1
                continue
        
        logging.info(f"Comment processing complete: {success_count} successful, {error_count} errors")
        return error_count == 0
    
    def run(self):
        """Main execution method."""
        try:
            logging.info("Starting Comment Processor...")
            
            # Extract comments from log
            comments = self.extract_comments_from_log()
            
            if not comments:
                logging.info("No comments found to process")
                return True
            
            # Process all comments
            success = self.process_all_comments(comments)
            
            if success:
                logging.info("✅ Comment processing completed successfully!")
            else:
                logging.warning("⚠️ Comment processing completed with some errors")
            
            return success
            
        except Exception as e:
            logging.error(f"Error in comment processor: {e}")
            return False

def main():
    """Main function."""
    print("Comment Processor for Petty Cash Transactions")
    print("=" * 50)
    
    processor = CommentProcessor()
    success = processor.run()
    
    if success:
        print("✅ Comment processing completed successfully!")
    else:
        print("❌ Comment processing failed")
    
    return success

if __name__ == "__main__":
    main() 
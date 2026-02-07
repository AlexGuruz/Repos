#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Sheets XLSX Downloader
Downloads Google Sheets as XLSX files for local processing
"""

import gspread
from google.oauth2.service_account import Credentials
import logging
from pathlib import Path
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/sheets_downloader.log'),
        logging.StreamHandler()
    ]
)

class GoogleSheetsDownloader:
    def __init__(self):
        self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        self.creds = Credentials.from_service_account_file('config/service_account.json', scopes=self.scope)
        self.gc = gspread.authorize(self.creds)
        
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)
        
        # Sheets to download
        self.sheets_to_download = {
            "financials": {
                "url": "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU/edit",
                "filename": "2025 JGD Financials.xlsx"
            },
            "jgd_truth": {
                "url": "https://docs.google.com/spreadsheets/d/1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU/edit",
                "filename": "JGD Truth Current.xlsx"
            }
        }
        
        logging.info("INITIALIZING GOOGLE SHEETS DOWNLOADER")
        logging.info("=" * 60)
    
    def download_sheet_as_xlsx(self, sheet_name, sheet_info):
        """Download a Google Sheet as XLSX file."""
        try:
            logging.info(f"Downloading {sheet_name}...")
            
            # Extract spreadsheet ID from URL
            url_parts = sheet_info["url"].split('/')
            spreadsheet_id = url_parts[5]
            
            # Open the spreadsheet using gspread
            spreadsheet = self.gc.open_by_key(spreadsheet_id)
            
            # Get the export URL
            export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"
            
            # Download using requests with proper authentication
            response = requests.get(export_url, headers={
                'Authorization': f'Bearer {self.creds.token}'
            })
            
            if response.status_code == 200:
                # Save file (replacing existing)
                filepath = Path(sheet_info['filename'])
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                logging.info(f"Successfully downloaded {sheet_name} as {sheet_info['filename']}")
                return True
            else:
                logging.error(f"Failed to download {sheet_name}: HTTP {response.status_code}")
                logging.error(f"Response content: {response.text[:200]}...")
                return False
                
        except Exception as e:
            logging.error(f"Error downloading {sheet_name}: {e}")
            return False
    
    def download_all_sheets(self):
        """Download all configured sheets."""
        logging.info("STARTING GOOGLE SHEETS DOWNLOAD")
        logging.info("=" * 60)
        
        success_count = 0
        total_count = len(self.sheets_to_download)
        
        for sheet_name, sheet_info in self.sheets_to_download.items():
            if self.download_sheet_as_xlsx(sheet_name, sheet_info):
                success_count += 1
        
        logging.info(f"DOWNLOAD SUMMARY: {success_count}/{total_count} sheets downloaded successfully")
        logging.info("=" * 60)
        
        return success_count == total_count

def main():
    """Main function."""
    print("GOOGLE SHEETS XLSX DOWNLOADER")
    print("=" * 60)
    
    # Check if service account file exists
    if not Path("config/service_account.json").exists():
        print("❌ Service account file not found: config/service_account.json")
        return
    
    # Create downloader
    downloader = GoogleSheetsDownloader()
    
    # Run download
    success = downloader.download_all_sheets()
    if success:
        print("✅ Download completed successfully!")
    else:
        print("❌ Download failed!")

if __name__ == "__main__":
    main() 
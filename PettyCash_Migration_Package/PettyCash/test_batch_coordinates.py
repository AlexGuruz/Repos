#!/usr/bin/env python3
"""
Test Batch Coordinates
Test the new batch coordinate finding functionality
"""

from google_sheets_integration import GoogleSheetsIntegration
from csv_downloader_fixed import CSVDownloader

def main():
    """Test batch coordinate finding."""
    print("TESTING BATCH COORDINATE FINDING")
    print("=" * 40)
    
    try:
        # Initialize components
        sheets_integration = GoogleSheetsIntegration()
        downloader = CSVDownloader()
        
        # Test connection
        if not sheets_integration.test_connection():
            print("Failed to connect to Google Sheets")
            return
        
        print("Connected to Google Sheets successfully")
        
        # Download some transactions
        transactions = downloader.download_petty_cash_data()
        if not transactions:
            print("No transactions found")
            return
        
        print(f"Downloaded {len(transactions)} transactions")
        
        # Create sample coordinate requests
        coordinate_requests = []
        sample_transactions = transactions[:5]  # Test with 5 transactions
        
        for transaction in sample_transactions:
            # Simulate some common target sheets and headers
            test_targets = [
                {'target_sheet': 'INCOME', 'target_header': 'REGISTERS'},
                {'target_sheet': 'INCOME', 'target_header': '(N) WHOLESALE'},
                {'target_sheet': 'NUGZ C.O.G.', 'target_header': 'WALMART'},
            ]
            
            for target in test_targets:
                coordinate_requests.append({
                    'target_sheet': target['target_sheet'],
                    'target_header': target['target_header'],
                    'date': transaction['date']
                })
        
        print(f"Created {len(coordinate_requests)} coordinate requests")
        
        # Test batch coordinate finding
        print("\nTesting batch coordinate finding...")
        results = sheets_integration.batch_find_target_cell_coordinates(coordinate_requests)
        
        print(f"Batch results: {len(results)} results")
        
        # Show results
        successful_finds = 0
        for request_key, coords in results.items():
            if coords:
                successful_finds += 1
                print(f"✅ {request_key}: Row {coords['row']}, Col {coords['col']}")
            else:
                print(f"❌ {request_key}: Not found")
        
        print(f"\nSuccess rate: {successful_finds}/{len(results)} ({successful_finds/len(results)*100:.1f}%)")
        
        # Compare with individual method
        print("\nComparing with individual method...")
        individual_success = 0
        for request in coordinate_requests[:3]:  # Test first 3
            coords = sheets_integration.find_target_cell_coordinates(
                request['target_sheet'],
                request['target_header'],
                request['date']
            )
            if coords:
                individual_success += 1
                print(f"✅ Individual: {request['target_sheet']} -> {request['target_header']}: Row {coords['row']}, Col {coords['col']}")
            else:
                print(f"❌ Individual: {request['target_sheet']} -> {request['target_header']}: Not found")
        
        print(f"Individual success rate: {individual_success}/3 ({individual_success/3*100:.1f}%)")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 
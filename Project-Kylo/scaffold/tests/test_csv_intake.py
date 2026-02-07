"""
Tests for CSV intake functionality
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch

from services.intake.csv_downloader import get_file_fingerprint, validate_csv_content, get_csv_metadata
from services.intake.csv_processor import PettyCashCSVProcessor, validate_transaction


class TestCSVDownloader:
    """Test CSV downloader functionality"""
    
    def test_get_file_fingerprint(self):
        """Test file fingerprint generation"""
        content1 = "test,csv,content"
        content2 = "test,csv,content"
        content3 = "different,content"
        
        fp1 = get_file_fingerprint(content1)
        fp2 = get_file_fingerprint(content2)
        fp3 = get_file_fingerprint(content3)
        
        assert fp1 == fp2  # Same content should have same fingerprint
        assert fp1 != fp3  # Different content should have different fingerprint
        assert len(fp1) == 64  # SHA256 hex digest length
    
    def test_validate_csv_content(self):
        """Test CSV content validation"""
        # Valid CSV (matching actual schema: initials,date,company,description,amount)
        valid_csv = "initials,date,company,description,amount\nAB,01/01/2025,NUGZ,Test transaction,100.00"
        assert validate_csv_content(valid_csv, min_rows=1) is True
        
        # Invalid CSV (no commas)
        invalid_csv = "date amount company description"
        assert validate_csv_content(invalid_csv, min_rows=1) is False
        
        # Too few rows
        short_csv = "date,amount\n01/01/2025,100.00"
        assert validate_csv_content(short_csv, min_rows=5) is False
    
    def test_get_csv_metadata(self):
        """Test CSV metadata extraction"""
        csv_content = "initials,date,company,description,amount\nAB,01/01/2025,NUGZ,Test transaction,100.00"
        metadata = get_csv_metadata(csv_content)
        
        assert 'file_fingerprint' in metadata
        assert 'total_lines' in metadata
        assert 'non_empty_lines' in metadata
        assert 'file_size_bytes' in metadata
        assert metadata['total_lines'] == 2
        assert metadata['non_empty_lines'] == 2


class TestCSVProcessor:
    """Test CSV processor functionality"""
    
    def test_csv_processor_initialization(self):
        """Test CSV processor initialization"""
        csv_content = "initials,date,company,description,amount\nAB,01/01/2025,NUGZ,Test transaction,100.00"
        processor = PettyCashCSVProcessor(csv_content, header_rows=1)
        
        assert processor.csv_content == csv_content
        assert processor.header_rows == 1
        assert processor.file_fingerprint is not None
        assert len(processor.seen_rows) == 0
    
    def test_parse_valid_transaction(self):
        """Test parsing valid transaction row"""
        csv_content = "initials,date,company,description,amount\nAB,01/01/2025,NUGZ,Test transaction,100.00"
        processor = PettyCashCSVProcessor(csv_content, header_rows=1)
        
        transactions = list(processor.parse_transactions())
        
        assert len(transactions) == 1
        txn = transactions[0]
        
        assert txn['company_id'] == 'NUGZ'
        assert txn['posted_date'] == '2025-01-01'
        assert txn['amount_cents'] == 10000  # $100.00 in cents
        assert txn['description'] == 'Test transaction'
        assert txn['counterparty_name'] == 'AB'  # Employee initials
        assert 'txn_uid' in txn
        assert 'hash_norm' in txn
        assert 'business_hash' in txn
    
    def test_parse_invalid_company(self):
        """Test parsing transaction with invalid company"""
        csv_content = "initials,date,company,description,amount\nAB,01/01/2025,INVALID,Test transaction,100.00"
        processor = PettyCashCSVProcessor(csv_content, header_rows=1)
        
        transactions = list(processor.parse_transactions())
        assert len(transactions) == 0  # Invalid company should be skipped
    
    def test_parse_invalid_date(self):
        """Test parsing transaction with invalid date"""
        csv_content = "initials,date,company,description,amount\nAB,invalid-date,NUGZ,Test transaction,100.00"
        processor = PettyCashCSVProcessor(csv_content, header_rows=1)
        
        transactions = list(processor.parse_transactions())
        assert len(transactions) == 0  # Invalid date should be skipped
    
    def test_parse_invalid_amount(self):
        """Test parsing transaction with invalid amount"""
        csv_content = "initials,date,company,description,amount\nAB,01/01/2025,NUGZ,Test transaction,invalid"
        processor = PettyCashCSVProcessor(csv_content, header_rows=1)
        
        transactions = list(processor.parse_transactions())
        assert len(transactions) == 0  # Invalid amount should be skipped
    
    def test_row_deduplication(self):
        """Test row-level deduplication"""
        csv_content = """initials,date,company,description,amount
AB,01/01/2025,NUGZ,Test transaction,100.00
AB,01/01/2025,NUGZ,Test transaction,100.00
CD,01/01/2025,NUGZ,Another transaction,200.00"""
        processor = PettyCashCSVProcessor(csv_content, header_rows=1)
        
        transactions = list(processor.parse_transactions())
        assert len(transactions) == 2  # Duplicate row should be skipped
    
    def test_amount_parsing(self):
        """Test various amount formats"""
        csv_content = """initials,date,company,description,amount
AB,01/01/2025,NUGZ,Positive amount,100.00
CD,01/01/2025,NUGZ,Negative amount,-50.00
EF,01/01/2025,NUGZ,Parentheses negative,(25.00)
GH,01/01/2025,NUGZ,With currency and commas,"$1,234.56" """
        processor = PettyCashCSVProcessor(csv_content, header_rows=1)
        
        transactions = list(processor.parse_transactions())
        assert len(transactions) == 4
        
        amounts = [txn['amount_cents'] for txn in transactions]
        assert 10000 in amounts  # $100.00
        assert -5000 in amounts  # -$50.00
        assert -2500 in amounts  # -$25.00
        assert 123456 in amounts  # $1,234.56
    
    def test_date_parsing(self):
        """Test various date formats"""
        csv_content = """initials,date,company,description,amount
AB,01/15/2025,NUGZ,MM/DD/YYYY,100.00
CD,2025-01-15,NUGZ,YYYY-MM-DD,100.00
EF,01-15-2025,NUGZ,MM-DD-YYYY,100.00
GH,01/15/25,NUGZ,MM/DD/YY,100.00"""
        processor = PettyCashCSVProcessor(csv_content, header_rows=1)
        
        transactions = list(processor.parse_transactions())
        assert len(transactions) == 4
        
        # All should be normalized to YYYY-MM-DD
        for txn in transactions:
            assert txn['posted_date'] == '2025-01-15'
    
    def test_get_processing_stats(self):
        """Test processing statistics"""
        csv_content = """initials,date,company,description,amount
AB,01/01/2025,NUGZ,Test transaction,100.00
AB,01/01/2025,NUGZ,Test transaction,100.00
CD,01/01/2025,NUGZ,Another transaction,200.00"""
        processor = PettyCashCSVProcessor(csv_content, header_rows=1)
        
        # Parse transactions to populate stats
        list(processor.parse_transactions())
        
        stats = processor.get_processing_stats()
        assert stats['total_lines'] == 4  # Including header
        assert stats['data_rows'] == 3
        assert stats['unique_rows_processed'] == 2  # One duplicate skipped
        assert stats['duplicate_rows_skipped'] == 1


class TestTransactionValidation:
    """Test transaction validation"""
    
    def test_valid_transaction(self):
        """Test validation of valid transaction"""
        transaction = {
            'txn_uid': 'test-uuid',
            'company_id': 'NUGZ',
            'posted_date': '2025-01-01',
            'amount_cents': 10000,
            'description': 'Test transaction'
        }
        
        is_valid, errors = validate_transaction(transaction)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_missing_required_fields(self):
        """Test validation with missing required fields"""
        transaction = {
            'txn_uid': 'test-uuid',
            'company_id': 'NUGZ'
            # Missing posted_date, amount_cents, description
        }
        
        is_valid, errors = validate_transaction(transaction)
        assert is_valid is False
        assert len(errors) == 3  # Three missing fields
    
    def test_invalid_company(self):
        """Test validation with invalid company"""
        transaction = {
            'txn_uid': 'test-uuid',
            'company_id': 'INVALID',
            'posted_date': '2025-01-01',
            'amount_cents': 10000,
            'description': 'Test transaction'
        }
        
        is_valid, errors = validate_transaction(transaction)
        assert is_valid is False
        assert any('Invalid company' in error for error in errors)
    
    def test_invalid_amount(self):
        """Test validation with invalid amount"""
        transaction = {
            'txn_uid': 'test-uuid',
            'company_id': 'NUGZ',
            'posted_date': '2025-01-01',
            'amount_cents': 0,  # Zero amount
            'description': 'Test transaction'
        }
        
        is_valid, errors = validate_transaction(transaction)
        assert is_valid is False
        assert any('Amount cannot be zero' in error for error in errors)
    
    def test_invalid_date_format(self):
        """Test validation with invalid date format"""
        transaction = {
            'txn_uid': 'test-uuid',
            'company_id': 'NUGZ',
            'posted_date': 'invalid-date',
            'amount_cents': 10000,
            'description': 'Test transaction'
        }
        
        is_valid, errors = validate_transaction(transaction)
        assert is_valid is False
        assert any('Invalid date format' in error for error in errors)


class TestCSVIntakeIntegration:
    """Integration tests for CSV intake"""
    
    @pytest.fixture
    def sample_csv_content(self):
        """Sample CSV content for testing"""
        return """initials,date,company,description,amount
AB,01/01/2025,NUGZ,Test transaction 1,100.00
CD,01/02/2025,710 EMPIRE,Test transaction 2,200.00
EF,01/03/2025,PUFFIN PURE,Test transaction 3,300.00
GH,01/04/2025,JGD,Test transaction 4,400.00"""
    
    def test_end_to_end_processing(self, sample_csv_content):
        """Test end-to-end CSV processing"""
        processor = PettyCashCSVProcessor(sample_csv_content, header_rows=1)
        transactions = list(processor.parse_transactions())
        
        # Should parse all 4 transactions
        assert len(transactions) == 4
        
        # Validate all transactions
        valid_transactions = []
        for txn in transactions:
            is_valid, errors = validate_transaction(txn)
            if is_valid:
                valid_transactions.append(txn)
            else:
                pytest.fail(f"Transaction validation failed: {errors}")
        
        assert len(valid_transactions) == 4
        
        # Check company distribution (710 EMPIRE maps to EMPIRE, PUFFIN PURE maps to PUFFIN)
        companies = [txn['company_id'] for txn in valid_transactions]
        assert 'NUGZ' in companies
        assert 'EMPIRE' in companies  # 710 EMPIRE aliases to EMPIRE
        assert 'PUFFIN' in companies  # PUFFIN PURE aliases to PUFFIN
        assert 'JGD' in companies
    
    def test_processing_stats_accuracy(self, sample_csv_content):
        """Test that processing stats are accurate"""
        processor = PettyCashCSVProcessor(sample_csv_content, header_rows=1)
        
        # Parse transactions
        transactions = list(processor.parse_transactions())
        
        # Get stats
        stats = processor.get_processing_stats()
        
        # Verify stats
        assert stats['total_lines'] == 5  # Header + 4 data rows
        assert stats['data_rows'] == 4
        assert stats['unique_rows_processed'] == 4
        assert stats['duplicate_rows_skipped'] == 0
        assert len(transactions) == stats['unique_rows_processed']

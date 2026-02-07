#!/usr/bin/env python3
"""Check Kylo_Config structure"""
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", os.path.join(os.path.dirname(__file__), '..', '..', '.secrets', 'service_account.json'))

creds = Credentials.from_service_account_file(
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'],
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)
svc = build('sheets', 'v4', credentials=creds)

spreadsheet_id = '1ZxzOvP14M7syKuZ3EoqaHJUkZoOEcMpgk5adHP9p2no'
vals = svc.spreadsheets().values().get(
    spreadsheetId=spreadsheet_id,
    range='Kylo_Config!A1:AA20'
).execute().get('values', [])

if vals:
    header = vals[0]
    print('Header columns:')
    for i, col in enumerate(header[:20]):
        print(f'  Column {i+1} ({chr(65+i)}): {col}')
    
    if len(vals) > 1:
        print('\nFirst data row:')
        row = vals[1]
        for i, col in enumerate(row[:20]):
            if i < len(header):
                print(f'  {header[i]}: {col}')

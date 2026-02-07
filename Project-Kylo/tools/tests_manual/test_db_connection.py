#!/usr/bin/env python3
import psycopg2

try:
    conn = psycopg2.connect('postgresql://postgres:kylo@localhost:5433/postgres')
    print('✅ Database connection successful!')
    
    # Test query
    with conn.cursor() as cur:
        cur.execute('SELECT version();')
        version = cur.fetchone()
        print(f'✅ PostgreSQL version: {version[0]}')
    
    conn.close()
    print('✅ Connection closed successfully')
    
except Exception as e:
    print(f'❌ Connection failed: {e}')

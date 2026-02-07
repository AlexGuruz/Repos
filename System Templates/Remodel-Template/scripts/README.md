# Scripts

Place utility scripts here for:
- Database setup/migration
- Data loading/export
- Development helpers
- Deployment scripts

## Example Script

```python
#!/usr/bin/env python3
"""Example utility script."""

from yourapp.config.connection_manager import get_connection_context

def main():
    """Example main function."""
    with get_connection_context("entity1") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            print("Connection successful!")

if __name__ == "__main__":
    main()
```

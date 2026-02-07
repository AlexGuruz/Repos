"""
SQL Preprocessor Service

Handles runtime SQL preprocessing for multi-schema mode.
Replaces schema references and manages search paths.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import re
import logging

from yourapp.config.schema_resolver import get_entity_schema, should_use_multi_schema
from yourapp.config.flags import multi_schema_enabled


class SQLPreprocessor:
    """
    Preprocesses SQL queries for multi-schema mode.
    
    Features:
    - Runtime schema substitution (app. -> app_entity1.)
    - Search path management
    - Bounded/regex-safe replacements
    - Backward compatibility with single-schema mode
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._replacement_cache: Dict[str, str] = {}
    
    def preprocess_sql(self, sql: str, entity_id: str, use_shadow: bool = False) -> str:
        """
        Preprocess SQL query for multi-schema mode.
        
        Args:
            sql: Original SQL query
            entity_id: Entity identifier
            use_shadow: If True, use shadow schema
            
        Returns:
            Preprocessed SQL query
        """
        if not multi_schema_enabled() or not should_use_multi_schema(entity_id):
            # No preprocessing needed in single-schema mode
            return sql
        
        # Get target schema name
        target_schema = get_entity_schema(entity_id, use_shadow)
        
        # Check cache first
        cache_key = f"{sql}:{entity_id}:{use_shadow}"
        if cache_key in self._replacement_cache:
            return self._replacement_cache[cache_key]
        
        # Perform schema replacements
        processed_sql = self._replace_schema_references(sql, target_schema)
        
        # Cache the result
        self._replacement_cache[cache_key] = processed_sql
        
        self.logger.debug(f"Preprocessed SQL for {entity_id} -> {target_schema}")
        return processed_sql
    
    def get_local_search_path_sql(self, entity_id: str, use_shadow: bool = False) -> str:
        """
        Generate SQL to set LOCAL search path for a transaction.
        
        Args:
            entity_id: Entity identifier
            use_shadow: If True, use shadow schema
            
        Returns:
            SQL command to set LOCAL search path
        """
        if not multi_schema_enabled() or not should_use_multi_schema(entity_id):
            return "SET LOCAL search_path = app, public;"
        
        target_schema = get_entity_schema(entity_id, use_shadow)
        return f"SET LOCAL search_path = {target_schema}, public;"
    
    def _replace_schema_references(self, sql: str, target_schema: str) -> str:
        """
        Replace schema references in SQL query.
        
        Args:
            sql: Original SQL query
            target_schema: Target schema name
            
        Returns:
            SQL with schema references replaced
        """
        processed_sql = sql
        
        # Replace app. with target_schema.
        processed_sql = re.sub(r'\bapp\.', f'{target_schema}.', processed_sql)
        
        return processed_sql
    
    def clear_cache(self):
        """Clear the preprocessing cache."""
        self._replacement_cache.clear()


# Global instance for easy access
_sql_preprocessor = SQLPreprocessor()

def preprocess_sql(sql: str, entity_id: str, use_shadow: bool = False) -> str:
    """
    Convenience function to preprocess SQL query.
    
    Args:
        sql: Original SQL query
        entity_id: Entity identifier
        use_shadow: If True, use shadow schema
        
    Returns:
        Preprocessed SQL query
    """
    return _sql_preprocessor.preprocess_sql(sql, entity_id, use_shadow)

def get_local_search_path_sql(entity_id: str, use_shadow: bool = False) -> str:
    """
    Convenience function to get LOCAL search path SQL.
    
    Args:
        entity_id: Entity identifier
        use_shadow: If True, use shadow schema
        
    Returns:
        SQL command to set LOCAL search path
    """
    return _sql_preprocessor.get_local_search_path_sql(entity_id, use_shadow)

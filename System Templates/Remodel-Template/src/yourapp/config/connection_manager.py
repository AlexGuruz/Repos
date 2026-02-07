"""
Connection Manager Service

Handles database connections for both single-schema and multi-schema modes.
Provides unified interface for connection management across all services.
"""
from __future__ import annotations

from typing import Dict, Optional, Any
import json
import logging
import psycopg2
from contextlib import contextmanager

from yourapp.config.flags import (
    multi_schema_enabled, global_dsn, entity_schemas
)
from yourapp.config.schema_resolver import should_use_multi_schema, get_entity_schema
from yourapp.config.sql_preprocessor import get_local_search_path_sql


class ConnectionManager:
    """
    Manages database connections for multi-schema and single-schema modes.
    
    Features:
    - Unified connection interface
    - Automatic schema routing
    - Connection pooling support
    - Backward compatibility
    - Search path management
    """
    
    def __init__(self, dsn_map: Optional[Dict[str, str]] = None):
        self.logger = logging.getLogger(__name__)
        self.dsn_map = dsn_map or {}
        self._connection_cache: Dict[str, psycopg2.connection] = {}
        
    def get_connection(self, entity_id: Optional[str] = None, 
                      use_shadow: bool = False,
                      autocommit: bool = False) -> psycopg2.connection:
        """
        Get database connection for an entity.
        
        Args:
            entity_id: Entity identifier (None for global connection)
            use_shadow: If True, use shadow schema
            autocommit: If True, enable autocommit mode
            
        Returns:
            PostgreSQL connection object
        """
        if multi_schema_enabled() and (entity_id is None or should_use_multi_schema(entity_id)):
            return self._get_multi_schema_connection(entity_id, use_shadow, autocommit)
        else:
            return self._get_single_schema_connection(entity_id, autocommit)
    
    def _get_multi_schema_connection(self, entity_id: Optional[str], 
                                   use_shadow: bool, autocommit: bool) -> psycopg2.connection:
        """Get connection for multi-schema mode."""
        dsn = global_dsn()
        if not dsn:
            raise ValueError("APP_GLOBAL_DSN not configured for multi-schema mode")
        
        # Create connection
        conn = psycopg2.connect(dsn)
        conn.autocommit = autocommit
        
        # Set search path if entity_id is provided
        if entity_id:
            search_path_sql = get_local_search_path_sql(entity_id, use_shadow)
            with conn.cursor() as cur:
                cur.execute(search_path_sql)
        
        self.logger.debug(f"Created multi-schema connection for {entity_id} (shadow={use_shadow})")
        return conn
    
    def _get_single_schema_connection(self, entity_id: Optional[str], 
                                    autocommit: bool) -> psycopg2.connection:
        """Get connection for single-schema mode (backward compatibility)."""
        if entity_id and entity_id in self.dsn_map:
            dsn = self.dsn_map[entity_id]
        else:
            # Fallback to first available DSN or raise error
            if not self.dsn_map:
                raise ValueError("No DSN configured and no entity_id provided")
            dsn = next(iter(self.dsn_map.values()))
        
        conn = psycopg2.connect(dsn)
        conn.autocommit = autocommit
        
        self.logger.debug(f"Created single-schema connection for {entity_id}")
        return conn
    
    @contextmanager
    def get_connection_context(self, entity_id: Optional[str] = None,
                             use_shadow: bool = False,
                             autocommit: bool = False):
        """
        Context manager for database connections.
        
        Args:
            entity_id: Entity identifier
            use_shadow: If True, use shadow schema
            autocommit: If True, enable autocommit mode
            
        Yields:
            PostgreSQL connection object
        """
        conn = None
        try:
            conn = self.get_connection(entity_id, use_shadow, autocommit)
            yield conn
        except Exception as e:
            if conn and not autocommit:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def load_dsn_map_from_file(self, file_path: str):
        """
        Load DSN mapping from JSON file.
        
        Args:
            file_path: Path to JSON file containing DSN mapping
        """
        try:
            with open(file_path, 'r') as f:
                self.dsn_map = json.load(f)
            self.logger.info(f"Loaded DSN map from {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to load DSN map from {file_path}: {e}")
            raise


# Global instance for easy access
_connection_manager = ConnectionManager()

def get_connection(entity_id: Optional[str] = None, 
                  use_shadow: bool = False,
                  autocommit: bool = False) -> psycopg2.connection:
    """
    Convenience function to get database connection.
    
    Args:
        entity_id: Entity identifier
        use_shadow: If True, use shadow schema
        autocommit: If True, enable autocommit mode
        
    Returns:
        PostgreSQL connection object
    """
    return _connection_manager.get_connection(entity_id, use_shadow, autocommit)

@contextmanager
def get_connection_context(entity_id: Optional[str] = None,
                         use_shadow: bool = False,
                         autocommit: bool = False):
    """
    Convenience context manager for database connections.
    
    Args:
        entity_id: Entity identifier
        use_shadow: If True, use shadow schema
        autocommit: If True, enable autocommit mode
        
    Yields:
        PostgreSQL connection object
    """
    with _connection_manager.get_connection_context(entity_id, use_shadow, autocommit) as conn:
        yield conn

def load_dsn_map_from_file(file_path: str):
    """
    Convenience function to load DSN map from file.
    
    Args:
        file_path: Path to JSON file containing DSN mapping
    """
    _connection_manager.load_dsn_map_from_file(file_path)

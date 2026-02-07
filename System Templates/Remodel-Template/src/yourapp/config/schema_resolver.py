"""
Schema Resolver Service

Handles entity ID to schema name mapping for multi-schema mode.
Provides backward compatibility with single-schema mode.
"""
from __future__ import annotations

from typing import Dict, Optional, Set
import logging
import re

from yourapp.config.flags import (
    multi_schema_enabled, entity_schema_prefix, entity_schemas,
    shadow_mode_enabled, shadow_schema_suffix
)


class SchemaResolver:
    """
    Resolves entity IDs to schema names for multi-schema database architecture.
    
    Features:
    - Entity ID to schema name mapping
    - Shadow mode support for validation
    - Backward compatibility with single-schema mode
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._schema_cache: Dict[str, str] = {}
        self._shadow_schemas: Set[str] = set()
        
    def get_entity_schema(self, entity_id: str, use_shadow: bool = False) -> str:
        """
        Get schema name for an entity ID.
        
        Args:
            entity_id: Entity identifier (e.g., "entity1", "entity2")
            use_shadow: If True, return shadow schema name for validation
            
        Returns:
            Schema name (e.g., "app_entity1", "app_entity1_shadow")
        """
        if not multi_schema_enabled():
            # Backward compatibility: return default schema
            return "app"
        
        # Check cache first
        cache_key = f"{entity_id}:{use_shadow}"
        if cache_key in self._schema_cache:
            return self._schema_cache[cache_key]
        
        # Get base schema name
        schema_map = entity_schemas()
        base_schema = schema_map.get(entity_id)
        
        if not base_schema:
            # Fallback to prefix + normalized entity ID
            prefix = entity_schema_prefix()
            normalized_id = self._normalize_entity_id(entity_id)
            base_schema = f"{prefix}{normalized_id}"
        
        # Apply shadow suffix if requested
        if use_shadow and shadow_mode_enabled():
            suffix = shadow_schema_suffix()
            schema_name = f"{base_schema}{suffix}"
            self._shadow_schemas.add(schema_name)
        else:
            schema_name = base_schema
        
        # Cache the result
        self._schema_cache[cache_key] = schema_name
        
        self.logger.debug(f"Resolved {entity_id} -> {schema_name} (shadow={use_shadow})")
        return schema_name
    
    def _normalize_entity_id(self, entity_id: str) -> str:
        """
        Normalize entity ID for schema name generation.
        
        Args:
            entity_id: Raw entity identifier
            
        Returns:
            Normalized identifier suitable for schema names
        """
        # Convert to lowercase and replace spaces/special chars with underscores
        normalized = entity_id.lower()
        normalized = normalized.replace(" ", "_")
        normalized = normalized.replace("-", "_")
        normalized = normalized.replace(".", "_")
        
        # Remove any remaining special characters
        normalized = re.sub(r'[^a-z0-9_]', '', normalized)
        
        return normalized


# Global instance for easy access
_schema_resolver = SchemaResolver()

def get_entity_schema(entity_id: str, use_shadow: bool = False) -> str:
    """
    Convenience function to get entity schema name.
    
    Args:
        entity_id: Entity identifier
        use_shadow: If True, return shadow schema name
        
    Returns:
        Schema name
    """
    return _schema_resolver.get_entity_schema(entity_id, use_shadow)

def should_use_multi_schema(entity_id: str) -> bool:
    """
    Determine if an entity should use multi-schema mode.
    
    Args:
        entity_id: Entity identifier
        
    Returns:
        True if multi-schema mode should be used for this entity
    """
    if not multi_schema_enabled():
        return False
    return True

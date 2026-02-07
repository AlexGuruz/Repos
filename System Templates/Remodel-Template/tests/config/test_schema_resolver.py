"""
Tests for schema resolver functionality.
"""
import os
from yourapp.config.schema_resolver import SchemaResolver, get_entity_schema, should_use_multi_schema


def test_schema_resolver_single_schema():
    """Test schema resolver in single-schema mode."""
    # Disable multi-schema
    os.environ.pop("APP_MULTI_SCHEMA", None)
    
    resolver = SchemaResolver()
    schema = resolver.get_entity_schema("entity1")
    assert schema == "app"


def test_schema_resolver_multi_schema():
    """Test schema resolver in multi-schema mode."""
    # Enable multi-schema
    os.environ["APP_MULTI_SCHEMA"] = "true"
    os.environ["APP_ENTITY_SCHEMAS"] = "entity1:app_entity1,entity2:app_entity2"
    
    resolver = SchemaResolver()
    schema = resolver.get_entity_schema("entity1")
    assert schema == "app_entity1"
    
    schema2 = resolver.get_entity_schema("entity2")
    assert schema2 == "app_entity2"
    
    # Cleanup
    os.environ.pop("APP_MULTI_SCHEMA", None)
    os.environ.pop("APP_ENTITY_SCHEMAS", None)


def test_get_entity_schema_convenience():
    """Test convenience function for getting entity schema."""
    os.environ.pop("APP_MULTI_SCHEMA", None)
    
    schema = get_entity_schema("entity1")
    assert schema == "app"

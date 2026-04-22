#!/usr/bin/env python3
"""
Database initialization script.
Creates all tables including the new Profile Management tables.
"""
from sqlmodel import SQLModel
from database import engine
from models import (
    User, Profile, Job, ExecutionLog, Settlement,
    ProfileField, WorkflowStep, ProfileVersion,
    ColumnMapping, MappingSession
)

def init_db():
    """Initialize the database with all tables."""
    print("Creating all database tables...")
    SQLModel.metadata.create_all(engine)
    print("✓ Database tables created successfully")
    
    # List created tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\nCreated tables: {', '.join(sorted(tables))}")
    
    return tables

if __name__ == "__main__":
    tables = init_db()
    
    expected_tables = [
        "user", "profile", "job", "executionlog", "settlement",
        "profile_fields", "workflow_step", "profile_versions",
        "column_mappings", "mapping_session"
    ]
    
    print("\n" + "="*50)
    print("Database Initialization Complete")
    print("="*50)
    
    missing = [t for t in expected_tables if t not in tables]
    if missing:
        print(f"\n⚠ Warning: Missing tables: {missing}")
    else:
        print("\n✓ All expected tables present")

-- Initialize database tables and sample data
-- This will be executed when PostgreSQL container starts

-- Create database if it doesn't exist
-- (Handled by environment variables in docker-compose)

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sample data for testing (optional)
-- This will be populated by the application models

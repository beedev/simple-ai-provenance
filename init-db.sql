-- Initialize AI Commit database schema
-- This script runs when the PostgreSQL container starts for the first time

-- Create the ai_commit schema
CREATE SCHEMA IF NOT EXISTS ai_commit;

-- Set default search path
ALTER DATABASE ai_commit SET search_path TO ai_commit, public;

-- Grant permissions to the ai_commit_user
GRANT ALL PRIVILEGES ON SCHEMA ai_commit TO ai_commit_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ai_commit TO ai_commit_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA ai_commit TO ai_commit_user;

-- Grant future privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_commit GRANT ALL ON TABLES TO ai_commit_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA ai_commit GRANT ALL ON SEQUENCES TO ai_commit_user;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The actual tables will be created by SQLAlchemy on first run
-- This ensures the schema and permissions are set up correctly
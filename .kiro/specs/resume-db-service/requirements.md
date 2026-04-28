# Requirements Document

## Introduction

A lightweight database service for the `ai-job-agent` project that retrieves resume data stored as JSONB from a PostgreSQL `resumes` table. The service exposes a single function to look up a resume by its version name and return the content as a Python dict. No ORM, no async — just a clean, direct psycopg2 connection.

## Glossary

- **DB_Service**: The module `app/services/tracker/db_service.py` responsible for all database interactions related to resumes.
- **Resume**: A record in the `resumes` table with columns `id` (int), `version_name` (text), and `content` (JSONB).
- **version_name**: A human-readable string identifier for a resume version (e.g., `"base_v2"`).
- **content**: The JSONB column in the `resumes` table that stores the full resume as a JSON object.

## Requirements

### Requirement 1: Fetch Resume by Version Name

**User Story:** As a developer, I want to retrieve a resume's JSON content by its version name, so that I can use it in downstream processing such as job matching.

#### Acceptance Criteria

1. WHEN `get_resume_by_version` is called with a valid `version_name`, THE DB_Service SHALL query the `resumes` table and return the `content` column as a Python dict.
2. WHEN `get_resume_by_version` is called with a `version_name` that does not exist in the database, THE DB_Service SHALL return `None`.
3. THE DB_Service SHALL use a parameterised query (`SELECT content FROM resumes WHERE version_name = %s`) to prevent SQL injection.
4. WHEN a database connection error occurs, THE DB_Service SHALL print a descriptive error message and return `None`.
5. WHEN a query execution error occurs, THE DB_Service SHALL print a descriptive error message and return `None`.

### Requirement 2: Database Connection

**User Story:** As a developer, I want the service to manage its own PostgreSQL connection, so that callers do not need to handle connection setup.

#### Acceptance Criteria

1. THE DB_Service SHALL read connection parameters from environment variables (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`).
2. WHEN environment variables are missing, THE DB_Service SHALL fall back to sensible defaults (`localhost`, `5432`, `postgres`, `postgres`, `""`) and print a warning.
3. THE DB_Service SHALL open and close the database connection within a single function call, ensuring no connection is left open after `get_resume_by_version` returns.

### Requirement 3: Manual Test Entry Point

**User Story:** As a developer, I want a quick way to smoke-test the service from the command line, so that I can verify the database connection and query without writing a separate script.

#### Acceptance Criteria

1. WHEN the module is executed directly (`python db_service.py`), THE DB_Service SHALL call `get_resume_by_version("base_v2")` and print the result to stdout.
2. WHEN the result is `None`, THE DB_Service SHALL print a message indicating that the resume was not found.

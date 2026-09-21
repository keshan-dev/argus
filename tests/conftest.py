"""Pytest configuration and environment fixtures for ARGUS."""

import os

# Ensure dummy configuration secrets exist so app.config can load in test environments
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://argus:argus@localhost:5432/argus")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")
os.environ.setdefault("JIRA_BASE_URL", "https://example.atlassian.net")
os.environ.setdefault("JIRA_EMAIL", "test@example.com")
os.environ.setdefault("JIRA_API_TOKEN", "test-jira-token")
os.environ.setdefault("SCHEDULER_ENABLED", "false")

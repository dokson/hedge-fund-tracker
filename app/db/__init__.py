"""
Postgres persistence layer.

Distinct from the project-level `database/` directory, which holds public
versioned CSVs (hedge_funds, stocks, quarterly filings). This package is
the per-user, mutable, relational data: users, api_keys, starred_items, etc.
"""

# Changelog

Every notable change, newest first. Each pull request adds a line under
Unreleased. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Coding standards in CONTRIBUTING.md: branch naming, Conventional Commits, pull request
  expectations and peer review (docs/coding-standards)
- Pull request template and a CI workflow that lints and runs every offline test on pull
  requests to integration and main (docs/coding-standards)
- backend/ruff.toml and backend/testkit.py so lint and tests are the same for everyone
  (docs/coding-standards)

## [0.1.0] - 2026-09-07

### Added
- Governance assessment against the ASX Corporate Governance Council Principles
  (4th edition): harvest, extract, Gemini reading, deterministic scoring
- FastAPI service implementing api-contract v0.1 and the six-screen interface
- Offline fixture company and 31 offline tests

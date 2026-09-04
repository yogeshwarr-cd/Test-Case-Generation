# EXAMPLE - Modular Playwright Automation Project

Automated test project generated with standard Page Object Model (POM) architecture.

## Directory Structure
```
example/
├── modules/
│   └── {module_name}/
│       ├── pages/          # Page Object classes
│       └── tests/          # Pytest test suites
├── shared/
│   ├── assets/             # Test assets / uploads
│   ├── config/             # Environment and settings
│   ├── fixtures/           # Global conftest.py fixtures
│   ├── test_data/          # Test data loader and JSON data
│   └── utils/              # Helper utilities
├── screenshots/            # Failure and execution screenshots
├── traces/                 # Playwright debug traces
├── reports/                # Pytest execution reports
├── requirements.txt
├── .env.example
├── pytest.ini
└── pyproject.toml
```

## Setup & Running Tests
1. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

2. Run all tests:
```bash
pytest
```

3. Run specific module:
```bash
pytest modules/core/tests/
```

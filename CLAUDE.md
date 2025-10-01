# CLAUDE.md - AI Assistant Context

This file provides context and guidelines for AI assistants (like Claude) working on the settfex project.

## Project Overview

**settfex** is a Python library designed to fetch real-time and historical data from:
- **SET** (Stock Exchange of Thailand)
- **TFEX** (Thailand Futures Exchange)

The library is built for publication on PyPI and follows modern Python development practices.

## Project Structure

```
settfex/
├── settfex/                    # Main package
│   ├── __init__.py
│   ├── services/              # Business logic and API integrations
│   │   ├── __init__.py
│   │   ├── set/              # SET-specific services
│   │   │   ├── __init__.py
│   │   │   ├── client.py     # SET API client
│   │   │   ├── realtime.py   # Real-time data fetching
│   │   │   └── historical.py # Historical data fetching
│   │   └── tfex/             # TFEX-specific services
│   │       ├── __init__.py
│   │       ├── client.py     # TFEX API client
│   │       ├── realtime.py   # Real-time data fetching
│   │       └── historical.py # Historical data fetching
│   └── utils/                # Helper functions and utilities
│       ├── __init__.py
│       ├── logging.py        # Logging utilities
│       ├── validation.py     # Data validation
│       ├── formatting.py     # Data formatting
│       └── http.py           # HTTP utilities
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── conftest.py           # Pytest configuration
│   ├── services/
│   │   ├── set/
│   │   └── tfex/
│   └── utils/
├── docs/                      # Documentation
│   ├── index.md
│   ├── installation.md
│   ├── quickstart.md
│   ├── api-reference.md
│   └── contributing.md
├── examples/                  # Usage examples
│   ├── set_realtime_example.py
│   ├── set_historical_example.py
│   ├── tfex_realtime_example.py
│   └── tfex_historical_example.py
├── scripts/                   # Utility scripts
│   ├── build.py
│   ├── release.py
│   └── test.py
├── pyproject.toml            # Project configuration
├── README.md                 # Project overview
├── LICENSE                   # MIT License
├── .gitignore               # Git ignore rules
└── CLAUDE.md                # This file
```

## Architecture Principles

1. **Modular Design**: Clear separation between SET and TFEX services
2. **Service Layer**: All external API interactions are encapsulated in the `services/` directory
3. **Utilities**: Reusable helpers in `utils/` for cross-cutting concerns
4. **Type Safety**: Full type hints and Pydantic validation
5. **Modern Python**: Targeting Python 3.11+ with modern async patterns
6. **Testing**: Comprehensive test coverage using pytest
7. **Documentation**: Clear, maintained documentation for all public APIs

## Development Guidelines

### Code Style
- Follow PEP 8 with line length of 100 characters
- Use Ruff for linting
- Use mypy for type checking with strict mode
- All functions should have type hints

### Dependencies
- **httpx**: Modern async HTTP client
- **pydantic**: Runtime validation and settings management
- Minimize external dependencies to keep the library lightweight

### Testing
- Write tests for all new features
- Maintain high test coverage (aim for >80%)
- Use pytest fixtures in `conftest.py` for shared test setup
- Mock external API calls in tests

### Documentation
- Update relevant documentation when adding features
- Include docstrings for all public functions and classes
- Keep examples up-to-date

## Common Tasks

### Adding a New SET Service
1. Create new module in `settfex/services/set/`
2. Add corresponding tests in `tests/services/set/`
3. Update `settfex/services/set/__init__.py` to export the new service
4. Add example usage in `examples/`
5. Document in `docs/api-reference.md`

### Adding a New TFEX Service
1. Create new module in `settfex/services/tfex/`
2. Add corresponding tests in `tests/services/tfex/`
3. Update `settfex/services/tfex/__init__.py` to export the new service
4. Add example usage in `examples/`
5. Document in `docs/api-reference.md`

### Adding Utility Functions
1. Add to appropriate module in `settfex/utils/` or create new module
2. Add tests in `tests/utils/`
3. Ensure utilities are generic and reusable

## API Design Principles

1. **Consistency**: SET and TFEX services should follow similar patterns
2. **Simplicity**: Provide simple, intuitive APIs
3. **Async-first**: Prefer async/await patterns for I/O operations
4. **Error Handling**: Clear, informative error messages
5. **Validation**: Validate inputs using Pydantic models
6. **Documentation**: All public APIs should be well-documented

## Target Users

- Python developers building trading applications
- Financial analysts needing Thailand market data
- Quantitative researchers and data scientists
- Automated trading system developers

## Important Notes

- This library is not officially affiliated with SET or TFEX
- Always respect API rate limits and terms of service
- Handle sensitive data (API keys, credentials) securely
- Never commit credentials or API keys to version control

## Future Enhancements (Ideas)

- WebSocket support for real-time streaming
- Data caching mechanisms
- Rate limiting and retry logic
- CLI tool for quick data queries
- Integration with popular data analysis libraries (pandas, polars)
- Historical data export to various formats (CSV, Parquet, etc.)

## When Working on This Project

1. **Read First**: Always check existing code patterns before implementing new features
2. **Test**: Write tests before or alongside your code
3. **Document**: Update documentation when adding features
4. **Consistency**: Follow existing patterns and naming conventions
5. **Type Safety**: Always use type hints
6. **Ask Questions**: If unclear about architecture decisions, ask for clarification

## Contact & Resources

- GitHub Repository: [yourusername/settfex]
- Documentation: See `docs/` directory
- Issues: GitHub Issues
- License: MIT

---

*This file should be kept up-to-date as the project evolves.*

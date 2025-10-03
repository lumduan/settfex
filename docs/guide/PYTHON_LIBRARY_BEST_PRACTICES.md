# Python Library Best Practices

This document outlines the best practices followed in the `settfex` library and serves as a guide for maintaining high-quality Python library code.

## 📦 Package Structure

### ✅ Recommended Structure

```
settfex/                       # Root directory
├── settfex/                   # Main package (same name as project)
│   ├── __init__.py           # Package entry point with public API
│   ├── services/             # Business logic modules
│   │   ├── __init__.py
│   │   └── set/              # Sub-packages
│   │       ├── __init__.py
│   │       └── *.py
│   └── utils/                # Utility modules
│       ├── __init__.py
│       └── *.py
├── tests/                    # Test suite (mirrors package structure)
│   ├── __init__.py
│   ├── conftest.py
│   └── */
├── docs/                     # Documentation
├── scripts/                  # Development/utility scripts
├── pyproject.toml           # Project configuration (modern standard)
├── README.md                # User-facing documentation
├── LICENSE                  # License file
└── .gitignore              # Git ignore rules
```

### ❌ Files to Avoid

- **`main.py` in root** - Libraries are imported, not executed
- **`setup.py`** - Deprecated in favor of `pyproject.toml`
- **`requirements.txt`** - Use `pyproject.toml` dependencies instead
- **Empty placeholder files** - Remove or complete them

## 🎯 Package Entry Point (`__init__.py`)

### Best Practices

1. **Package Docstring**: Include comprehensive documentation
2. **Metadata**: Export `__version__`, `__author__`, `__license__`
3. **Public API**: Import and re-export commonly used classes/functions
4. **`__all__` Declaration**: Explicitly list public API
5. **Sorted Imports**: Keep imports alphabetically sorted

### Example Implementation

```python
"""settfex - Stock Exchange of Thailand Data Library.

Usage:
    >>> from settfex import Stock, get_stock_list
    >>> stock_list = await get_stock_list()
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__license__ = "MIT"

# Public API exports
from settfex.services.set import (
    Stock,
    get_stock_list,
)

__all__ = [
    "__version__",
    "Stock",
    "get_stock_list",
]
```

### Benefits

- ✅ Users import from package root: `from settfex import Stock`
- ✅ Clear API boundaries with `__all__`
- ✅ Version accessible: `settfex.__version__`
- ✅ Tab-completion works in IDEs
- ✅ Namespace pollution prevention

## 📄 Project Configuration (`pyproject.toml`)

### Modern Standard

Use `pyproject.toml` for all configuration (PEP 518/621):

```toml
[project]
name = "settfex"
version = "0.1.0"
description = "Your description"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[tool.mypy]
strict = true
```

### Benefits

- ✅ Single source of truth for configuration
- ✅ Modern Python packaging standard
- ✅ Tool configuration in one place
- ✅ No `setup.py` or `setup.cfg` needed

## 🧪 Testing Structure

### Best Practices

1. **Mirror Package Structure**: `tests/` mirrors `settfex/`
2. **Use pytest**: Modern testing framework
3. **`conftest.py`**: Shared fixtures
4. **Test Naming**: `test_*.py`, `test_*()` functions
5. **Coverage**: Aim for >80% coverage

### Example Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── services/
│   └── set/
│       └── test_client.py
└── utils/
    └── test_http.py
```

## 📚 Documentation

### Essential Files

1. **README.md**: User-facing overview and quick start
2. **LICENSE**: Clear license declaration (MIT, Apache, etc.)
3. **CHANGELOG.md**: Version history (optional)
4. **docs/**: Detailed documentation

### README.md Structure

```markdown
# Project Name

Brief description

## Features
## Installation
## Quick Start
## Documentation
## Contributing
## License
```

## 🔧 Development Tools

### Recommended Stack

- **uv**: Fast Python package manager
- **pytest**: Testing framework
- **ruff**: Fast linter and formatter
- **mypy**: Static type checker
- **pytest-cov**: Coverage reporting

### Configuration

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
```

## 📦 Publishing to PyPI

### Checklist

- [ ] Proper `pyproject.toml` configuration
- [ ] Version number in `__init__.py` and `pyproject.toml`
- [ ] Comprehensive README.md
- [ ] LICENSE file
- [ ] All tests passing
- [ ] Type hints on all public APIs
- [ ] Documentation complete

### Build and Publish

```bash
# Install build tools
uv pip install build twine

# Build distribution
python -m build

# Upload to PyPI
twine upload dist/*
```

## 🚀 API Design Principles

### For Python Libraries

1. **Async-First**: Use `async`/`await` for I/O operations
2. **Type Hints**: Complete type annotations on public APIs
3. **Pydantic Models**: Data validation and serialization
4. **Context Managers**: Resource management with `async with`
5. **Explicit Exports**: Use `__all__` in all modules
6. **Consistent Naming**: Follow PEP 8 conventions

### Example

```python
from typing import Optional
from pydantic import BaseModel

class StockData(BaseModel):
    """Stock data model with validation."""
    symbol: str
    price: float
    volume: Optional[int] = None

async def get_stock(symbol: str) -> StockData:
    """Fetch stock data.
    
    Args:
        symbol: Stock symbol to fetch
        
    Returns:
        StockData: Validated stock data
        
    Raises:
        ValueError: If symbol is invalid
    """
    ...
```

## 🎓 Key Takeaways

### ✅ Do This

- Use `pyproject.toml` for all configuration
- Export public API from `__init__.py`
- Include comprehensive type hints
- Write docstrings for all public APIs
- Mirror package structure in tests
- Use modern async patterns
- Follow PEP 8 naming conventions

### ❌ Avoid This

- `main.py` in library root
- `setup.py` (deprecated)
- Missing `__all__` declarations
- Bare `except:` clauses
- Blocking I/O in async code
- Missing type hints
- Empty placeholder files

## 📖 Further Reading

- [Python Packaging User Guide](https://packaging.python.org/)
- [PEP 517: Build System Independence](https://peps.python.org/pep-0517/)
- [PEP 621: Project Metadata](https://peps.python.org/pep-0621/)
- [Python Library Patterns](https://docs.python-guide.org/writing/structure/)

---

*This document reflects the standards implemented in `settfex` as of October 2025.*

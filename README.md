# settfex

> Fetch real-time and historical data from the Stock Exchange of Thailand (SET) and Thailand Futures Exchange (TFEX)

[![PyPI version](https://badge.fury.io/py/settfex.svg)](https://badge.fury.io/py/settfex)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **SET Data**: Access real-time and historical stock data from the Stock Exchange of Thailand
- **TFEX Data**: Fetch futures and derivatives data from the Thailand Futures Exchange
- **Modern Python**: Built with Python 3.11+ using modern async patterns
- **Type Safe**: Full type hints and runtime validation with Pydantic
- **Easy to Use**: Simple, intuitive API for fetching market data

## Installation

```bash
pip install settfex
```

## Quick Start

```python
from settfex.services.set import SETClient
from settfex.services.tfex import TFEXClient

# Fetch SET real-time data
set_client = SETClient()
# Your code here

# Fetch TFEX real-time data
tfex_client = TFEXClient()
# Your code here
```

## Documentation

For detailed documentation, please see:
- [Installation Guide](docs/installation.md)
- [Quick Start Guide](docs/quickstart.md)
- [API Reference](docs/api-reference.md)
- [Contributing Guide](docs/contributing.md)

## Examples

Check out the [examples](examples/) directory for more detailed usage examples:
- [SET Real-time Data](examples/set_realtime_example.py)
- [SET Historical Data](examples/set_historical_example.py)
- [TFEX Real-time Data](examples/tfex_realtime_example.py)
- [TFEX Historical Data](examples/tfex_historical_example.py)

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/settfex.git
cd settfex

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Run linting
ruff check .

# Run type checking
mypy settfex
```

## Contributing

Contributions are welcome! Please see our [Contributing Guide](docs/contributing.md) for details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This library is not officially affiliated with the Stock Exchange of Thailand or Thailand Futures Exchange. Use at your own risk.

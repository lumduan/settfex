"""Tests for Financial Service."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from settfex.services.set.stock.financial import (
    Account,
    BalanceSheet,
    CashFlow,
    FinancialService,
    IncomeStatement,
    get_balance_sheet,
    get_cash_flow,
    get_income_statement,
)
from settfex.utils.data_fetcher import FetchResponse, FetcherConfig


@pytest.fixture
def mock_balance_sheet_response():
    """Mock balance sheet API response."""
    return [
        {
            "symbol": "CPALL",
            "quarter": "6M",
            "year": 2025,
            "beginDate": "2025-01-01T00:00:00+07:00",
            "endDate": "2025-06-30T00:00:00+07:00",
            "fsType": "C",
            "accountFormId": "6",
            "downloadUrl": "https://weblink.set.or.th/dat/news/202508/0737FIN130820251356300593E.zip",
            "fsTypeDescription": "Consolidate",
            "status": "Reviewed",
            "isFSComp": False,
            "hasAdjustedAccount": False,
            "accounts": [
                {
                    "accountCode": "601",
                    "accountName": "Cash And Cash Equivalents",
                    "amount": 3.7680002E7,
                    "adjusted": False,
                    "level": 0,
                    "divider": 1000,
                    "format": ""
                },
                {
                    "accountCode": "607",
                    "accountName": "Total Assets",
                    "amount": 9.31772208E8,
                    "adjusted": False,
                    "level": -1,
                    "divider": 1000,
                    "format": "BU"
                }
            ],
            "isRestatement": False,
            "restatementDate": None
        }
    ]


@pytest.fixture
def mock_income_statement_response():
    """Mock income statement API response."""
    return [
        {
            "symbol": "CPALL",
            "quarter": "6M",
            "year": 2025,
            "beginDate": "2025-01-01T00:00:00+07:00",
            "endDate": "2025-06-30T00:00:00+07:00",
            "fsType": "C",
            "accountFormId": "6",
            "downloadUrl": "https://weblink.set.or.th/dat/news/202508/0737FIN130820251356300593E.zip",
            "fsTypeDescription": "Consolidate",
            "status": "Reviewed",
            "isFSComp": False,
            "hasAdjustedAccount": False,
            "accounts": [
                {
                    "accountCode": "624",
                    "accountName": "Revenue From Operations",
                    "amount": 4.94663255E8,
                    "adjusted": False,
                    "level": 0,
                    "divider": 1000,
                    "format": ""
                },
                {
                    "accountCode": "633",
                    "accountName": "Net Profit  : Owners Of The Parent",
                    "amount": 1.4353693E7,
                    "adjusted": False,
                    "level": -1,
                    "divider": 1000,
                    "format": "BU"
                }
            ],
            "isRestatement": False,
            "restatementDate": None
        }
    ]


@pytest.fixture
def mock_cash_flow_response():
    """Mock cash flow API response."""
    return [
        {
            "symbol": "CPALL",
            "quarter": "6M",
            "year": 2025,
            "beginDate": "2025-01-01T00:00:00+07:00",
            "endDate": "2025-06-30T00:00:00+07:00",
            "fsType": "C",
            "accountFormId": "6",
            "downloadUrl": "https://weblink.set.or.th/dat/news/202508/0737FIN130820251356300593E.zip",
            "fsTypeDescription": "Consolidate",
            "status": "Reviewed",
            "isFSComp": False,
            "hasAdjustedAccount": False,
            "accounts": [
                {
                    "accountCode": "701",
                    "accountName": "Cash From Operating Activities",
                    "amount": 5000000,
                    "adjusted": False,
                    "level": 0,
                    "divider": 1000,
                    "format": ""
                }
            ],
            "isRestatement": False,
            "restatementDate": None
        }
    ]


class TestAccount:
    """Tests for Account model."""

    def test_account_model_creation(self):
        """Test Account model can be created with valid data."""
        account = Account(
            accountCode="601",
            accountName="Cash And Cash Equivalents",
            amount=37680002.0,
            adjusted=False,
            level=0,
            divider=1000,
            format=""
        )
        assert account.account_code == "601"
        assert account.account_name == "Cash And Cash Equivalents"
        assert account.amount == 37680002.0
        assert account.adjusted is False
        assert account.level == 0
        assert account.divider == 1000
        assert account.format == ""

    def test_account_model_with_alias(self):
        """Test Account model accepts API field aliases."""
        data = {
            "accountCode": "607",
            "accountName": "Total Assets",
            "amount": 931772208.0,
            "adjusted": False,
            "level": -1,
            "divider": 1000,
            "format": "BU"
        }
        account = Account(**data)
        assert account.account_code == "607"
        assert account.account_name == "Total Assets"
        assert account.level == -1
        assert account.format == "BU"

    def test_account_model_null_amount(self):
        """Test Account model handles null amounts."""
        account = Account(
            accountCode="618",
            accountName="Treasury Stock",
            amount=None,
            adjusted=False,
            level=0,
            divider=1000,
            format=""
        )
        assert account.amount is None


class TestFinancialStatement:
    """Tests for FinancialStatement models."""

    def test_balance_sheet_model(self, mock_balance_sheet_response):
        """Test BalanceSheet model can be created from API response."""
        data = mock_balance_sheet_response[0]
        balance_sheet = BalanceSheet(**data)

        assert balance_sheet.symbol == "CPALL"
        assert balance_sheet.quarter == "6M"
        assert balance_sheet.year == 2025
        assert isinstance(balance_sheet.begin_date, datetime)
        assert isinstance(balance_sheet.end_date, datetime)
        assert balance_sheet.fs_type == "C"
        assert balance_sheet.status == "Reviewed"
        assert len(balance_sheet.accounts) == 2
        assert balance_sheet.is_restatement is False
        assert balance_sheet.restatement_date is None

    def test_income_statement_model(self, mock_income_statement_response):
        """Test IncomeStatement model can be created from API response."""
        data = mock_income_statement_response[0]
        income_statement = IncomeStatement(**data)

        assert income_statement.symbol == "CPALL"
        assert income_statement.quarter == "6M"
        assert income_statement.year == 2025
        assert income_statement.status == "Reviewed"
        assert len(income_statement.accounts) == 2

    def test_cash_flow_model(self, mock_cash_flow_response):
        """Test CashFlow model can be created from API response."""
        data = mock_cash_flow_response[0]
        cash_flow = CashFlow(**data)

        assert cash_flow.symbol == "CPALL"
        assert cash_flow.quarter == "6M"
        assert cash_flow.year == 2025
        assert len(cash_flow.accounts) == 1

    def test_financial_statement_quarter_codes(self):
        """Test financial statement handles different quarter codes."""
        # Test half year
        data = {
            "symbol": "TEST",
            "quarter": "6M",
            "year": 2025,
            "beginDate": "2025-01-01T00:00:00+07:00",
            "endDate": "2025-06-30T00:00:00+07:00",
            "fsType": "C",
            "accountFormId": "6",
            "downloadUrl": "http://example.com",
            "fsTypeDescription": "Consolidate",
            "status": "Reviewed",
            "isFSComp": False,
            "hasAdjustedAccount": False,
            "accounts": [],
            "isRestatement": False,
            "restatementDate": None
        }
        stmt = BalanceSheet(**data)
        assert stmt.quarter == "6M"

        # Test full year
        data["quarter"] = "Q9"
        stmt = BalanceSheet(**data)
        assert stmt.quarter == "Q9"


class TestFinancialService:
    """Tests for FinancialService class."""

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test service initializes with default config."""
        service = FinancialService()
        assert service.base_url == "https://www.set.or.th"
        assert service.config is not None

    @pytest.mark.asyncio
    async def test_service_initialization_with_custom_config(self):
        """Test service initializes with custom config."""
        config = FetcherConfig(timeout=60, max_retries=5)
        service = FinancialService(config=config)
        assert service.config.timeout == 60
        assert service.config.max_retries == 5

    @pytest.mark.asyncio
    async def test_fetch_balance_sheet_success(self, mock_balance_sheet_response):
        """Test fetching balance sheet successfully."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock response
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps(mock_balance_sheet_response).encode(),
                text=json.dumps(mock_balance_sheet_response),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.5
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            service = FinancialService()
            result = await service.fetch_balance_sheet(symbol="CPALL", lang="en")

            # Assert
            assert len(result) == 1
            assert isinstance(result[0], BalanceSheet)
            assert result[0].symbol == "CPALL"
            assert result[0].quarter == "6M"
            assert len(result[0].accounts) == 2

    @pytest.mark.asyncio
    async def test_fetch_income_statement_success(self, mock_income_statement_response):
        """Test fetching income statement successfully."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock response
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps(mock_income_statement_response).encode(),
                text=json.dumps(mock_income_statement_response),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.5
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            service = FinancialService()
            result = await service.fetch_income_statement(symbol="CPALL", lang="en")

            # Assert
            assert len(result) == 1
            assert isinstance(result[0], IncomeStatement)
            assert result[0].symbol == "CPALL"

    @pytest.mark.asyncio
    async def test_fetch_cash_flow_success(self, mock_cash_flow_response):
        """Test fetching cash flow successfully."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock response
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps(mock_cash_flow_response).encode(),
                text=json.dumps(mock_cash_flow_response),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.5
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            service = FinancialService()
            result = await service.fetch_cash_flow(symbol="CPALL", lang="en")

            # Assert
            assert len(result) == 1
            assert isinstance(result[0], CashFlow)
            assert result[0].symbol == "CPALL"

    @pytest.mark.asyncio
    async def test_fetch_with_thai_language(self, mock_balance_sheet_response):
        """Test fetching with Thai language."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock response
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps(mock_balance_sheet_response).encode(),
                text=json.dumps(mock_balance_sheet_response),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.5
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            service = FinancialService()
            result = await service.fetch_balance_sheet(symbol="CPALL", lang="th")

            # Assert - URL should contain lang=th
            call_args = mock_instance.fetch.call_args
            assert "lang=th" in call_args.kwargs["url"]

    @pytest.mark.asyncio
    async def test_fetch_balance_sheet_raw(self, mock_balance_sheet_response):
        """Test fetching raw balance sheet data."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock response
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps(mock_balance_sheet_response).encode(),
                text=json.dumps(mock_balance_sheet_response),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.5
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            service = FinancialService()
            result = await service.fetch_balance_sheet_raw(symbol="CPALL", lang="en")

            # Assert
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["symbol"] == "CPALL"
            assert result[0]["quarter"] == "6M"

    @pytest.mark.asyncio
    async def test_symbol_normalization(self, mock_balance_sheet_response):
        """Test symbol is normalized to uppercase."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock response
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps(mock_balance_sheet_response).encode(),
                text=json.dumps(mock_balance_sheet_response),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.5
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute with lowercase symbol
            service = FinancialService()
            await service.fetch_balance_sheet(symbol="cpall", lang="en")

            # Assert - URL should contain uppercase symbol
            call_args = mock_instance.fetch.call_args
            assert "CPALL" in call_args.kwargs["url"]

    @pytest.mark.asyncio
    async def test_empty_symbol_raises_error(self):
        """Test empty symbol raises ValueError."""
        service = FinancialService()

        with pytest.raises(ValueError, match="Stock symbol cannot be empty"):
            await service.fetch_balance_sheet(symbol="", lang="en")

    @pytest.mark.asyncio
    async def test_http_error_handling(self):
        """Test handling of HTTP errors."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock 404 response
            mock_response = FetchResponse(
                status_code=404,
                content=b"Not Found",
                text="Not Found",
                headers={},
                url="https://www.set.or.th/api/set/factsheet/INVALID/financialstatement",
                elapsed=0.1
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            service = FinancialService()

            with pytest.raises(Exception, match="Failed to fetch balance_sheet"):
                await service.fetch_balance_sheet(symbol="INVALID", lang="en")

    @pytest.mark.asyncio
    async def test_json_parse_error_handling(self):
        """Test handling of JSON parse errors."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock invalid JSON response
            mock_response = FetchResponse(
                status_code=200,
                content=b"Invalid JSON",
                text="Invalid JSON",
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.1
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            service = FinancialService()

            with pytest.raises(Exception):  # JSONDecodeError
                await service.fetch_balance_sheet(symbol="CPALL", lang="en")

    @pytest.mark.asyncio
    async def test_invalid_response_type(self):
        """Test handling of non-list response."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock dict response instead of list
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps({"error": "Invalid"}).encode(),
                text=json.dumps({"error": "Invalid"}),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.1
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            service = FinancialService()

            with pytest.raises(ValueError, match="Expected list response"):
                await service.fetch_balance_sheet(symbol="CPALL", lang="en")


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_get_balance_sheet(self, mock_balance_sheet_response):
        """Test get_balance_sheet convenience function."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock response
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps(mock_balance_sheet_response).encode(),
                text=json.dumps(mock_balance_sheet_response),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.5
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            result = await get_balance_sheet(symbol="CPALL", lang="en")

            # Assert
            assert len(result) == 1
            assert isinstance(result[0], BalanceSheet)
            assert result[0].symbol == "CPALL"

    @pytest.mark.asyncio
    async def test_get_income_statement(self, mock_income_statement_response):
        """Test get_income_statement convenience function."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock response
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps(mock_income_statement_response).encode(),
                text=json.dumps(mock_income_statement_response),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.5
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            result = await get_income_statement(symbol="CPALL", lang="en")

            # Assert
            assert len(result) == 1
            assert isinstance(result[0], IncomeStatement)

    @pytest.mark.asyncio
    async def test_get_cash_flow(self, mock_cash_flow_response):
        """Test get_cash_flow convenience function."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock response
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps(mock_cash_flow_response).encode(),
                text=json.dumps(mock_cash_flow_response),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.5
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute
            result = await get_cash_flow(symbol="CPALL", lang="en")

            # Assert
            assert len(result) == 1
            assert isinstance(result[0], CashFlow)

    @pytest.mark.asyncio
    async def test_convenience_functions_with_custom_config(self, mock_balance_sheet_response):
        """Test convenience functions with custom config."""
        with patch("settfex.services.set.stock.financial.financial.AsyncDataFetcher") as mock_fetcher:
            # Setup mock
            mock_instance = AsyncMock()
            mock_fetcher.return_value.__aenter__.return_value = mock_instance
            mock_fetcher.get_set_api_headers.return_value = {}

            # Mock response
            mock_response = FetchResponse(
                status_code=200,
                content=json.dumps(mock_balance_sheet_response).encode(),
                text=json.dumps(mock_balance_sheet_response),
                headers={},
                url="https://www.set.or.th/api/set/factsheet/CPALL/financialstatement",
                elapsed=0.5
            )
            mock_instance.fetch = AsyncMock(return_value=mock_response)

            # Execute with custom config
            config = FetcherConfig(timeout=60)
            result = await get_balance_sheet(symbol="CPALL", lang="en", config=config)

            # Assert
            assert len(result) == 1

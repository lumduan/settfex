"""Tests for SET company profile service."""

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.stock.profile_company import (
    Auditor,
    CompanyProfile,
    CompanyProfileService,
    Management,
    get_company_profile,
)
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse
from settfex.utils.parsing import ResponseParseError

# Sample test data based on the actual API response for VIBE (mai-listed), captured 2026-07-18.
# Kept deliberately close to the real payload: it exercises the null-heavy corners of this
# endpoint — a vacant management seat (`startDate: null`, empty name), plus null cgScore,
# treasuryShares, and preferred capital/share.
MOCK_COMPANY_PROFILE_DATA: dict[str, Any] = {
    "symbol": "VIBE",
    "name": "VIBE SYNERGY GROUP PUBLIC COMPANY LIMITED",
    "nameRemark": "",
    "market": "mai",
    "industry": "SERVICE",
    "industryName": "Services",
    "sector": "",
    "sectorName": "",
    "logoUrl": "https://media.set.or.th/common/logo/company/VIBE.png",
    "businessType": "Retail Business",
    "url": "https://www.vibesynergygroup.com",
    "address": "24, Soi Ramkhamhaeng 22 (Chittranukhro), Ramkhamhaeng Road, Bangkok 10240",
    "telephone": "0-2514-5000",
    "fax": "",
    "email": "",
    "dividendPolicy": "The Company has a policy to pay dividends to the shareholders "
    "when the Company does not have accumulated losses.",
    "cgScore": None,
    "cgRemark": "",
    "cacFlag": False,
    "setesgRating": "",
    "setesgRatingRemark": "",
    "establishedDate": "03/01/1990",
    "auditEnd": "2026-12-31T00:00:00+07:00",
    "auditChoice": "Unqualified opinion with an emphasis of matters",
    "auditors": [
        {
            "name": "MISS KANNIKA WIPANURAT",
            "company": "KARIN AUDIT COMPANY LIMITED",
            "auditEndDate": "2026-12-31T00:00:00+07:00",
        },
        {
            "name": "MR. JADESADA HUNGSAPRUEK",
            "company": "KARIN AUDIT COMPANY LIMITED",
            "auditEndDate": "2026-12-31T00:00:00+07:00",
        },
    ],
    "managements": [
        {
            # Vacant seat: SET reports the position with no holder and no start date.
            "positionCode": 1,
            "position": "The person taking the highest responsibility in finance and accounting",
            "name": "",
            "startDate": None,
        },
        {
            "positionCode": 2,
            "position": "The person supervising accounting",
            "name": "Miss Kan-Itsariya Charoenpakdee",
            "startDate": "2024-09-01T00:00:00+07:00",
        },
    ],
    "commonCapital": {
        "authorizedCapital": 737435718.0,
        "paidupCapital": 547680522.0,
        "par": 1.0,
        "currency": "Baht",
    },
    "commonsShare": {
        "listedShare": 547680522,
        "votingRights": [
            {"symbol": "VIBE", "paidupShare": 547680522, "ratio": "1 : 1"},
        ],
        "treasuryShares": None,
        "votingShares": [
            {"asOfDate": "2026-07-20T00:00:00+07:00", "share": 547680522},
            {"asOfDate": "2026-06-30T00:00:00+07:00", "share": 547680522},
        ],
    },
    "preferredCapital": None,
    "preferredShare": None,
}


def make_response(text: str, status_code: int = 200) -> FetchResponse:
    """Build a FetchResponse around the given body."""
    return FetchResponse(
        status_code=status_code,
        content=text.encode("utf-8"),
        text=text,
        headers={},
        url="https://www.set.or.th/api/set/company/VIBE/profile?lang=en",
        elapsed=0.5,
    )


@pytest.fixture
def mock_fetcher():
    """Create a mock AsyncDataFetcher."""
    with patch("settfex.services.set.stock.profile_company.AsyncDataFetcher") as mock:
        # Create async context manager mock
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None

        # Mock the get_set_api_headers static method
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})

        yield fetcher_instance


@pytest.mark.asyncio
class TestCompanyProfileService:
    """Tests for CompanyProfileService class."""

    async def test_init_default_config(self):
        """Test service initialization with default config."""
        service = CompanyProfileService()
        assert service.config is not None
        assert service.base_url == "https://www.set.or.th"

    async def test_init_custom_config(self):
        """Test service initialization with custom config."""
        config = FetcherConfig(timeout=60, max_retries=5)
        service = CompanyProfileService(config=config)
        assert service.config.timeout == 60
        assert service.config.max_retries == 5

    async def test_fetch_company_profile_success(self, mock_fetcher):
        """Test successful fetch of company profile data."""
        mock_fetcher.fetch.return_value = make_response(json.dumps(MOCK_COMPANY_PROFILE_DATA))

        service = CompanyProfileService()
        result = await service.fetch_company_profile("VIBE", lang="en")

        assert isinstance(result, CompanyProfile)
        assert result.symbol == "VIBE"
        assert result.name == "VIBE SYNERGY GROUP PUBLIC COMPANY LIMITED"
        assert result.market == "mai"
        assert result.business_type == "Retail Business"
        assert result.cg_score is None
        assert isinstance(result.audit_end, datetime)
        assert len(result.auditors) == 2
        assert isinstance(result.auditors[0], Auditor)
        assert len(result.managements) == 2
        assert result.common_capital.paidup_capital == 547680522.0
        assert result.commons_share.listed_share == 547680522
        assert result.commons_share.treasury_shares is None
        assert result.preferred_capital is None
        assert result.preferred_share is None

    async def test_fetch_tolerates_null_management_start_date(self, mock_fetcher):
        """Regression: a vacant management seat has `startDate: null` and must not raise.

        The real VIBE payload includes an executive position with no holder
        (`name: ""`, `startDate: null`). Prior to 0.10.1 every settfex release
        (0.1.0-0.10.0) raised a pydantic ValidationError on such symbols because
        `Management.start_date` was a required, non-nullable datetime.
        """
        mock_fetcher.fetch.return_value = make_response(json.dumps(MOCK_COMPANY_PROFILE_DATA))

        service = CompanyProfileService()
        result = await service.fetch_company_profile("VIBE", lang="en")

        vacant, held = result.managements
        assert vacant.position_code == 1
        assert vacant.name == ""
        assert vacant.start_date is None

        assert held.start_date is not None
        assert held.start_date.year == 2024
        assert held.start_date.month == 9

    async def test_fetch_company_profile_symbol_normalization(self, mock_fetcher):
        """Test symbol normalization (lowercase to uppercase)."""
        mock_fetcher.fetch.return_value = make_response(json.dumps(MOCK_COMPANY_PROFILE_DATA))

        service = CompanyProfileService()
        result = await service.fetch_company_profile("vibe", lang="en")

        assert result.symbol == "VIBE"

    async def test_fetch_company_profile_empty_symbol(self):
        """Test fetch with empty symbol raises ValueError."""
        service = CompanyProfileService()

        with pytest.raises(ValueError, match="Stock symbol cannot be empty"):
            await service.fetch_company_profile("", lang="en")

    async def test_fetch_company_profile_invalid_language(self):
        """Test fetch with invalid language raises ValueError."""
        service = CompanyProfileService()

        with pytest.raises(ValueError, match="Invalid language"):
            await service.fetch_company_profile("VIBE", lang="invalid")  # type: ignore[arg-type]  # intentional: runtime-permissive language

    async def test_fetch_company_profile_http_error(self, mock_fetcher):
        """Test handling of HTTP error response."""
        mock_fetcher.fetch.return_value = make_response("Not Found", status_code=404)

        service = CompanyProfileService()

        with pytest.raises(Exception, match="Failed to fetch company profile"):
            await service.fetch_company_profile("INVALID", lang="en")

    async def test_fetch_company_profile_json_decode_error(self, mock_fetcher):
        """Test handling of invalid JSON response."""
        mock_fetcher.fetch.return_value = make_response("Invalid JSON")

        service = CompanyProfileService()

        with pytest.raises(ResponseParseError, match="VIBE"):
            await service.fetch_company_profile("VIBE", lang="en")

    async def test_fetch_company_profile_raw_success(self, mock_fetcher):
        """Test successful fetch of raw company profile data."""
        mock_fetcher.fetch_json.return_value = MOCK_COMPANY_PROFILE_DATA

        service = CompanyProfileService()
        result = await service.fetch_company_profile_raw("VIBE", lang="en")

        assert isinstance(result, dict)
        assert result["symbol"] == "VIBE"
        assert result["managements"][0]["startDate"] is None


@pytest.mark.asyncio
class TestCompanyProfileModels:
    """Tests for Company Profile Pydantic models."""

    def test_management_null_start_date(self):
        """Regression: Management must accept `startDate: null` (vacant/undisclosed seat)."""
        management = Management.model_validate(MOCK_COMPANY_PROFILE_DATA["managements"][0])

        assert management.position_code == 1
        assert management.name == ""
        assert management.start_date is None

    def test_management_with_start_date(self):
        """A populated startDate still parses to a datetime."""
        management = Management.model_validate(MOCK_COMPANY_PROFILE_DATA["managements"][1])

        assert isinstance(management.start_date, datetime)
        assert management.start_date.year == 2024

    def test_management_field_name_support(self):
        """Test that Management supports snake_case field names (populate_by_name)."""
        management = Management(
            position_code=1,
            position="Chief Executive Officer",
            name="Test Person",
            start_date=None,
        )
        assert management.start_date is None

    def test_create_company_profile(self):
        """Test creating a CompanyProfile model from the full payload."""
        profile = CompanyProfile.model_validate(MOCK_COMPANY_PROFILE_DATA)

        assert profile.symbol == "VIBE"
        assert profile.market == "mai"
        assert isinstance(profile.managements[0], Management)
        assert profile.managements[0].start_date is None
        assert isinstance(profile.auditors[0].audit_end_date, datetime)
        assert profile.common_capital.currency == "Baht"


@pytest.mark.asyncio
class TestConvenienceFunction:
    """Tests for get_company_profile convenience function."""

    async def test_get_company_profile_success(self, mock_fetcher):
        """Test convenience function with successful fetch."""
        mock_fetcher.fetch.return_value = make_response(json.dumps(MOCK_COMPANY_PROFILE_DATA))

        result = await get_company_profile("VIBE", lang="en")

        assert isinstance(result, CompanyProfile)
        assert result.symbol == "VIBE"
        assert result.managements[0].start_date is None

    async def test_get_company_profile_custom_config(self, mock_fetcher):
        """Test convenience function with custom config."""
        mock_fetcher.fetch.return_value = make_response(json.dumps(MOCK_COMPANY_PROFILE_DATA))

        config = FetcherConfig(timeout=60, max_retries=5)
        result = await get_company_profile("VIBE", lang="en", config=config)

        assert result.symbol == "VIBE"

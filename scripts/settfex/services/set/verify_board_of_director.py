#!/usr/bin/env python3
"""
Manual verification script for Board of Director Service.

This script tests the board of director service by fetching data for
multiple stock symbols and displaying the results.

Usage:
    python scripts/settfex/services/set/verify_board_of_director.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from settfex.services.set import get_board_of_directors
from settfex.services.set.stock import BoardOfDirectorService
from settfex.utils.logging import setup_logger


async def test_convenience_function():
    """Test the convenience function get_board_of_directors()."""
    print("\n" + "=" * 80)
    print("TEST 1: Convenience Function - get_board_of_directors()")
    print("=" * 80)

    try:
        # Fetch data for MINT
        directors = await get_board_of_directors("MINT")

        print(f"\n✓ Successfully fetched {len(directors)} directors for MINT")

        # Display all directors
        print(f"\n  Board of Directors:")
        for i, director in enumerate(directors, 1):
            positions = ", ".join(director.positions)
            print(f"\n    {i}. {director.name}")
            print(f"       Position(s): {positions}")

        # Analyze board structure
        chairman = next(
            (d for d in directors if "CHAIRMAN" in d.positions), None
        )
        if chairman:
            print(f"\n  Chairman: {chairman.name}")

        # Find CEO/Chief Executive
        ceo = next(
            (
                d
                for d in directors
                if any("CEO" in pos or "CHIEF EXECUTIVE" in pos for pos in d.positions)
            ),
            None,
        )
        if ceo:
            print(f"  CEO: {ceo.name}")

        # Find independent directors
        independent_directors = [
            d for d in directors if any("INDEPENDENT" in pos for pos in d.positions)
        ]
        if independent_directors:
            print(f"  Independent Directors: {len(independent_directors)}")

        # Directors with multiple positions
        multi_position_directors = [d for d in directors if len(d.positions) > 1]
        if multi_position_directors:
            print(f"  Directors with multiple positions: {len(multi_position_directors)}")

        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        logger.exception("Failed to fetch data using convenience function")
        return False


async def test_service_class():
    """Test the BoardOfDirectorService class."""
    print("\n" + "=" * 80)
    print("TEST 2: Service Class - BoardOfDirectorService().fetch_board_of_directors()")
    print("=" * 80)

    try:
        service = BoardOfDirectorService()

        # Fetch data for PTT
        directors = await service.fetch_board_of_directors("PTT", lang="en")

        print(f"\n✓ Successfully fetched {len(directors)} directors for PTT")

        # Display top 5 directors
        print(f"\n  Top 5 Directors:")
        for i, director in enumerate(directors[:5], 1):
            positions = ", ".join(director.positions)
            print(f"    {i}. {director.name}")
            print(f"       {positions}")

        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        logger.exception("Failed to fetch data using service class")
        return False


async def test_thai_language():
    """Test fetching data in Thai language."""
    print("\n" + "=" * 80)
    print("TEST 3: Thai Language Support - get_board_of_directors(lang='th')")
    print("=" * 80)

    try:
        # Fetch data in Thai
        directors = await get_board_of_directors("CPALL", lang="th")

        print(f"\n✓ Successfully fetched Thai language data ({len(directors)} directors)")
        print(f"\n  กรรมการบริษัท (Top 5):")
        for i, director in enumerate(directors[:5], 1):
            positions = ", ".join(director.positions)
            print(f"    {i}. {director.name}")
            print(f"       ตำแหน่ง: {positions}")

        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        logger.exception("Failed to fetch Thai language data")
        return False


async def test_symbol_normalization():
    """Test symbol normalization (lowercase to uppercase)."""
    print("\n" + "=" * 80)
    print("TEST 4: Symbol Normalization - get_board_of_directors('cpall')")
    print("=" * 80)

    try:
        # Fetch with lowercase symbol
        directors = await get_board_of_directors("cpall")

        print(f"\n✓ Symbol normalized from 'cpall' to 'CPALL'")
        print(f"  Found {len(directors)} directors")

        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        logger.exception("Failed symbol normalization test")
        return False


async def test_raw_data_fetch():
    """Test fetching raw list data."""
    print("\n" + "=" * 80)
    print("TEST 5: Raw Data - BoardOfDirectorService().fetch_board_of_directors_raw()")
    print("=" * 80)

    try:
        service = BoardOfDirectorService()
        raw_data = await service.fetch_board_of_directors_raw("MINT")

        print(f"\n✓ Successfully fetched raw data")
        print(f"\n  Data type: {type(raw_data).__name__}")
        print(f"  Number of directors: {len(raw_data)}")
        print(f"\n  First director data:")
        print(f"    Keys: {list(raw_data[0].keys())}")
        print(f"    Name: {raw_data[0]['name']}")
        print(f"    Positions: {raw_data[0]['positions']}")

        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        logger.exception("Failed to fetch raw data")
        return False


async def test_multiple_stocks():
    """Test fetching data for multiple stocks."""
    print("\n" + "=" * 80)
    print("TEST 6: Multiple Stocks - Fetch data for 5 different stocks")
    print("=" * 80)

    symbols = ["PTT", "CPALL", "AOT", "KBANK", "MINT"]
    results = []

    for symbol in symbols:
        try:
            directors = await get_board_of_directors(symbol)
            results.append((symbol, directors))

            # Find chairman
            chairman = next(
                (d for d in directors if "CHAIRMAN" in d.positions), None
            )
            chairman_name = chairman.name[:50] if chairman else "N/A"

            # Count independent directors
            independent_count = sum(
                1
                for d in directors
                if any("INDEPENDENT" in pos for pos in d.positions)
            )

            print(
                f"\n  ✓ {symbol:6} - {len(directors):2} directors, "
                f"{independent_count:2} independent"
            )
            print(f"           Chairman: {chairman_name}")

        except Exception as e:
            print(f"\n  ✗ {symbol:6} - Error: {e}")
            logger.error(f"Failed to fetch data for {symbol}: {e}")

    print(f"\n  Successfully fetched {len(results)}/{len(symbols)} stocks")
    return len(results) == len(symbols)


async def test_position_analysis():
    """Test analyzing board positions."""
    print("\n" + "=" * 80)
    print("TEST 7: Position Analysis - Categorize directors by position type")
    print("=" * 80)

    try:
        directors = await get_board_of_directors("MINT")

        # Group directors by position type
        position_groups = {}
        for director in directors:
            for position in director.positions:
                if position not in position_groups:
                    position_groups[position] = []
                position_groups[position].append(director.name[:40])

        print(f"\n✓ Position analysis for MINT ({len(directors)} directors)")
        print(f"\n  Positions found:")
        for position, names in sorted(position_groups.items()):
            print(f"\n    {position}:")
            for name in names:
                print(f"      - {name}")

        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        logger.exception("Failed position analysis test")
        return False


async def test_error_handling():
    """Test error handling with invalid inputs."""
    print("\n" + "=" * 80)
    print("TEST 8: Error Handling - Invalid inputs")
    print("=" * 80)

    # Test empty symbol
    try:
        await get_board_of_directors("")
        print("\n  ✗ Empty symbol should raise ValueError")
        return False
    except ValueError as e:
        print(f"\n  ✓ Empty symbol correctly raises ValueError: {e}")

    # Test invalid language
    try:
        await get_board_of_directors("PTT", lang="invalid")
        print("\n  ✗ Invalid language should raise ValueError")
        return False
    except ValueError as e:
        print(f"  ✓ Invalid language correctly raises ValueError: {e}")

    return True


async def main():
    """Run all verification tests."""
    # Setup logger with INFO level
    setup_logger(level="INFO")

    print("\n" + "=" * 80)
    print("BOARD OF DIRECTOR SERVICE VERIFICATION TESTS")
    print("=" * 80)
    print("\nThis script will test all aspects of the board of director service")
    print("including data fetching, Thai language support, and error handling.\n")

    # Run all tests
    tests = [
        test_convenience_function(),
        test_service_class(),
        test_thai_language(),
        test_symbol_normalization(),
        test_raw_data_fetch(),
        test_multiple_stocks(),
        test_position_analysis(),
        test_error_handling(),
    ]

    results = await asyncio.gather(*tests, return_exceptions=True)

    # Count successes
    successes = sum(1 for r in results if r is True)
    total = len(tests)

    # Print summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"\nTests Passed: {successes}/{total}")

    if successes == total:
        print("\n✓ All tests passed successfully!")
        return 0
    else:
        print(f"\n✗ {total - successes} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

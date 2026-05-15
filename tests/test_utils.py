"""Tests for a_stock_data package."""

import pytest

from a_stock_data.utils import (
    get_market,
    get_mootdx_market,
    get_prefix,
    normalize_code,
)


class TestUtils:
    """Test utility functions."""

    def test_get_prefix(self):
        """Test get_prefix function."""
        assert get_prefix("688017") == "sh"
        assert get_prefix("300476") == "sz"
        assert get_prefix("832000") == "bj"

    def test_normalize_code(self):
        """Test normalize_code function."""
        assert normalize_code("688017") == "688017"
        assert normalize_code("SH688017") == "688017"
        assert normalize_code("sh688017") == "688017"
        assert normalize_code("688017.SH") == "688017"
        assert normalize_code("SZ000001") == "000001"
        assert normalize_code("BJ832000") == "832000"

    def test_get_market(self):
        """Test get_market function."""
        assert get_market("688017") == "沪市"
        assert get_market("300476") == "深市"
        assert get_market("832000") == "北交所"

    def test_get_mootdx_market(self):
        """Test get_mootdx_market function."""
        assert get_mootdx_market("688017") == 1
        assert get_mootdx_market("300476") == 0

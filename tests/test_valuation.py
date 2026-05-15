"""Tests for valuation module."""

import pytest

from feifan_stock_data.valuation import calc_peg, forward_pe, pe_digestion


class TestValuation:
    """Test valuation functions."""

    def test_forward_pe(self):
        """Test forward_pe calculation."""
        assert forward_pe(100.0, 2.5) == 40.0
        assert forward_pe(100.0, 0) == float("inf")
        assert forward_pe(100.0, -1) == float("inf")

    def test_pe_digestion(self):
        """Test PE digestion calculation."""
        # 100 PE -> 30 PE @ 30% CAGR
        years = pe_digestion(100, 0.3, target_pe=30)
        assert 3 < years < 4

        # Already at target
        assert pe_digestion(25, 0.3, target_pe=30) == 0.0

        # Negative growth
        assert pe_digestion(100, -0.1) == float("inf")

    def test_calc_peg(self):
        """Test PEG calculation."""
        # 50 PE @ 40% growth
        peg = calc_peg(50, 0.4)
        assert 1.2 < peg < 1.3

        # Negative growth
        assert calc_peg(50, -0.1) == float("inf")

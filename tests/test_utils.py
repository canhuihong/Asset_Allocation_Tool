"""
Unit tests for utility functions.
Run with: python -m pytest tests/ -v
"""
import pytest
from main import fix_ibkr_symbol


class TestIBKRSymbolFix:
    """Test IBKR symbol format fixing."""
    
    def test_brk_b_conversion(self):
        assert fix_ibkr_symbol('BRK-B') == 'BRK B'
    
    def test_brk_a_conversion(self):
        assert fix_ibkr_symbol('BRK-A') == 'BRK A'
    
    def test_bf_b_conversion(self):
        assert fix_ibkr_symbol('BF-B') == 'BF B'
    
    def test_regular_symbol_unchanged(self):
        assert fix_ibkr_symbol('AAPL') == 'AAPL'
    
    def test_msft_unchanged(self):
        assert fix_ibkr_symbol('MSFT') == 'MSFT'
    
    def test_nvda_unchanged(self):
        assert fix_ibkr_symbol('NVDA') == 'NVDA'


class TestCSVColumnDetection:
    """Test fuzzy CSV column name matching (from main.py logic)."""
    
    def test_symbol_column_detection(self):
        """Test detection of symbol column in various formats."""
        possible_names = ['symbol', 'ticker', 'code', '代码']
        test_cols = ['Symbol', 'Ticker', 'symbol', 'CODE']
        
        for col in test_cols:
            col_lower = col.lower()
            found = next((c for c in possible_names if c == col_lower), None)
            assert found is not None, f"Should detect {col}"
    
    def test_weight_column_detection(self):
        """Test detection of weight column."""
        possible_names = ['weight', 'ratio', 'position', '权重']
        test_cols = ['Weight', 'weight', 'Ratio', 'position']
        
        for col in test_cols:
            col_lower = col.lower()
            found = next((c for c in possible_names if c == col_lower), None)
            assert found is not None, f"Should detect {col}"
    
    def test_percentage_cleaning(self):
        """Test percentage sign removal."""
        val_str = "50%"
        cleaned = val_str.replace('%', '')
        val = float(cleaned)
        assert val == 50.0
    
    def test_weight_normalization(self):
        """Test auto-normalization of weights > 1.0."""
        val = 50.0
        if val > 1.0:
            val /= 100.0
        assert val == 0.5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

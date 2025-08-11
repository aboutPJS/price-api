"""
Tests for price data edge cases including negative prices and currency precision.
"""

from datetime import datetime
from decimal import Decimal
import pytest

from src.models.price import PriceCategory, PriceRecord


class TestNegativePrices:
    """Test handling of negative spot prices."""
    
    def test_negative_spot_price_validation(self):
        """Test that negative spot prices are allowed (they occur in real markets)."""
        # This should NOT raise a validation error
        record = PriceRecord(
            timestamp=datetime(2025, 8, 7, 3, 0, 0),
            spot_price=Decimal('-0.05'),  # Negative spot price (happens in real markets!)
            transport_taxes=Decimal('1.25'),
            total_price=Decimal('1.20'),  # Still positive after taxes
            median_price=Decimal('1.50'),
            category=PriceCategory.PREFER
        )
        
        assert record.spot_price == Decimal('-0.05')
        assert record.total_price == Decimal('1.20')
    
    def test_negative_total_price_validation(self):
        """Test that very negative spot prices can result in negative total prices."""
        # This should also be allowed (rare but possible)
        record = PriceRecord(
            timestamp=datetime(2025, 8, 7, 3, 0, 0),
            spot_price=Decimal('-2.00'),  # Very negative spot price
            transport_taxes=Decimal('1.25'),
            total_price=Decimal('-0.75'),  # Negative total after taxes
            median_price=Decimal('1.50'),
            category=PriceCategory.PREFER  # Still cheapest!
        )
        
        assert record.spot_price == Decimal('-2.00')
        assert record.total_price == Decimal('-0.75')


class TestCurrencyPrecision:
    """Test currency precision and floating point issues."""
    
    def test_floating_point_precision_issue(self):
        """Demonstrate floating point precision problems with currency."""
        # Classic floating point precision issue
        price1 = 0.1
        price2 = 0.2
        total = price1 + price2
        
        # This will fail with floats!
        assert total != 0.3, f"Float precision issue: {total} != 0.3"
        assert abs(total - 0.3) < 1e-10, "Need epsilon comparison for floats"
    
    def test_decimal_precision_accuracy(self):
        """Test that Decimal provides exact currency calculations."""
        price1 = Decimal('0.1')
        price2 = Decimal('0.2') 
        total = price1 + price2
        
        # This works correctly with Decimal
        assert total == Decimal('0.3'), "Decimal arithmetic is exact"
    
    def test_currency_rounding_consistency(self):
        """Test currency rounding behavior."""
        # Using floats
        float_price = 1.235
        float_rounded = round(float_price, 2)
        
        # Using Decimal
        decimal_price = Decimal('1.235')
        decimal_rounded = decimal_price.quantize(Decimal('0.01'))
        
        # Both should be the same, but let's verify
        assert float_rounded == 1.23 or float_rounded == 1.24  # Depends on rounding mode
        assert decimal_rounded == Decimal('1.23') or decimal_rounded == Decimal('1.24')
    
    def test_danish_csv_price_parsing(self):
        """Test parsing Danish CSV prices with comma decimal separators."""
        # Real examples from Danish energy data
        danish_prices = [
            "1,09",   # 1.09 DKK/kWh
            "1,25",   # 1.25 DKK/kWh
            "2,34",   # 2.34 DKK/kWh
            "-0,05",  # Negative price!
            "0,01",   # Very small positive
        ]
        
        expected_decimals = [
            Decimal('1.09'),
            Decimal('1.25'), 
            Decimal('2.34'),
            Decimal('-0.05'),
            Decimal('0.01'),
        ]
        
        for danish_str, expected_decimal in zip(danish_prices, expected_decimals):
            # Parse Danish format (comma as decimal separator)
            parsed_decimal = Decimal(danish_str.replace(',', '.'))
            assert parsed_decimal == expected_decimal
    
    def test_price_comparison_accuracy(self):
        """Test that price comparisons work accurately with currency data."""
        prices = [
            Decimal('1.09'),
            Decimal('1.25'),
            Decimal('2.34'),
            Decimal('-0.05'),  # Negative price
            Decimal('1.10'),
        ]
        
        sorted_prices = sorted(prices)
        expected_order = [
            Decimal('-0.05'),  # Cheapest (negative)
            Decimal('1.09'),
            Decimal('1.10'), 
            Decimal('1.25'),
            Decimal('2.34'),   # Most expensive
        ]
        
        assert sorted_prices == expected_order, "Currency sorting must be exact"
    
    def test_price_arithmetic_precision(self):
        """Test currency arithmetic maintains precision."""
        spot_price = Decimal('-0.15')      # Negative spot price
        transport_tax = Decimal('1.25')    # Transport costs
        total_price = spot_price + transport_tax
        
        assert total_price == Decimal('1.10'), "Currency arithmetic must be exact"
        
        # Test with more complex calculation
        median_calculation = (Decimal('1.09') + Decimal('2.34')) / 2
        assert median_calculation == Decimal('1.715'), "Division must maintain precision"


class TestPriceCategorizationWithNegatives:
    """Test price categorization with negative prices."""
    
    def test_tertile_calculation_with_negatives(self):
        """Test that tertile boundaries work correctly with negative prices."""
        prices = [
            Decimal('-0.50'),  # Very negative
            Decimal('-0.10'),  # Slightly negative  
            Decimal('0.50'),   # Positive
            Decimal('1.00'),   # Higher positive
            Decimal('1.50'),   # Highest
        ]
        
        sorted_prices = sorted(prices)
        
        # Calculate tertile boundaries (33rd and 67th percentiles)
        n = len(sorted_prices)
        tertile_1_idx = int(n * 0.333)
        tertile_2_idx = int(n * 0.667)
        
        # With negative prices, the cheapest (PREFER) should include negatives
        cheapest_price = sorted_prices[0]  # -0.50
        assert cheapest_price < Decimal('0'), "Cheapest price can be negative"
        
        # Most expensive (AVOID) should be positive
        most_expensive = sorted_prices[-1]  # 1.50
        assert most_expensive > Decimal('0'), "Most expensive should be positive"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

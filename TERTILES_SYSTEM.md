# Tertiles-Based Price Categorization System

## Overview

The Energy Price API uses a **tertiles-based categorization system** to classify energy prices into three balanced categories, providing clear guidance for optimal energy usage timing.

## Categories

- **PREFER** (Bottom 1/3): Least expensive hours - optimal for energy consumption
- **OKAY** (Middle 1/3): Moderate prices - acceptable for flexible usage
- **AVOID** (Top 1/3): Most expensive hours - avoid energy-intensive activities

## Implementation

### Percentile Calculation with Linear Interpolation

The system uses proper percentile calculation with linear interpolation (similar to `numpy.percentile`) rather than simple index rounding:

```python
def _calculate_percentile(sorted_values: List[float], percentile: float) -> float:
    """
    Calculate percentile using linear interpolation.
    
    - Handles edge cases (empty lists, single values)
    - Uses linear interpolation between nearest values
    - More accurate than simple index-based approaches
    """
```

### Tertile Boundaries

The system calculates:
- **33.333rd percentile** as the lower boundary (PREFER/OKAY threshold)
- **66.667th percentile** as the upper boundary (OKAY/AVOID threshold)

### Edge Case Handling

- **Empty datasets**: Returns default boundaries (0.0, 0.0)
- **Small datasets (< 3 values)**: Uses proportional range division
- **Single values**: Returns the same value for all boundaries

## Benefits

1. **Balanced Distribution**: Each category contains approximately 1/3 of the data
2. **Accurate Calculation**: Linear interpolation provides smooth percentile values
3. **Practical Guidance**: Clear action recommendations for each category
4. **Edge Case Robust**: Handles all dataset sizes gracefully

## Usage in Application

The tertiles are calculated for each 48-hour period (today + tomorrow) and applied to all price records within that period. This ensures:

- Categories are relative to the current price forecast
- Distribution remains balanced regardless of overall price levels
- Energy optimization decisions are based on near-term price variations

## Code Architecture

### Helper Functions
- `_calculate_percentile()`: Core percentile calculation with interpolation
- `_calculate_tertile_boundaries()`: Wrapper for 33rd/67th percentile calculation

### Integration Points
- `PriceService._parse_danish_csv()`: Applied during data parsing
- Test fixtures: Used for consistent test data generation
- Database: Categories stored as string values in the database

This system provides a robust foundation for energy price categorization that scales well across different price environments and dataset sizes.

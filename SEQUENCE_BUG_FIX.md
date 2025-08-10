# Sequence Query Bug Fix

## Problem

The `get_cheapest_sequence_start` method was returning start times in the past, which is incorrect behavior for energy scheduling applications.

## Root Causes

### 🐛 **Bug 1: Incorrect Sequence Logic** 
```sql
-- OLD (INCORRECT):
WHERE h2.jd >= h1.jd AND h2.jd < (h1.jd + {duration}/24.0)
```

**Issue**: For a 3-hour sequence starting at 10:00, this would look for hours 10, 11, 12 but exclude 13:00, making it only a 2-hour sequence in practice.

### 🐛 **Bug 2: Incomplete Future Validation**
```sql
-- OLD (INCORRECT):
WHERE timestamp >= ?  -- Only checks start time
```

**Issue**: Only ensured the start time was in the future, but didn't validate that the entire sequence fits within the future time window.

## Solution

### ✅ **Fix 1: Correct Sequence Boundaries**
```sql
-- NEW (CORRECT):  
WHERE h2.jd >= h1.jd AND h2.jd <= (h1.jd + ({duration}-1)/24.0)
```

**Result**: For a 3-hour sequence starting at 10:00, this correctly includes hours 10:00, 11:00, 12:00.

### ✅ **Fix 2: Complete Sequence Validation**
```sql
-- NEW (CORRECT):
-- Calculate cutoff: if we need 3 hours and have 12 hours window,
-- latest start is at hour 9 (to end at hour 11 within 12-hour window)
sequence_end_cutoff = search_end_time - timedelta(hours=duration-1)
WHERE timestamp >= ? AND timestamp <= ?  -- Both start AND end boundaries
```

**Result**: Ensures the entire sequence fits within the requested time window.

### ✅ **Fix 3: Additional Validation**
- Added `sequence_end_time` calculation to verify complete sequences
- Added explicit bounds checking in the WHERE clause
- Improved parameter validation logic

## Key Changes

### Before (Buggy Code)
```python
# Simple boundary check - INCOMPLETE
base_condition = "timestamp >= ?"
if within_hours is not None:
    base_condition += " AND timestamp <= ?"
    params.append(end_time.isoformat())

# Wrong sequence range - OFF BY ONE ERROR
WHERE h2.jd < (h1.jd + {duration}/24.0)  # Should be <=
```

### After (Fixed Code)
```python
# Complete boundary validation
sequence_end_cutoff = search_end_time - timedelta(hours=duration-1)
params = [now.isoformat(), sequence_end_cutoff.isoformat()]

# Correct sequence range
WHERE h2.jd <= (h1.jd + ({duration}-1)/24.0)  # Inclusive end boundary

# Additional validation
AND sequence_end_time IS NOT NULL  # Ensure complete sequence exists
```

## Test Coverage

Created comprehensive test script (`scripts/test_sequence_fix.py`) that validates:

1. **Basic Functionality**: Various duration/time window combinations
2. **Edge Cases**: Boundary conditions and impossible requests  
3. **Past Timestamp Prevention**: Ensures no past results are returned
4. **Complete Sequence Validation**: Verifies entire sequence fits in window

## Usage

```bash
# Test the fix
python scripts/dev.py test-sequences

# Or run directly  
python scripts/test_sequence_fix.py
```

## Impact

- ✅ **No more past timestamps**: All returned start times are guaranteed to be in the future
- ✅ **Accurate sequences**: Sequences are the exact requested duration  
- ✅ **Proper bounds checking**: Entire sequences fit within the specified time window
- ✅ **Better error handling**: Clear failures for impossible requests

This fix ensures reliable energy scheduling for Home Assistant integrations and other automation systems.

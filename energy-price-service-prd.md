# Product Requirements Document
## Dynamic Energy Price Optimization System - PoC

### Executive Summary
A simple system to automatically schedule the dishwasher during periods of lowest electricity prices, leveraging daily price prediction data to minimize energy costs.

---

## 1. Problem Statement

### Current Situation
- User has a dynamic energy contract with time-varying electricity prices
- Dishwasher is operated manually without price consideration
- Electricity provider publishes CSV files daily at 2 PM with next-day price predictions (>24h forecast)
- Significant cost savings potential is being missed

### Target Users
- Homeowners with dynamic energy contracts and smart dishwashers
- Cost-conscious households with flexible appliance usage patterns

---

## 2. Solution Overview - PoC Scope

### System Architecture
```
Energy Provider CSV (daily 2 PM) → Price Service API → Home Assistant → Siemens Dishwasher
```

### Core Components
1. **Energy Price Service**: Simple API with 2 endpoints for optimal timing
2. **Home Assistant Integration**: Basic automation to schedule dishwasher
3. **Database**: SQLite for price data storage and fast querying

---

## 3. Technical Requirements

### 3.1 Database Choice: SQLite

**Why SQLite for this PoC:**
- **Simplicity**: Single file database, no server setup required
- **Performance**: Fast queries for time-series data with proper indexing
- **Zero Configuration**: No database administration overhead
- **Embedded**: Runs in same process as API service
- **ACID Compliance**: Reliable for financial data (prices)
- **Perfect Scale**: 365 days × 24 hours = ~9K records/year (well within SQLite limits)
- **SQL Support**: Complex time-based queries for sequence finding
- **Backup**: Simple file copy for data backup

**Alternative Considered**: In-memory/CSV processing rejected due to:
- Slow sequence queries (O(n) linear search)
- No concurrent read/write support
- Complex time-window calculations

---

## 4. Functional Requirements

### 4.1 Energy Price Service

#### FR-1: Data Management
- **REQ-1.1**: Download CSV files daily at 2:10 PM from Andel Energi API
  - URL: `https://andelenergi.dk/?obexport_format=csv&obexport_start={start_date}&obexport_end={end_date}&obexport_region=east&obexport_tax=0&obexport_product_id=1%231%23TIMEENERGI`
  - Region: **MUST be "east"** (required parameter)
  - Date range: Dynamic calculation for next 24+ hours
- **REQ-1.2**: Parse CSV data with Danish locale (comma as decimal separator)
- **REQ-1.3**: Store comprehensive price data in SQLite database
- **REQ-1.4**: Maintain rolling window of prediction data with automatic cleanup of old records

#### FR-2: Price Analysis - Enhanced with Real Data
- **REQ-2.1**: Calculate daily median of **total_price** for categorization
- **REQ-2.2**: Categorize each hour based on total_price as: 
  - **CHEAPEST**: Single cheapest hour of the day (e.g., 1.44 DKK/kWh from example)
  - **CHEAP**: Below median total_price
  - **EXPENSIVE**: Above median total_price
- **REQ-2.3**: Use **total_price** column for all optimization calculations (includes all costs)

#### FR-3: API Endpoints - Minimal Set

##### Endpoint 1: Single Cheapest Hour
```http
GET /api/v1/cheapest-hour?within_hours=24
```
**Purpose**: Find the single cheapest hour within specified timeframe  
**Parameters**: 
- `within_hours` (optional): Look ahead window, defaults to all available predictions
**Response**: 
```json
{
  "start_time": "2025-08-07T14:00:00Z"
}
```

##### Endpoint 2: Cheapest Sequence Start
```http
GET /api/v1/cheapest-sequence-start?duration=3&within_hours=10
```
**Purpose**: Find start time of cheapest consecutive sequence  
**Parameters**: 
- `duration` (required): Length of sequence in hours
- `within_hours` (optional): Look ahead window, defaults to all available predictions
**Response**: 
```json
{
  "start_time": "2025-08-07T23:00:00Z"
}
```

### 4.2 Home Assistant Integration - Simplified

#### FR-4: Dishwasher Automation
- **REQ-4.1**: Detect when dishwasher is ready to run (Home Connect integration)
- **REQ-4.2**: Get selected program duration from dishwasher
- **REQ-4.3**: Round up duration to full hours
- **REQ-4.4**: Call API: `getCheapestSequenceStart(duration, within_reasonable_timeframe)`
- **REQ-4.5**: Use Home Connect API to set dishwasher start time
- **REQ-4.6**: Manual override always available through Home Assistant UI

#### Use Case Flow:
```
1. User loads dishwasher → "Ready" state detected
2. HA reads program duration (e.g., 2.5 hours) → rounds to 3 hours  
3. HA calls API: /cheapest-sequence-start?duration=3&within_hours=12
4. API responds: {"start_time": "2025-08-07T23:00:00Z"}
5. HA sets dishwasher start time to 23:00 via Home Connect
6. At 23:00: Dishwasher automatically starts (cheapest 3-hour window)
```

---

## 5. Technical Implementation

### 5.1 Technology Stack - PoC
- **Language**: Python
- **API Framework**: FastAPI (lightweight, fast, auto-documentation)
- **Database**: SQLite with datetime indexing
- **Scheduler**: APScheduler for daily CSV fetching at 2:10 PM
- **Data Processing**: Pandas for CSV parsing
- **Deployment**: Docker container

### 5.2 Data Models - Minimal

#### Price Record - Enhanced Model
```python
@dataclass
class PriceRecord:
    timestamp: datetime          # Parsed from "Start": "07.08.2025 - 23:00"
    spot_price: float           # "Elpris" - raw energy price
    transport_taxes: float      # "Transport og afgifter" - grid costs + taxes  
    total_price: float         # "Total" - final price per kWh
    category: str              # CHEAPEST, CHEAP, EXPENSIVE (based on total_price)
    
    # Note: Danish CSV uses comma as decimal separator ("1,09" → 1.09)
```

#### API Responses
```python
@dataclass 
class OptimalTimeResponse:
    start_time: datetime  # ISO format timestamp
```

### 5.3 CSV Processing - Andel Energi Format
```python
# Example CSV structure (Danish format):
# "Start","Elpris","Transport og afgifter","Total"
# "07.08.2025 - 23:00","1,09","1,25","2,34"

def parse_andel_energi_csv(csv_content):
    """
    Parse Andel Energi CSV with Danish locale:
    - Comma decimal separator ("1,09" → 1.09)
    - Danish date format: "07.08.2025 - 23:00"
    - Headers: Start, Elpris, Transport og afgifter, Total
    """
    
def build_daily_url(date):
    """
    Generate dynamic URL for CSV download:
    https://andelenergi.dk/?obexport_format=csv
    &obexport_start=2025-08-07
    &obexport_end=2025-08-08  
    &obexport_region=east     # MANDATORY
    &obexport_tax=0
    &obexport_product_id=1%231%23TIMEENERGI
    """
```

---

## 6. Non-Functional Requirements - PoC

### 6.1 Reliability - Essential Only
- **REQ-6.1**: Graceful handling of CSV download failures (retry logic)
- **REQ-6.2**: Manual dishwasher operation remains unaffected if service fails
- **REQ-6.3**: Basic error logging for debugging

### 6.2 Performance - PoC Adequate  
- **REQ-6.4**: API response time < 1 second (acceptable for scheduling use case)
- **REQ-6.5**: Daily CSV processing < 60 seconds

---

## 7. Implementation Phases - PoC Focus

### Phase 1: Core Service (Week 1)
- FastAPI project with Docker
- CSV download at 2:10 PM daily  
- SQLite storage with basic price records
- Two API endpoints implementation

### Phase 2: Algorithm & Testing (Week 2)
- Cheapest hour finding logic
- Cheapest sequence algorithm with sliding window
- Unit tests for edge cases
- Manual API testing

### Phase 3: Home Assistant Integration (Week 3)  
- Home Connect dishwasher integration research
- Basic automation: ready state → API call → set start time
- Manual override controls
- End-to-end testing with actual dishwasher

---

## 8. Success Criteria - PoC

### Primary Goals
- **Functional**: Dishwasher automatically starts during cheapest predicted periods
- **User Experience**: Manual override works reliably
- **Cost Impact**: Measurable difference in electricity costs for dishwasher usage

### Technical Goals  
- **API Reliability**: Successfully processes daily CSV data
- **Integration Success**: Home Assistant successfully controls dishwasher timing
- **Data Accuracy**: Correct identification of cheapest sequences

---

## 9. Future Enhancements (Post-PoC)

### Beyond PoC Scope
- Multiple appliance support
- Advanced price analytics and savings calculation
- Mobile notifications and monitoring dashboard
- Machine learning for usage pattern optimization
- Integration with other smart home systems

---

## 10. Key Assumptions

### Data Assumptions
- Andel Energi CSV format remains stable (Start, Elpris, Transport og afgifter, Total)
- Daily publication at 2 PM continues
- **East region** data availability continues
- Danish number format (comma decimal separator) remains consistent
- Price predictions are reasonably accurate

### Technical Assumptions  
- Home Connect API allows programmatic start time setting
- Home Assistant can reliably detect dishwasher ready state
- Network connectivity available for daily downloads

### User Assumptions
- User accepts delayed dishwasher operation for cost savings
- Typical flexibility window of 8-12 hours acceptable
- Manual override sufficient for urgent washing needs

---

*Document Version: 2.0 - PoC Focused*  
*Last Updated: August 6, 2025*  
*Target: Proof of Concept Implementation*
# Energy Price API

A Dynamic Energy Price Optimization System that integrates with Andel Energi to provide optimal timing for energy usage based on real-time price predictions.

## Overview

This service automatically schedules energy-consuming appliances (like dishwashers) during periods of lowest electricity prices, leveraging daily price prediction data from Andel Energi to minimize energy costs.

### Key Features

- **Real-time Price Data**: Daily fetching of energy price predictions from Andel Energi CSV API
- **Optimization Algorithms**: Find cheapest single hours or consecutive sequences for appliance scheduling
- **RESTful API**: Simple endpoints for Home Assistant integration
- **Automated Scheduling**: Daily price data fetching at 2:10 PM Copenhagen time
- **SQLite Storage**: Efficient local database with automatic cleanup
- **Docker Ready**: Containerized deployment with health checks

## Architecture

```
Andel Energi CSV (daily 2 PM) → Price Service API → Home Assistant → Smart Appliances
```

## API Endpoints

### 1. Get Cheapest Hour
```http
GET /api/v1/cheapest-hour?within_hours=24
```
Returns the single cheapest hour within the specified timeframe.

**Response:**
```json
{
  "start_time": "2025-08-07T14:00:00Z"
}
```

### 2. Get Cheapest Sequence Start
```http
GET /api/v1/cheapest-sequence-start?duration=3&within_hours=12
```
Returns the start time of the cheapest consecutive sequence of specified duration.

**Response:**
```json
{
  "start_time": "2025-08-07T23:00:00Z"
}
```

### 3. Health Check
```http
GET /api/v1/health
```
Service health status for monitoring.

## Quick Start

### Using Docker (Recommended for Production)

#### Development with Docker

1. **Clone and configure:**
   ```bash
   git clone <repository-url>
   cd price-api
   cp .env.example .env
   # Edit .env with your settings
   ```

2. **Start development environment:**
   ```bash
   docker-compose up -d
   ```
   This uses the default `docker-compose.yml` with `docker-compose.override.yml` for development features.

3. **Verify installation:**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

#### Production Docker Deployment

1. **Configure for production:**
   ```bash
   cp .env.example .env
   # Edit .env with production values
   mkdir -p data logs
   ```

2. **Deploy with production settings:**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

3. **Verify deployment:**
   ```bash
   curl http://localhost:8000/api/v1/health
   docker logs energy-price-api-prod
   ```

### Step-by-Step Local Development Setup

Follow these steps to run the service locally for development:

1. **Activate virtual environment**
   ```bash
   source venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   python -m pip install -r requirements.txt
   ```

3. **Initialize database** (creates SQLite DB and schema)
   ```bash
   python scripts/dev.py init-db
   ```

4. **Start the API server** (automatically starts scheduler)
   ```bash
   python -m src.main
   ```
   The API will be available at `http://localhost:8000`

5. **Manual price data fetch** (optional)
   ```bash
   python scripts/dev.py fetch-prices
   ```

6. **Run tests** (ensure API correctness)
   ```bash
   python -m pytest tests/ -v
   ```

7. **Additional management commands**
   ```bash
   python scripts/dev.py show-prices          # Show recent prices
   python scripts/dev.py test-optimization    # Test optimization algorithms
   python scripts/dev.py cleanup-data         # Clean old data
   python scripts/dev.py show-config          # Show current settings
   python scripts/dev.py test-api             # Test Andel Energi connection
   ```

## Docker vs Local Development

### Key Differences

| Aspect | Local Development | Docker Deployment |
|--------|-------------------|-------------------|
| **Database Initialization** | Manual `python scripts/dev.py init-db` | Automatic on container startup |
| **Dependencies** | Manual venv management | Containerized with all dependencies |
| **Data Persistence** | Files in `./data/` directory | Docker volumes (persistent across restarts) |
| **Environment Config** | Reads from `.env` or defaults | Uses `.env` + container environment overrides |
| **Process Management** | Single Python process | Container with proper signal handling |
| **Health Checks** | Manual via scripts | Built-in Docker health checks |
| **Log Management** | Console/file output | Structured Docker logging with rotation |
| **Resource Limits** | System resources | Configurable CPU/memory limits |
| **Security** | Runs as current user | Runs as non-root user in container |
| **Networking** | Direct host access | Isolated container network |

### When to Use Each

**Use Local Development When:**
- Actively developing and debugging code
- Need direct access to development tools
- Running tests and code quality checks
- Using database inspection scripts frequently

**Use Docker When:**
- Deploying to production
- Need consistent environments
- Want automatic health checks and restarts
- Integrating with other containerized services
- Need resource isolation and limits

## Configuration

Configuration is handled via environment variables. See `.env.example` for all available options:

| Variable | Description | Default |
|----------|-------------|---------|
| `API_HOST` | API host address | `0.0.0.0` |
| `API_PORT` | API port | `8000` |
| `DATABASE_PATH` | SQLite database path | `./data/prices.db` |
| `ANDEL_ENERGI_REGION` | Energy region (must be "east") | `east` |
| `FETCH_HOUR` | Daily fetch hour (24h format) | `14` |
| `FETCH_MINUTE` | Daily fetch minute | `10` |
| `DATA_RETENTION_DAYS` | Days to retain old data | `30` |

## Development

### Development Scripts

Use the development helper script for common tasks:

```bash
# Initialize database
python scripts/dev.py init-db

# Manually fetch price data
python scripts/dev.py fetch-prices

# View recent price data
python scripts/dev.py show-prices

# Test optimization algorithms
python scripts/dev.py test-optimization

# Clean up old data
python scripts/dev.py cleanup-data

# Show current configuration
python scripts/dev.py show-config

# Test API connectivity
python scripts/dev.py test-api
```

### Database Inspection Tools

Use the database inspection script to monitor and debug price data:

```bash
# Show database schema and structure
python scripts/db_inspect.py schema

# Show database statistics
python scripts/db_inspect.py stats

# Show recent data (default: 12 hours)
python scripts/db_inspect.py recent [HOURS]

# Check for missing hourly data
python scripts/db_inspect.py gaps

# Vacuum database to reclaim space
python scripts/db_inspect.py vacuum

# Run all checks
python scripts/db_inspect.py all
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_api.py
```

### Code Quality

```bash
# Format code
black src tests scripts

# Sort imports
isort src tests scripts

# Type checking
mypy src

# Lint code
flake8 src tests
```

## Home Assistant Integration

### Example Automation

```yaml
alias: "Dishwasher Optimal Start"
trigger:
  - platform: state
    entity_id: sensor.dishwasher_status
    to: "ready"
action:
  - service: rest_command.get_optimal_time
    data:
      duration: 3  # dishwasher program duration in hours
  - service: siemens_home_connect.set_start_time
    data:
      entity_id: dishwasher.siemens_dishwasher
      start_time: "{{ states('sensor.optimal_start_time') }}"
```

### REST Command Configuration

```yaml
rest_command:
  get_optimal_time:
    url: "http://price-api:8000/api/v1/cheapest-sequence-start"
    method: GET
    payload: "duration={{ duration }}&within_hours=12"
    headers:
      Content-Type: "application/json"
```

## Data Format

The service processes Andel Energi CSV data with the following format:

```csv
"Start","Elpris","Transport og afgifter","Total"
"07.08.2025 - 23:00","1,09","1,25","2,34"
```

- **Start**: Danish datetime format (DD.MM.YYYY - HH:MM)
- **Elpris**: Spot price (DKK/kWh, comma decimal separator)
- **Transport og afgifter**: Grid costs and taxes (DKK/kWh)
- **Total**: Final price per kWh (DKK/kWh)

### Price Categorization

The service categorizes all price data using a **tertiles-based system** calculated from 48-hour periods (today + tomorrow):

- **PREFER** (Bottom 1/3): Least expensive hours - optimal for energy consumption
- **OKAY** (Middle 1/3): Moderate prices - acceptable for flexible usage
- **AVOID** (Top 1/3): Most expensive hours - avoid energy-intensive activities

This categorization provides a more balanced distribution compared to simple median-based approaches, making it easier to identify cost-effective time slots for appliance scheduling.

## Monitoring

### Health Checks

The service includes health checks for:
- Database connectivity
- Recent data availability
- Service responsiveness

### Logging

Structured JSON logging is available with configurable levels:
- `DEBUG`: Detailed debugging information
- `INFO`: General operational messages
- `WARNING`: Warning conditions
- `ERROR`: Error conditions

### Metrics

Monitor these key metrics:
- API response times
- Daily fetch success rate
- Database record count
- Price optimization accuracy

## Deployment

### Production Checklist

- [ ] Configure environment variables in `.env`
- [ ] Set up log rotation
- [ ] Configure monitoring and alerting
- [ ] Set up regular database backups
- [ ] Configure reverse proxy (nginx/traefik)
- [ ] Enable HTTPS
- [ ] Configure firewall rules

### Docker Production

```bash
# Build production image
docker build -t energy-price-api:latest .

# Run with production settings
docker run -d \
  --name price-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --env-file .env \
  energy-price-api:latest
```

## Troubleshooting

### Common Issues

**1. No price data available**
- Check Andel Energi API connectivity
- Verify region setting is "east"
- Check daily fetch schedule

**2. Database errors**
- Ensure data directory has write permissions
- Check disk space availability
- Verify database file integrity

**3. API timeout errors**
- Increase httpx timeout settings
- Check network connectivity
- Verify DNS resolution

### Docker Management Commands

When running in Docker, you can still use the development and inspection scripts:

```bash
# Execute commands inside running container
docker exec energy-price-api-prod python scripts/dev.py show-prices
docker exec energy-price-api-prod python scripts/db_inspect.py stats

# Manual price fetch
docker exec energy-price-api-prod python scripts/dev.py fetch-prices

# Database inspection
docker exec energy-price-api-prod python scripts/db_inspect.py all

# Interactive shell in container
docker exec -it energy-price-api-prod /bin/bash
```

### Log Analysis

```bash
# View recent logs
docker logs price-api --tail 100

# Follow logs in real-time
docker logs price-api -f

# Filter error logs
docker logs price-api 2>&1 | grep ERROR
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Make changes and add tests
4. Run code quality checks
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the development scripts for debugging tools

# Find Flights MCP Server
MCP server for searching and retrieving flight information using Duffel API.

## Features
- Search for flights between multiple destinations
- Support for one-way, round-trip, and multi-city flight queries
- Detailed flight offer information
- Flexible search parameters (departure times, cabin class, number of passengers)
- Automatic handling of flight connections

## Prerequisites
- Python 3.x
- Duffel API Live Key

## Getting Your Duffel API Key
1. Visit [Duffel Website](https://duffel.com)
2. Create an account or log in
3. Navigate to API settings
4. Generate a new Live API key (there are two keys, one for testing and one for live, make sure to use the live key)

### Note on API Usage Limits
- Check Duffel's current pricing and usage limits
- Different tiers available based on your requirements
- Recommended to review current pricing on their website

## Installation
Clone the repository:
```bash
git clone https://github.com/ravinahp/flights-mcp
cd find-flights-mcp
```

Install dependencies using uv:
```bash
uv sync
```
Note: We use uv instead of pip since the project uses pyproject.toml for dependency management.

## Configure as MCP Server
To add this tool as an MCP server, modify your Claude desktop configuration file.

Configuration file locations:
- MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`

Add the following configuration to your JSON file:
```json
{
    "find-flights-mcp": {
        "command": "uv",
        "args": [
            "--directory",
            "/Users/YOUR_USERNAME/Code/find-flights-mcp",
            "run",
            "find-flights-mcp"
        ],
        "env": {
            "DUFFEL_API_KEY_LIVE": "your_duffel_live_api_key_here"
        }
    }
}
```

⚠️ IMPORTANT:
- Replace `YOUR_USERNAME` with your actual system username
- Replace `your_duffel_live_api_key_here` with your actual Duffel Live API key
- Ensure the directory path matches your local installation

## Deployment
### Building
Prepare the package:
```bash
# Sync dependencies and update lockfile
uv sync

# Build package
uv build
```
This will create distributions in the `dist/` directory.

## Debugging
For the best debugging experience, use the MCP Inspector:
```bash
npx @modelcontextprotocol/inspector uv --directory /path/to/find-flights-mcp run find-flights-mcp
```

The Inspector provides:
- Real-time request/response monitoring
- Input/output validation
- Error tracking
- Performance metrics

## Available Tools

### 1. Search Flights
```python
@mcp.tool()
async def search_flights(params: FlightSearch) -> str:
    """Search for flights based on parameters."""
```
Supports three flight types:
- One-way flights
- Round-trip flights
- Multi-city flights

Parameters include:
- `type`: Flight type ('one_way', 'round_trip', 'multi_city')
- `origin`: Origin airport code
- `destination`: Destination airport code
- `departure_date`: Departure date (YYYY-MM-DD)
- Optional parameters:
  - `return_date`: Return date for round-trips
  - `adults`: Number of adult passengers
  - `cabin_class`: Preferred cabin class
  - `departure_time`: Specific departure time range
  - `arrival_time`: Specific arrival time range
  - `max_connections`: Maximum number of connections

### 2. Get Offer Details
```python
@mcp.tool()
async def get_offer_details(params: OfferDetails) -> str:
    """Get detailed information about a specific flight offer."""
```
Retrieves comprehensive details for a specific flight offer using its unique ID.

### 3. Search Multi-City Flights
```python
@mcp.tool(name="search_multi_city")
async def search_multi_city(params: MultiCityRequest) -> str:
    """Search for multi-city flights."""
```
Specialized tool for complex multi-city flight itineraries.

Parameters include:
- `segments`: List of flight segments
- `adults`: Number of adult passengers
- `cabin_class`: Preferred cabin class
- `max_connections`: Maximum number of connections

## Use Cases
### Some Example (But try it out yourself!)
You can use these tools to find flights with various complexities:
- "Find a one-way flight from SFO to NYC on Jan 7 for 2 adults in business class"
- "Search for a round-trip flight from LAX to London, departing Jan 8 and returning Jan 15"
- "Plan a multi-city trip from New York to Paris on Jan 7, then to Rome on Jan 10, and back to New York on Jan 15"
- "What is the cheapest flight from SFO to LAX from Jan 7 to Jan 15 for 2 adults in economy class?"

## Response Format
The tools return JSON-formatted responses with:
- Flight offer details
- Pricing information
- Slice (route) details
- Carrier information
- Connection details

## Error Handling
The service includes robust error handling for:
- API request failures
- Invalid airport codes
- Missing or invalid API keys
- Network timeouts
- Invalid search parameters

## Contributing
[Add guidelines for contribution, if applicable]

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Performance Notes
- Searches are limited to 50 offers for one-way/round-trip flights
- Multi-city searches are limited to 10 offers
- Supplier timeout is set to 15-30 seconds depending on the search type

### Cabin Classes
Available cabin classes:
- `economy`: Standard economy class
- `premium_economy`: Premium economy class
- `business`: Business class
- `first`: First class

Example request with cabin class:
```json
{
  "params": {
    "type": "one_way",
    "adults": 1,
    "origin": "SFO",
    "destination": "LAX",
    "departure_date": "2025-01-12",
    "cabin_class": "business"  // Specify desired cabin class
  }
}
```
"""Flight search tools using Duffel API."""

import logging
from datetime import datetime
from typing import List
import json
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from . import duffel_api

# Set up logging
logger = logging.getLogger(__name__)

# Initialize FastMCP server and API client
mcp = FastMCP("find-flights-mcp")
flight_client = duffel_api.Client(logger)

class FlightSearch(BaseModel):
    """Model for flight search parameters."""
    type: str = Field(..., description="Type of flight: 'one_way', 'round_trip', or 'multi_city'")
    origin: str = Field(..., description="Origin airport code")
    destination: str = Field(..., description="Destination airport code")
    departure_date: str = Field(..., description="Departure date (YYYY-MM-DD)")
    return_date: str | None = Field(None, description="Return date for round trips (YYYY-MM-DD)")
    additional_stops: List[dict] | None = Field(None, description="Additional stops for multi-city trips")
    cabin_class: str = Field("economy", description="Cabin class (economy, business, first)")
    adults: int = Field(1, description="Number of adult passengers")

@mcp.tool()
async def search_flights(params: FlightSearch) -> str:
    """Search for flights based on parameters."""
    try:
        slices = []
        
        # Build slices based on flight type
        if params.type == "one_way":
            slices = [{
                "origin": params.origin,
                "destination": params.destination,
                "departure_date": params.departure_date,
                "departure_time": {
                    "from": "00:00",
                    "to": "23:59"
                }
            }]
        elif params.type == "round_trip":
            if not params.return_date:
                raise ValueError("Return date required for round-trip flights")
            slices = [
                {
                    "origin": params.origin,
                    "destination": params.destination,
                    "departure_date": params.departure_date,
                    "departure_time": {
                        "from": "00:00",
                        "to": "23:59"
                    }
                },
                {
                    "origin": params.destination,
                    "destination": params.origin,
                    "departure_date": params.return_date,
                    "departure_time": {
                        "from": "00:00",
                        "to": "23:59"
                    }
                }
            ]
        elif params.type == "multi_city":
            if not params.additional_stops:
                raise ValueError("Additional stops required for multi-city flights")
            
            # First leg
            slices.append({
                "origin": params.origin,
                "destination": params.destination,
                "departure_date": params.departure_date,
                "departure_time": {
                    "from": "00:00",
                    "to": "23:59"
                }
            })
            
            # Additional legs
            for stop in params.additional_stops:
                slices.append({
                    "origin": stop["origin"],
                    "destination": stop["destination"],
                    "departure_date": stop["departure_date"],
                    "departure_time": {
                        "from": "00:00",
                        "to": "23:59"
                    }
                })
        
        # Search for offers
        response = await flight_client.create_offer_request(
            slices=slices,
            cabin_class=params.cabin_class,
            adult_count=params.adults,
            return_offers=True,
            supplier_timeout=15000
        )
        
        # Format the response
        formatted_response = {
            'request_id': response['request_id'],
            'offers': []
        }
        
        # Limit to top 5 offers
        for offer in list(response.get('offers', []))[:5]:
            offer_details = {
                'offer_id': offer.get('id'),
                'price': {
                    'amount': offer.get('total_amount'),
                    'currency': offer.get('total_currency')
                },
                'slices': []
            }
            
            # Only include essential slice details
            for slice in offer.get('slices', []):
                slice_details = {
                    'origin': slice['origin']['iata_code'],
                    'destination': slice['destination']['iata_code'],
                    'departure': slice.get('departing_at'),
                    'arrival': slice.get('arriving_at'),
                    'duration': slice.get('duration'),
                    'carrier': slice.get('segments', [{}])[0].get('marketing_carrier', {}).get('name')
                }
                offer_details['slices'].append(slice_details)
            
            formatted_response['offers'].append(offer_details)
        
        return json.dumps(formatted_response, indent=2)
            
    except Exception as e:
        logger.error(f"Error searching flights: {str(e)}", exc_info=True)
        raise
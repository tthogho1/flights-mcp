"""Flight search tools using Duffel API."""

import logging
from datetime import datetime
from typing import List, Literal, Dict
import json
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from . import duffel_api

# Set up logging
logger = logging.getLogger(__name__)

# Initialize FastMCP server and API client
mcp = FastMCP("find-flights-mcp")
flight_client = duffel_api.Client(logger)

class TimeRange(BaseModel):
    """Model for time range specification."""
    from_time: str = Field(..., description="Start time (HH:MM)", pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    to_time: str = Field(..., description="End time (HH:MM)", pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")

class FlightSearch(BaseModel):
    """Model for flight search parameters."""
    type: str = Field(..., description="Type of flight: 'one_way', 'round_trip', or 'multi_city'")
    origin: str = Field(..., description="Origin airport code")
    destination: str = Field(..., description="Destination airport code")
    departure_date: str = Field(..., description="Departure date (YYYY-MM-DD)")
    return_date: str | None = Field(None, description="Return date for round trips (YYYY-MM-DD)")
    departure_time: TimeRange | None = Field(None, description="Preferred departure time range")
    arrival_time: TimeRange | None = Field(None, description="Preferred arrival time range")
    cabin_class: str = Field("economy", description="Cabin class (economy, business, first)")
    adults: int = Field(1, description="Number of adult passengers")
    max_connections: int = Field(None, description="Maximum number of connections (0 for non-stop)")

class OfferDetails(BaseModel):
    """Model for getting detailed offer information."""
    offer_id: str = Field(..., description="The ID of the offer to get details for")

class FlightSegment(BaseModel):
    """Model for a single flight segment in a multi-city trip."""
    origin: str = Field(..., description="Origin airport code")
    destination: str = Field(..., description="Destination airport code") 
    departure_date: str = Field(..., description="Departure date (YYYY-MM-DD)")

class MultiCityRequest(BaseModel):
    """Model for multi-city flight search."""
    type: Literal["multi_city"]
    segments: List[FlightSegment] = Field(..., min_items=2, description="Flight segments")
    cabin_class: str = Field("economy", description="Cabin class")
    adults: int = Field(1, description="Number of adult passengers")
    max_connections: int = Field(None, description="Maximum number of connections (0 for non-stop)")
    departure_time: TimeRange | None = Field(None, description="Optional departure time range")
    arrival_time: TimeRange | None = Field(None, description="Optional arrival time range")

def _create_slice(origin: str, destination: str, date: str, 
                 departure_time: TimeRange | None = None,
                 arrival_time: TimeRange | None = None) -> Dict:
    """Helper to create a slice with time ranges."""
    slice_data = {
        "origin": origin,
        "destination": destination,
        "departure_date": date,
        "departure_time": {
            "from": "00:00",
            "to": "23:59"
        },
        "arrival_time": {
            "from": "00:00",
            "to": "23:59"
        }
    }
    
    if departure_time:
        slice_data["departure_time"] = {
            "from": departure_time.from_time,
            "to": departure_time.to_time
        }
    
    if arrival_time:
        slice_data["arrival_time"] = {
            "from": arrival_time.from_time,
            "to": arrival_time.to_time
        }
    
    return slice_data

@mcp.tool()
async def search_flights(params: FlightSearch) -> str:
    """Search for flights based on parameters."""
    try:
        slices = []
        
        # Build slices based on flight type
        if params.type == "one_way":
            slices = [_create_slice(
                params.origin, 
                params.destination, 
                params.departure_date,
                params.departure_time,
                params.arrival_time
            )]
        elif params.type == "round_trip":
            if not params.return_date:
                raise ValueError("Return date required for round-trip flights")
            slices = [
                _create_slice(
                    params.origin,
                    params.destination,
                    params.departure_date,
                    params.departure_time,
                    params.arrival_time
                ),
                _create_slice(
                    params.destination,
                    params.origin,
                    params.return_date,
                    params.departure_time,
                    params.arrival_time
                )
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
                },
                "arrival_time": {
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
                    },
                    "arrival_time": {
                        "from": "00:00",
                        "to": "23:59"
                    }
                })
        
        # Search for offers
        response = await flight_client.create_offer_request(
            slices=slices,
            cabin_class=params.cabin_class,
            adult_count=params.adults,
            max_connections=params.max_connections,
            return_offers=True,
            supplier_timeout=15000
        )
        
        # Format the response
        formatted_response = {
            'request_id': response['request_id'],
            'offers': []
        }
        
        # Get all offers (limit to 10 to manage response size)
        for offer in response.get('offers', [])[:50]:  # Keep the slice to limit offers
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
                segments = slice.get('segments', [])
                if segments:  # Check if there are any segments
                    slice_details = {
                        'origin': slice['origin']['iata_code'],
                        'destination': slice['destination']['iata_code'],
                        'departure': segments[0].get('departing_at'),  # First segment departure
                        'arrival': segments[-1].get('arriving_at'),    # Last segment arrival
                        'duration': slice.get('duration'),
                        'carrier': segments[0].get('marketing_carrier', {}).get('name'),
                        'connections': []
                    }
                    
                    # Add connection information if there are multiple segments
                    if len(segments) > 1:
                        for i in range(len(segments)-1):
                            connection = {
                                'airport': segments[i].get('destination', {}).get('iata_code'),
                                'arrival': segments[i].get('arriving_at'),
                                'departure': segments[i+1].get('departing_at'),
                                'duration': segments[i+1].get('duration')
                            }
                            slice_details['connections'].append(connection)
                    
                    offer_details['slices'].append(slice_details)
            
            formatted_response['offers'].append(offer_details)
        
        return json.dumps(formatted_response, indent=2)
            
    except Exception as e:
        logger.error(f"Error searching flights: {str(e)}", exc_info=True)
        raise

@mcp.tool()
async def get_offer_details(params: OfferDetails) -> str:
    """Get detailed information about a specific flight offer."""
    try:
        # Get detailed offer information
        response = await flight_client.get_offer(
            offer_id=params.offer_id
        )
        
        # Return the complete response
        return json.dumps(response, indent=2)
            
    except Exception as e:
        logger.error(f"Error getting offer details: {str(e)}", exc_info=True)
        raise

@mcp.tool(name="search_multi_city")
async def search_multi_city(params: MultiCityRequest) -> str:
    """Search for multi-city flights."""
    try:
        slices = []
        for segment in params.segments:
            slices.append(_create_slice(
                segment.origin,
                segment.destination,
                segment.departure_date,
                None,  # Default to full day if no time range specified
                None   # Default to full day if no time range specified
            ))

        # Search for offers
        response = await flight_client.create_offer_request(
            slices=slices,
            cabin_class=params.cabin_class,
            adult_count=params.adults,
            max_connections=params.max_connections,
            return_offers=True,
            supplier_timeout=15000
        )
        
        # Format the response
        formatted_response = {
            'request_id': response['request_id'],
            'offers': []
        }
        
        # Get all offers (limit to 10 to manage response size)
        for offer in response.get('offers', [])[:10]:  # Keep the slice to limit offers
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
                segments = slice.get('segments', [])
                if segments:  # Check if there are any segments
                    slice_details = {
                        'origin': slice['origin']['iata_code'],
                        'destination': slice['destination']['iata_code'],
                        'departure': segments[0].get('departing_at'),  # First segment departure
                        'arrival': segments[-1].get('arriving_at'),    # Last segment arrival
                        'duration': slice.get('duration'),
                        'carrier': segments[0].get('marketing_carrier', {}).get('name'),
                        'connections': []
                    }
                    
                    # Add connection information if there are multiple segments
                    if len(segments) > 1:
                        for i in range(len(segments)-1):
                            connection = {
                                'airport': segments[i].get('destination', {}).get('iata_code'),
                                'arrival': segments[i].get('arriving_at'),
                                'departure': segments[i+1].get('departing_at'),
                                'duration': segments[i+1].get('duration')
                            }
                            slice_details['connections'].append(connection)
                    
                    offer_details['slices'].append(slice_details)
            
            formatted_response['offers'].append(offer_details)
        
        return json.dumps(formatted_response, indent=2)
            
    except Exception as e:
        logger.error(f"Error searching flights: {str(e)}", exc_info=True)
        raise
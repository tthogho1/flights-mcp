"""Tests for the Duffel API client."""

import pytest
import logging
from datetime import datetime, timedelta
import os
from flights.duffel_api import Client
import json

# Set up basic logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
def client():
    """Create a Duffel API client instance for testing."""
    return Client(logger)

@pytest.fixture
def future_date():
    """Get a date 2 months in the future for testing."""
    return (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")

@pytest.mark.asyncio
async def test_api_connection(client):
    """Test basic API connectivity and authentication."""
    try:
        # Try a simple API call
        response = await client.list_offer_requests(limit=1)
        assert response is not None
        assert "data" in response
        logger.info("API connection successful")
    except Exception as e:
        logger.error(f"API connection failed: {str(e)}")
        pytest.fail(f"API connection test failed: {str(e)}")

@pytest.mark.asyncio
async def test_create_one_way_offer_request(client, future_date):
    """Test creating a basic one-way offer request."""
    slices = [{
        "origin": "LHR",
        "destination": "JFK",
        "departure_date": future_date,
        "departure_time": {
            "from": "09:45",
            "to": "17:00"
        }
    }]
    
    try:
        response = await client.create_offer_request(
            slices=slices,
            cabin_class="economy",
            adult_count=1,
            return_offers=True,
            supplier_timeout=15000
        )
        
        assert "request_id" in response
        assert "offers" in response
        assert isinstance(response["offers"], list)
        
        return response["request_id"]
        
    except Exception as e:
        logger.error(f"Request failed with headers: {client.headers}")
        pytest.fail(f"Failed to create offer request: {str(e)}")

@pytest.mark.asyncio
async def test_create_round_trip_offer_request(client, future_date):
    """Test creating a round-trip offer request."""
    logger.info("Starting round-trip offer request test")
    
    return_date = (datetime.now() + timedelta(days=67)).strftime("%Y-%m-%d")
    
    slices = [
        {
            "origin": "LHR",
            "destination": "JFK",
            "departure_date": future_date,
            "departure_time": {
                "from": "09:45",
                "to": "17:00"
            }
        },
        {
            "origin": "JFK",
            "destination": "LHR",
            "departure_date": return_date,
            "departure_time": {
                "from": "09:45",
                "to": "17:00"
            }
        }
    ]
    
    logger.info(f"Request slices: {json.dumps(slices, indent=2)}")
    
    try:
        response = await client.create_offer_request(
            slices=slices,
            cabin_class="economy",
            adult_count=1,
            return_offers=True,
            supplier_timeout=30000
        )
        
        logger.info(f"Response: {json.dumps(response, indent=2)}")
        
        assert "request_id" in response
        assert "offers" in response
        assert isinstance(response["offers"], list)
        
        # Check if we got round-trip offers
        if response["offers"]:
            assert len(response["offers"][0]["slices"]) == 2
            logger.info(f"Successfully received {len(response['offers'])} round-trip offers")
        else:
            logger.warning("No offers received in response")
            
    except Exception as e:
        logger.error(f"Request failed with headers: {client.headers}")
        logger.error(f"Full error: {str(e)}")
        pytest.fail(f"Failed to create round-trip offer request: {str(e)}")

@pytest.mark.asyncio
async def test_get_offer_request(client):
    """Test retrieving a specific offer request."""
    # First create an offer request
    request_id = await test_create_one_way_offer_request(client, 
        (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d"))
    
    try:
        response = await client.get_offer_request(request_id)
        assert "data" in response
        assert response["data"]["id"] == request_id
        
        # If there are offers, get the first offer ID for other tests
        if response["data"].get("offers"):
            return response["data"]["offers"][0]["id"]
            
    except Exception as e:
        pytest.fail(f"Failed to get offer request: {str(e)}")

@pytest.mark.asyncio
async def test_get_offer(client):
    """Test retrieving a specific offer."""
    # First get an offer ID
    offer_id = await test_get_offer_request(client)
    
    if not offer_id:
        pytest.skip("No offers available to test")
        
    try:
        response = await client.get_offer(offer_id)
        assert "data" in response
        assert response["data"]["id"] == offer_id
        
    except Exception as e:
        pytest.fail(f"Failed to get offer: {str(e)}")

@pytest.mark.asyncio
async def test_get_seat_map(client):
    """Test retrieving a seat map for an offer."""
    # First get an offer ID
    offer_id = await test_get_offer_request(client)
    
    if not offer_id:
        pytest.skip("No offers available to test")
        
    try:
        response = await client.get_seat_map(offer_id)
        assert "data" in response
        
    except Exception as e:
        pytest.fail(f"Failed to get seat map: {str(e)}")

@pytest.mark.asyncio
async def test_api_key_loaded():
    """Test that API key is loaded correctly."""
    from flights.duffel_api import API_KEY
    assert API_KEY is not None
    assert API_KEY != "your_api_key_here"
    assert API_KEY.startswith("duffel_live_")
    assert len(API_KEY) > 20 

@pytest.mark.asyncio
async def test_create_multi_city_offer_request(client, future_date):
    """Test creating a multi-city offer request."""
    logger.info("Starting multi-city offer request test")
    
    # Calculate dates for each leg of the journey
    date1 = datetime.strptime(future_date, "%Y-%m-%d")  # About 2 months from now
    date2 = date1 + timedelta(days=2)  # Shorter stay in New York
    date3 = date2 + timedelta(days=2)  # Shorter stay in Miami
    
    slices = [
        {
            # First leg: London to New York
            "origin": "LHR",
            "destination": "JFK",
            "departure_date": date1.strftime("%Y-%m-%d"),
            # Wider time window
            "departure_time": {
                "from": "00:00",
                "to": "23:59"
            }
        },
        {
            # Second leg: New York to Miami
            "origin": "JFK",
            "destination": "MIA",
            "departure_date": date2.strftime("%Y-%m-%d"),
            "departure_time": {
                "from": "00:00",
                "to": "23:59"
            }
        },
        {
            # Third leg: Miami back to London
            "origin": "MIA",
            "destination": "LHR",
            "departure_date": date3.strftime("%Y-%m-%d"),
            "departure_time": {
                "from": "00:00",
                "to": "23:59"
            }
        }
    ]
    
    logger.info(f"Request slices: {json.dumps(slices, indent=2)}")
    
    try:
        response = await client.create_offer_request(
            slices=slices,
            cabin_class="economy",
            adult_count=1,
            return_offers=True,
            supplier_timeout=60000  # Increased timeout even more
        )
        
        logger.info(f"Response: {json.dumps(response, indent=2)}")
        
        assert "request_id" in response
        assert "offers" in response
        assert isinstance(response["offers"], list)
        
        # Verify we got multi-city offers
        if response["offers"]:
            # Each offer should have 3 slices (LHR->JFK->MIA->LHR)
            assert len(response["offers"][0]["slices"]) == 3
            logger.info(f"Successfully received {len(response['offers'])} multi-city offers")
            
            # Log some details about the first offer
            offer = response["offers"][0]
            logger.info("First offer details:")
            logger.info(f"Total amount: {offer.get('total_amount')} {offer.get('total_currency')}")
            logger.info(f"Number of slices: {len(offer['slices'])}")
            for i, slice in enumerate(offer['slices'], 1):
                logger.info(f"Slice {i}: {slice['origin']['iata_code']} -> {slice['destination']['iata_code']}")
                if 'segments' in slice:
                    for seg in slice['segments']:
                        logger.info(f"  Flight: {seg.get('marketing_carrier_flight_number')} at {seg.get('departing_at')}")
        else:
            logger.warning("No offers received in response")
            # Log the request ID for debugging
            logger.warning(f"Request ID: {response.get('request_id')}")
            
            # Try to get more details about why no offers were returned
            try:
                details = await client.get_offer_request(response['request_id'])
                logger.info(f"Offer request details: {json.dumps(details, indent=2)}")
            except Exception as e:
                logger.error(f"Could not get offer request details: {str(e)}")
            
    except Exception as e:
        logger.error(f"Request failed with headers: {client.headers}")
        logger.error(f"Full error: {str(e)}")
        pytest.fail(f"Failed to create multi-city offer request: {str(e)}") 
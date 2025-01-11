"""Duffel API client."""

import logging
import os
from typing import Optional, Dict, List
from dotenv import load_dotenv
import httpx
import json
from datetime import datetime
from pathlib import Path
import asyncio
from functools import lru_cache
import hashlib

# Load environment variables from the correct path
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Configuration
API_KEY = os.getenv("DUFFEL_API_KEY_LIVE")
if not API_KEY:
    raise ValueError("DUFFEL_API_KEY_LIVE environment variable is not set")
if API_KEY == "your_api_key_here":
    raise ValueError("Please set a real API key in .env file")

class Client:
    def __init__(self, logger, timeout: float = 30.0):
        """Initialize the Duffel API client"""
        self.logger = logger
        self.timeout = timeout
        self.base_url = "https://api.duffel.com/air"
        
        # Add Accept-Encoding header and verify API key format
        self.headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Duffel-Version": "v1",
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        self.logger.info(f"API key starts with: {API_KEY[:8] if API_KEY else None}")
        self.logger.info(f"Using base URL: {self.base_url}")
        self._cache = {}

    def _cache_key(self, slices: List[Dict], cabin_class: str, adult_count: int) -> str:
        """Generate a cache key for the request."""
        key_data = {
            'slices': slices,
            'cabin_class': cabin_class,
            'adult_count': adult_count
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    async def list_offer_requests(self,
                                after: Optional[str] = None,
                                before: Optional[str] = None,
                                limit: int = 50) -> Dict:
        """List offer requests with pagination support"""
        try:
            params = {}
            if after:
                params["after"] = after
            if before:
                params["before"] = before
            if limit:
                params["limit"] = min(limit, 200)  # Max 200 per page
                
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/offer_requests",
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            error_msg = f"Error listing offer requests: {str(e)}"
            self.logger.error(error_msg)
            raise

    async def create_offer_request(self,
                                 slices: List[Dict],
                                 cabin_class: str = "economy",
                                 adult_count: int = 1,
                                 max_connections: int = None,
                                 return_offers: bool = True,
                                 supplier_timeout: int = 15000) -> Dict:
        """Create a flight offer request with caching."""
        try:
            # Build request data
            data = {
                "data": {
                    "slices": slices,
                    "cabin_class": cabin_class,
                    "passengers": [{"type": "adult"} for _ in range(adult_count)],
                }
            }

            # Add max_connections if specified
            if max_connections is not None:
                data["data"]["max_connections"] = max_connections

            # Query parameters
            params = {
                "return_offers": str(return_offers).lower(),
                "supplier_timeout": supplier_timeout
            }

            cache_key = self._cache_key(slices, cabin_class, adult_count)
            
            # Check cache first
            if cache_key in self._cache:
                cached_data = self._cache[cache_key]
                # Cache for 5 minutes
                if (datetime.now() - cached_data['timestamp']).total_seconds() < 300:
                    self.logger.info("Returning cached response")
                    return cached_data['response']
            
            # If not in cache or expired, make the API call
            response = await self._create_offer_request(
                slices, cabin_class, adult_count, 
                max_connections, return_offers, supplier_timeout
            )
            
            # Cache the response
            self._cache[cache_key] = {
                'response': response,
                'timestamp': datetime.now()
            }
            
            return response

        except Exception as e:
            error_msg = f"Error creating offer request: {str(e)}"
            self.logger.error(error_msg)
            raise

    async def _create_offer_request(self,
                                 slices: List[Dict],
                                 cabin_class: str = "economy",
                                 adult_count: int = 1,
                                 max_connections: int = 1,
                                 return_offers: bool = True,
                                 supplier_timeout: int = 15000) -> Dict:
        """Internal method for making the actual API call."""
        max_retries = 2
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                # Format passengers according to API spec
                passengers = [{"type": "adult"} for _ in range(adult_count)]
                
                # Format request data according to API spec
                request_data = {
                    "data": {
                        "slices": slices,  # API expects raw slice data
                        "passengers": passengers,
                        "cabin_class": cabin_class,
                        "max_connections": max_connections
                    }
                }

                # Query parameters
                params = {
                    "return_offers": str(return_offers).lower(),
                    "supplier_timeout": supplier_timeout
                }
                    
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                    self.logger.info(f"Creating offer request with data: {request_data}")
                    response = await client.post(
                        f"{self.base_url}/offer_requests",
                        headers=self.headers,
                        params=params,
                        json=request_data
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    request_id = data["data"]["id"]
                    offers = data["data"].get("offers", [])
                    
                    self.logger.info(f"Created offer request with ID: {request_id}")
                    self.logger.info(f"Received {len(offers)} offers")
                    
                    return {
                        "request_id": request_id,
                        "offers": offers
                    }
                    
            except httpx.ReadTimeout:
                if attempt == max_retries - 1:
                    raise
                self.logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                await asyncio.sleep(retry_delay)
                
            except Exception as e:
                error_msg = f"Error creating offer request: {str(e)}"
                self.logger.error(error_msg)
                raise

    async def get_offer_request(self, request_id: str) -> Dict:
        """Get details of a specific offer request"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/offer_requests/{request_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            self.logger.error(f"Error getting offer request {request_id}: {str(e)}")
            raise

    async def get_offer(self, offer_id: str) -> Dict:
        """Get details of a specific offer"""
        try:
            if not offer_id.startswith("off_"):
                raise ValueError("Invalid offer ID format - must start with 'off_'")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/offers/{offer_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            self.logger.error(f"Error getting offer {offer_id}: {str(e)}")
            raise

    async def get_seat_map(self, offer_id: str) -> Dict:
        """Get the seat map for a specific offer"""
        try:
            if not offer_id.startswith("off_"):
                raise ValueError("Invalid offer ID format - must start with 'off_'")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/seat_maps",
                    headers=self.headers,
                    params={"offer_id": offer_id}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            self.logger.error(f"Error getting seat map for offer {offer_id}: {str(e)}")
            raise
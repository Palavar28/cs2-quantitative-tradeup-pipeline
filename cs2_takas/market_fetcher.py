import os
import sys
import asyncio
import aiohttp
import logging
import urllib.parse
from dataclasses import dataclass
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_KEY = os.getenv("CSFLOAT_API_KEY")

# Set up basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

if not API_KEY:
    logging.critical("CRITICAL ERROR: CSFLOAT_API_KEY not found in environment variables.")
    sys.exit(1)

@dataclass
class MarketListing:
    """Data model representing a single market listing for a skin."""
    skin_name: str
    price: float
    float_value: float

class CS2MarketFetcher:
    """
    An async fetcher to retrieve CS2 market listings from the live CSFloat API.
    Handles rate-limiting and retries for HTTP 429 Too Many Requests.
    """
    def __init__(self, session: aiohttp.ClientSession, requests_per_second: int = 2, max_retries: int = 3):
        self.session = session
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(requests_per_second)
        self._delay_between_requests = 1.0 / requests_per_second if requests_per_second > 0 else 0

    async def fetch_listings(self, skin_name: str) -> List[MarketListing]:
        """
        Fetches market listings for a specific skin name from CSFloat API.
        """
        # Encode the skin name to handle spaces and special characters
        encoded_name = urllib.parse.quote(skin_name)
        url = f"https://csfloat.com/api/v1/listings?market_hash_name={encoded_name}"
        headers = {"Authorization": API_KEY}
        retries = 0
        
        while retries <= self.max_retries:
            async with self._semaphore:
                try:
                    logging.info(f"Fetching listings for {skin_name} (Attempt {retries + 1})...")
                    async with self.session.get(url, headers=headers) as response:
                        if response.status == 429:
                            logging.warning(f"Rate limited (429) on {skin_name}. Retrying in {2 ** retries}s...")
                            await asyncio.sleep(2 ** retries)
                            retries += 1
                            continue
                        elif response.status == 401:
                            logging.error(f"Unauthorized (401) on {skin_name}. Your API key is invalid or expired.")
                            return []

                        response.raise_for_status()
                        data = await response.json()
                        return self._parse_listings(skin_name, data)
                        
                except aiohttp.ClientResponseError as e:
                    logging.error(f"HTTP error for {skin_name}: {e.status} - {e.message}")
                    break
                except aiohttp.ClientError as e:
                    logging.error(f"Connection error for {skin_name}: {e}")
                    break
                finally:
                    if self._delay_between_requests > 0:
                        await asyncio.sleep(self._delay_between_requests)
                        
        logging.error(f"Failed to fetch {skin_name} after {self.max_retries} retries.")
        return []

    def _parse_listings(self, skin_name: str, data) -> List[MarketListing]:
        """Parses the CSFloat API JSON response into MarketListing objects."""
        listings = []
        
        # CSFloat API usually returns a list directly or a list under some key.
        if isinstance(data, dict):
            items = data.get("data", []) if "data" in data else []
        elif isinstance(data, list):
            items = data
        else:
            items = []

        for listing in items:
            try:
                # Convert price from cents to USD
                price_usd = float(listing.get("price", 0)) / 100.0
                
                # Extract float_value safely
                item_data = listing.get("item", {})
                float_value = item_data.get("float_value")
                
                if float_value is None:
                    continue  # Safely skip listings without a float value

                listings.append(MarketListing(
                    skin_name=skin_name,
                    price=price_usd,
                    float_value=float(float_value)
                ))
            except (KeyError, ValueError, TypeError) as e:
                logging.warning(f"Skipping invalid item in {skin_name}: {e}")
                
        return listings

    async def fetch_multiple_skins(self, skin_names: List[str]) -> Dict[str, List[MarketListing]]:
        """Fetches listings for a batch of skins concurrently."""
        tasks = [self.fetch_listings(skin) for skin in skin_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        market_data = {}
        for skin, result in zip(skin_names, results):
            if isinstance(result, Exception):
                logging.error(f"Unexpected exception fetching {skin}: {result}")
                market_data[skin] = []
            else:
                market_data[skin] = result
                
        return market_data

# ==========================================
# Main Execution
# ==========================================
async def main():
    target_skins = [
        "AK-47 | Redline (Field-Tested)"
    ]
    
    async with aiohttp.ClientSession() as session:
        fetcher = CS2MarketFetcher(session=session, requests_per_second=2, max_retries=3)
        
        logging.info("Starting live fetch...")
        results = await fetcher.fetch_multiple_skins(target_skins)
        
        print("\n" + "="*50)
        print("MARKET FETCH RESULTS (Top 3 Cheapest Listings)")
        print("="*50)
        
        for skin, listings in results.items():
            print(f"\nSkin: {skin}")
            if not listings:
                print("  No listings found or failed to fetch.")
                continue
                
            # Sort listings by price (ascending) to get the cheapest ones
            sorted_listings = sorted(listings, key=lambda x: x.price)
            top_3 = sorted_listings[:3]
            
            for i, listing in enumerate(top_3, 1):
                print(f"  {i}. Price: ${listing.price:.2f} | Float: {listing.float_value:.5f}")

if __name__ == "__main__":
    asyncio.run(main())

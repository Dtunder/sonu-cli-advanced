import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional
from .logger import setup_logger

logger = setup_logger("MarketDataInterface")

class MarketDataInterface:
    def __init__(self, cache_ttl: int = 5):
        self.cache_ttl = cache_ttl
        self.cache: Dict[str, Dict[str, Any]] = {}

        # We will use these generic endpoints as examples.
        # In a real scenario, use actual API endpoints for Binance/Bybit.
        self.binance_url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        self.bybit_url = "https://api.bybit.com/v5/market/tickers"

    async def _fetch_url(self, session: aiohttp.ClientSession, url: str, params: dict = None) -> Optional[Dict]:
        try:
            # Low latency and resilience with a strict timeout
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=2.0)) as response:
                response.raise_for_status()
                return await response.json()
        except asyncio.TimeoutError:
            logger.error(f"Timeout while fetching data from {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching data from {url}: {e}")
            return None

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Fetches the funding rate for a given symbol.
        Checks cache first, then falls back to API.
        """
        cache_key = f"funding_rate_{symbol}"
        now = time.time()

        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if now - cached_data['timestamp'] < self.cache_ttl:
                logger.info(f"Using cached funding rate for {symbol}")
                return cached_data['value']

        logger.info(f"Fetching fresh funding rate for {symbol} via API")

        async with aiohttp.ClientSession() as session:
            # Example using Binance premium index which contains lastFundingRate
            params = {"symbol": symbol}
            data = await self._fetch_url(session, self.binance_url, params=params)

            if data and 'lastFundingRate' in data:
                rate = float(data['lastFundingRate'])
                self.cache[cache_key] = {'value': rate, 'timestamp': now}
                return rate

            # If Binance fails, we could fallback to Bybit here...
            logger.warning(f"Could not retrieve funding rate for {symbol}")
            return None

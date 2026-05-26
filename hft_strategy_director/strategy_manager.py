import asyncio
import os
from .logger import setup_logger
from .market_data_interface import MarketDataInterface
from .risk_engine import RiskEngine

logger = setup_logger("StrategyManager")

class StrategyManager:
    def __init__(self, roadmap_path: str = "ROADMAP_50_TO_50K.md"):
        self.roadmap_path = roadmap_path
        self.market_data = MarketDataInterface()
        self.risk_engine = RiskEngine()
        self.roadmap_content = ""

        # Load roadmap
        self._load_roadmap()

    def _load_roadmap(self):
        if os.path.exists(self.roadmap_path):
            with open(self.roadmap_path, 'r', encoding='utf-8') as f:
                self.roadmap_content = f.read()
            logger.info(f"Loaded roadmap from {self.roadmap_path}")
        else:
            logger.warning(f"Roadmap file not found at {self.roadmap_path}. Running without specific roadmap constraints.")

    async def analyze_and_decide(self, symbol: str, current_exposure: float, current_drawdown: float) -> str:
        """
        The main loop / decision engine.
        Acts as the 'Decision-Director' generating recommendations for the SonuClient.
        """
        logger.info(f"Starting analysis for {symbol}...")

        # 1. Check risk limits (Barbell strategy)
        if not self.risk_engine.check_limits(current_exposure, current_drawdown):
            recommendation = "HALT_TRADING - Risk limits exceeded."
            logger.warning(recommendation)
            return recommendation

        # 2. Fetch market data (Funding Rates)
        funding_rate = await self.market_data.get_funding_rate(symbol)

        if funding_rate is None:
            recommendation = "HOLD - Cannot retrieve market data, waiting for next cycle."
            logger.warning(recommendation)
            return recommendation

        # 3. Decision Logic (Simple example based on funding rate and roadmap context)
        logger.info(f"Current funding rate for {symbol} is {funding_rate}")

        # In a real scenario, parsing self.roadmap_content would influence these thresholds
        if funding_rate > 0.001:
            # High positive funding rate -> Shorts are paying longs (or vice versa depending on exchange),
            # might be a signal to short.
            recommendation = f"SHORT - High funding rate ({funding_rate}) detected."
        elif funding_rate < -0.001:
            recommendation = f"LONG - Negative funding rate ({funding_rate}) detected."
        else:
            recommendation = f"HOLD - Funding rate ({funding_rate}) is neutral."

        logger.info(f"Generated recommendation: {recommendation}")
        return recommendation

    async def run_director_loop(self, symbol: str, interval: int = 10):
        """
        Continuous loop for the director.
        """
        logger.info("Starting Strategy Director Loop...")
        while True:
            # Dummy state for simulation
            dummy_exposure = 1000.0
            dummy_drawdown = 0.02

            recommendation = await self.analyze_and_decide(symbol, dummy_exposure, dummy_drawdown)
            logger.info(f"SonuClient Action: {recommendation}")

            await asyncio.sleep(interval)

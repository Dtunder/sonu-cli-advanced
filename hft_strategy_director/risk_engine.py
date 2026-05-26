from .logger import setup_logger

logger = setup_logger("RiskEngine")

class RiskEngine:
    def __init__(self, max_exposure: float = 10000.0, max_drawdown: float = 0.05):
        """
        Risk Engine to monitor Barbell Strategy limits.

        Barbell strategy involves playing it extremely safe with the majority of the portfolio
        and taking high risks with a small percentage.
        """
        self.max_exposure = max_exposure
        self.max_drawdown = max_drawdown

        # Example specific Barbell parameters
        self.safe_allocation_pct = 0.90
        self.risk_allocation_pct = 0.10

        logger.info("RiskEngine initialized with Barbell parameters.")

    def check_limits(self, current_exposure: float, current_drawdown: float) -> bool:
        """
        Check if the current state is within risk limits.
        """
        if current_exposure > self.max_exposure:
            logger.warning(f"Exposure {current_exposure} exceeds max limit {self.max_exposure}!")
            return False

        if current_drawdown > self.max_drawdown:
            logger.warning(f"Drawdown {current_drawdown} exceeds max limit {self.max_drawdown}!")
            return False

        logger.info("Risk limits are within acceptable boundaries.")
        return True

    def validate_trade_size(self, proposed_size: float, is_risky_asset: bool, total_portfolio_value: float) -> bool:
        """
        Validate if a proposed trade size fits within the Barbell allocation.
        """
        max_allowed_for_asset = (self.risk_allocation_pct if is_risky_asset else self.safe_allocation_pct) * total_portfolio_value

        if proposed_size > max_allowed_for_asset:
            logger.warning(f"Proposed size {proposed_size} exceeds allowed allocation for asset type.")
            return False

        return True

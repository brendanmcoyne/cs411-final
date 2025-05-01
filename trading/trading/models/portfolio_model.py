import logging
import os
import time
from typing import List

from trading.models.stock_model import Stocks
from trading.utils.api_utils import get_current_price
from trading.utils.logger import configure_logger

logger = logging.getLogger(__name__)
configure_logger(logger)


class PortfolioModel:
    """
    A class to manage a portfolio of stocks.

    """

    def __init__(self):
        """Initializes the PortfolioModel with an empty portfolio.

        portfolio (dict[str, int]) - A dictionary mapping keys (stock tickers) to the number of current shares owned
        The TTL (Time To Live) for song caching is set to a default value from the environment variable "TTL",
        which defaults to 60 seconds if not set.
        """
        self.portfolio: dict[str, int] = {}
        self._stock_cache: dict[int, Stocks] = {}
        self._price_cache: dict[str, float] = {}
        self._ttl: dict[int, float] = {}
        self.ttl_seconds = int(os.getenv("TTL", 60))  # Default TTL is 60 seconds


    ##################################################
    # Stock Management Functions
    ##################################################

    def calculate_portfolio_value(self) -> float:
        """Calculates the full value of the user's portfolio
        
        Returns:
            float: the full value of the user's portfolio in USD

        Raises:
            ValueError: If the portfolio is empty or there is an issue finding the stock in the database
        """
        logger.info("Reveived request to calculate portfolio value")
        self.check_if_empty()

        total = 0.0
        for ticker, quantity in self.portfolio.items():
            try:
                logger.info(f"Fetching price for {ticker}")
                stock = self._get_stock_from_cache_or_db(ticker)
                price = stock.update_stock()
                subtotal = price * quantity
                total += subtotal
                logger.info(f"{quantity} shares of {ticker} at ${price:.2f} each: ${subtotal:.2f}")
            except ValueError as e:
                logger.error(f"Failed to find price for stock {ticker}: {e}")
                raise

        logger.info(f"Successfully computed total portfolio value: ${total:.2f}")
        return total


    def _get_stock_from_cache_or_db(self, ticker: str) -> Stocks:
        """
        Retrieves a stock by ticker, using the internal cache if possible.

        This method checks whether a cached version of the stock is available
        and still valid. If not, it queries the database, updates the cache, and returns the stock.

        Args:
            ticker (str): The unique ticker of the song to retrieve.

        Returns:
            Stocks: The stock object corresponding to the given ticker.

        Raises:
            ValueError: If the stock cannot be found in the database.
        """
        now = time.time()

        if ticker in self._stock_cache and self._ttl.get(ticker, 0) > now:
            logger.debug(f"Stock {ticker} retrieved from cache")
            return self._stock_cache[ticker]

        try:
            stock = Stocks.get_stock_by_ticker(ticker)
            logger.info(f"Stock {ticker} loaded from DB")
        except ValueError as e:
            logger.error(f"Stock {ticker} not found in DB: {e}")
            raise ValueError(f"Stock {ticker} not found in database") from e

        self._stock_cache[ticker] = stock
        self._ttl[ticker] = now + self.ttl_seconds
        return stock

    def get_user_portfolio(self, user_id: int) -> dict:
        """
        Retrieves and summarizes the user's portfolio.

        Args:
            user_id (int): ID of the user

        Returns:
            dict: Portfolio summary
        """
        try:
            self.check_if_empty()

            result = []
            total_value = self.calculate_portfolio_value()

            for ticker, quantity in self.portfolio.item():
                stock = self._get_stock_from_cache_or_db(ticker)
                holding_value = quantity * stock.update_stock()

                result.append({
                    "ticker": stock.ticker,
                    "quantity": quantity,
                    "current_price": stock.current_price,
                    "total_value": holding_value
                })

            return {
                "total_value": round(total_value, 2),
                "holdings": result
            }

        except SQLAlchemyError as e:
            logger.error(f"Error retrieving portfolio: {e}")
            raise
    
    
    ##################################################
    # Stock Management Functions
    ##################################################


    def buy_stock(self, stock_symbol: str, shares: int) -> dict:
        """
        Enables users to purchase shares of a specified stock.

        Args:
            stock_symbol (str): The symbol of the stock to buy.
            shares (int): The number of shares to purchase.

        Returns:
            Dict: Transaction details including stock symbol, shares purchased, price per share,
                  total cost, and timestamp.

        Raises:
            ValueError: If the stock symbol is invalid, shares value is invalid, or the transaction fails.
        """
        logger.info(f"Attempting to buy {shares} shares of {stock_symbol}")

        stock_symbol = self.validate_stock_ticker(stock_symbol, check_in_portfolio=False)
        shares = self.validate_shares_count(shares)

        if stock_symbol in self.portfolio:
            self.portfolio[stock_symbol] += shares
        else:
            try:
                stock = self._get_stock_from_cache_or_db(stock_symbol)
            except ValueError as e:
                logger.error(f"Failed to add stock {stock_symbol}: {e}")
                raise
            self.portfolio[stock_symbol] = shares

        # Get current market price
        try:
            price_per_share = stock.update_stock()
        except ValueError as e:
            logger.error(f"Failed to buy stock {stock_symbol}: {e}")
            raise

        total_cost = price_per_share * shares

        transaction_details = {
            "transaction_type": "BUY",
            "stock_symbol": stock_symbol,
            "shares": shares,
            "price_per_share": price_per_share,
            "total_cost": total_cost,
            "timestamp": time.time()
        }

        logger.info(f"Successfully bought {shares} shares of {stock_symbol} at ${price_per_share:.2f} per share")
        return transaction_details

    def sell_stock(self, stock_symbol: str, shares: int) -> dict:
        """
        Allows users to sell shares of a stock they currently hold.

        Args:
            stock_symbol (str): The symbol of the stock to sell.
            shares (int): The number of shares to sell.

        Returns:
            Dict: Transaction details including stock symbol, shares sold, price per share,
                  total proceeds, and timestamp.

        Raises:
            ValueError: If the stock symbol is invalid, shares value is invalid,
                        the user doesn't own the stock, or owns insufficient shares.
        """
        logger.info(f"Attempting to sell {shares} shares of {stock_symbol}")

        # Check if portfolio is empty
        self.check_if_empty()
        
        stock_symbol = self.validate_stock_ticker(stock_symbol)
        shares = self.validate_shares_count(shares)

        # Check if the user owns this stock and has enough shares
        if stock_symbol not in self.portfolio:
            logger.error(f"Stock {stock_symbol} not found in portfolio")
            raise ValueError(f"You don't own any shares of {stock_symbol}")

        if self.portfolio[stock_symbol] < shares:
            logger.error(f"Insufficient shares of {stock_symbol} in portfolio")
            raise ValueError(f"You only have {self.portfolio[stock_symbol]} shares of {stock_symbol}, but attempted to sell {shares}")
        
        # Get current price
        try:
            stock = self._get_stock_from_cache_or_db(stock_symbol)
            price_per_share = stock.update_stock()
        except ValueError as e:
            logger.error(f"Failed to sell stock {stock_symbol}: {e}")
            raise
        self.portfolio[stock_symbol] = shares

        total = price_per_share * shares

        # Update portfolio
        self.portfolio[stock_symbol] -= shares
        
        # Remove stock from portfolio if no shares left
        if self.portfolio[stock_symbol] == 0:
            del self.portfolio[stock_symbol]

        transaction_details = {
            "transaction_type": "SELL",
            "stock_symbol": stock_symbol,
            "shares": shares,
            "price_per_share": price_per_share,
            "total_proceeds": total,
            "timestamp": time.time()
        }

        logger.info(f"Successfully sold {shares} shares of {stock_symbol} at ${price_per_share:.2f} per share")
        return transaction_details


    ##################################################
    # Utility Functions
    ##################################################


    ####################################################################################################
    #
    # Note: I am only testing these things once. EG I am not testing that everything rejects an empty
    # list as they all do so by calling this helper
    #
    ####################################################################################################

    def validate_stock_ticker(self, ticker: str, check_in_portfolio: bool = True) -> str:
        """
        Validates the given stock ID.

        Args:
            ticker (str): The stock ticker to validate.
            check_in_portfolio (bool, optional): If True, verifies the ticker is present in the portfolio.
                                                If False, skips that check. Defaults to True.

        Returns:
            str: The validated stock ticker.

        Raises:
            ValueError: If stock ticker is found in the portfolio (if check_in_portfolio=True),
                        or not found in the database.
        """

        if check_in_portfolio and ticker not in self.portfolio:
            logger.error(f"Stock {ticker} not found in portfolio")
            raise ValueError(f"Stock {ticker} not found in portfolio")
        try:
            stock = self._get_stock_from_cache_or_db(ticker)
        except Exception as e:
            logger.error(f"Stock {ticker} not found in database: {e}")
            raise ValueError(f"Stock {ticker} not found in database")

        

        return ticker
    
    def validate_shares_count(self, shares: int) -> int:
        """
        Validates that the number of shares is a positive integer.

        Args:
            shares: The number of shares to validate.

        Returns:
            int: The validated number of shares.

        Raises:
            ValueError: If the shares count is not a positive integer.
        """
        try:
            shares = int(shares)
            if shares <= 0:
                raise ValueError
        except (ValueError, TypeError):
            logger.error(f"Invalid number of shares: {shares}")
            raise ValueError(f"Number of shares must be a positive integer: {shares}")
            
        return shares

    def validate_track_number(self, track_number: int) -> int:
        """
        Validates the given track number, ensuring it is within the playlist's range.

        Args:
            track_number (int): The track number to validate.

        Returns:
            int: The validated track number.

        Raises:
            ValueError: If the track number is not a valid positive integer or is out of range.

        """
        try:
            track_number = int(track_number)
            if not (1 <= track_number <= self.get_playlist_length()):
                raise ValueError(f"Invalid track number: {track_number}")
        except ValueError as e:
            logger.error(f"Invalid track number: {track_number}")
            raise ValueError(f"Invalid track number: {track_number}") from e

        return track_number

    def check_if_empty(self) -> None:
        """
        Checks if the portfolio is empty and raises a ValueError if it is.

        Raises:
            ValueError: If the portfolio is empty.

        """
        if not self.portfolio:
            logger.error("Portfolio is empty")
            raise ValueError("Portfolio is empty")

import logging
import os
import requests  

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from trading.db import db  
from trading.utils.logger import configure_logger
from trading.utils.api_utils import get_current_price, is_valid_ticker


logger = logging.getLogger(__name__)
configure_logger(logger)

# Alpha Vantage API key from env
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

class Stocks(db.Model):
    """Represents a stock holding in the portfolio.

    This model maps to the 'stocks' table and stores metadata such as ticker
    and current price.

    Used in a Flask-SQLAlchemy application for stock portfolio management.
    """

    __tablename__ = "Stocks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticker = db.Column(db.String, nullable=False)
    current_price = db.Column(db.Float, nullable=False)

    def validate(self) -> None:
        """Validates the stock instance before committing to the database.

        Raises:
            ValueError: If any required fields are invalid.
        """
        if not self.ticker or not isinstance(self.ticker, str):
            raise ValueError("Ticker must be a non-empty string.")
        if not isinstance(self.current_price, (int, float)) or self.current_price <= 0:
            raise ValueError("Current price must be a positive number.")

    @classmethod
    def create_stock(cls, ticker: str, current_price: float) -> None:
        """
        Creates a new stock in the stocks table using SQLAlchemy.

        Args:
            ticker (str): Stock ticker symbol.

        Raises:
            ValueError: If validation fails or if stock with the same ticker already exists.
            SQLAlchemyError: For database-related issues.
        """
        logger.info(f"Received request to create stock: {ticker}")
        if not is_valid_ticker(ticker):
            logger.warning(f"Invalid ticker symbol: {ticker}")
            raise ValueError(f"Ticker '{ticker}' is not a valid stock symbol.")
        try:
            stock = Stocks(
                ticker=ticker.strip().upper(),
                current_price=get_current_price(ticker)
            )
            stock.validate()
        except ValueError as e:
            logger.warning(f"Validation failed: {e}")
            raise

        try:
            # Check if stock with same ticker already exists
            existing = Stocks.query.filter_by(ticker=ticker.strip().upper()).first()
            if existing:
                logger.error(f"Stock already exists: {ticker}")
                raise ValueError(f"Stock with ticker '{ticker}' already exists.")

            db.session.add(stock)
            db.session.commit()
            logger.info(f"Stock successfully added: {ticker}")

        except IntegrityError:
            logger.error(f"Stock already exists: {ticker}")
            db.session.rollback()
            raise ValueError(f"Stock with ticker '{ticker}' already exists.")

        except SQLAlchemyError as e:
            logger.error(f"Database error while creating stock: {e}")
            db.session.rollback()
            raise

    @classmethod
    def delete_stock(cls, stock_id: int) -> None:
        """
        Permanently deletes a stock from the database by ID.

        Args:
            stock_id (int): The ID of the stock to delete.

        Raises:
            ValueError: If the stock with the given ID does not exist.
            SQLAlchemyError: For any database-related issues.
        """
        logger.info(f"Received request to delete stock with ID {stock_id}")

        try:
            stock = cls.query.get(stock_id)
            if not stock:
                logger.warning(f"Attempted to delete non-existent stock with ID {stock_id}")
                raise ValueError(f"Stock with ID {stock_id} not found")

            db.session.delete(stock)
            db.session.commit()
            logger.info(f"Successfully deleted stock with ID {stock_id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error while deleting stock with ID {stock_id}: {e}")
            db.session.rollback()
            raise
    

    @classmethod
    def update_stock(cls, ticker: str) -> None:
        """
        Updates the current price of a stock to reflect the new value.

        Args:
            ticker (string): The ID of the stock to delete.

        Raises:
            ValueError: If the stock with the given ID does not exist.
            SQLAlchemyError: For any database-related issues.
        """
        logger.info(f"Received request to update stock price of stock {ticker}")
        price = get_current_price(ticker)

        try:
            stock = cls.query.filter_by(ticker=ticker.upper()).first()
            if not stock:
                logger.warning(f"Attempted to update non-existent stock {ticker}")
                raise ValueError(f"Stock with ticker: {ticker} not found")

            logger.info(f"Updating stock {ticker} price from {stock.current_price} to {price}")
            stock.current_price = price

            db.session.commit()
            logger.info(f"Successfully updated stock {ticker} to new price: {price}")

        except SQLAlchemyError as e:
            logger.error(f"Database error while updating stock {ticker}: {e}")
            db.session.rollback()
            raise

    @classmethod
    def get_stock_by_ticker(cls, ticker: str) -> "Stocks":
        """
        Retrieves a stock from the catalog by its ticker.

        Args:
            ticker (str): The ticker of the stock to retrieve.

        Returns:
            Stocks: The stock instance corresponding to the ticker.

        Raises:
            ValueError: If no stock with the given ticker is found.
            SQLAlchemyError: If a database error occurs.
        """
        logger.info(f"Attempting to retrieve stock {ticker}")

        try:
            stock = cls.query.filter_by(ticker=ticker.upper()).first()

            if not stock:
                logger.info(f"Stock {ticker} not found")
                raise ValueError(f"Stock {ticker} not found")

            logger.info(f"Successfully retrieved stock: {stock.ticker} - {stock.current_price}")
            return stock

        except SQLAlchemyError as e:
            logger.error(f"Database error while retrieving stock {ticker}: {e}")
            raise


    @classmethod
    def lookup_stock_details(ticker: str) -> dict:
        """
        Looks up details for a given stock.

        Args:
            ticker (str): Stock ticker

        Returns:
            dict: Stock details including price, history, and description
        """
    try:
        ticker = ticker.upper()

        # Current price
        current_price = get_current_price(ticker)

        # Historical data (sample using Alpha Vantage)
        hist_url = f"https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "apikey": ALPHA_VANTAGE_API_KEY,
            "outputsize": "compact"
        }
        response = requests.get(hist_url, params=params)
        data = response.json()

        if "Time Series (Daily)" not in data:
            raise ValueError(f"No historical data found for {ticker}")

        historical_prices = [
            {"date": date, "close": float(info["4. close"])}
            for date, info in sorted(data["Time Series (Daily)"].items(), reverse=True)[:30]
        ]

        # Description (sample using Alpha Vantage company overview)
        overview_url = f"https://www.alphavantage.co/query"
        params = {
            "function": "OVERVIEW",
            "symbol": ticker,
            "apikey": ALPHA_VANTAGE_API_KEY
        }
        overview_resp = requests.get(overview_url, params=params)
        overview_data = overview_resp.json()
        description = overview_data.get("Description", "Description not available")

        {
            "ticker": ticker,
            "current_price": current_price,
            "description": description,
            "historical_prices": historical_prices
        }

    except Exception as e:
        logger.error(f"Failed to look up stock details for {ticker}: {e}")
        raise

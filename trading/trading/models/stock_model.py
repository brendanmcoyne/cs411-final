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
    def get_song_by_compound_key(cls, artist: str, title: str, year: int) -> "Songs":
        """
        Retrieves a song from the catalog by its compound key (artist, title, year).

        Args:
            artist (str): The artist of the song.
            title (str): The title of the song.
            year (int): The year the song was released.

        Returns:
            Songs: The song instance matching the provided compound key.

        Raises:
            ValueError: If no matching song is found.
            SQLAlchemyError: If a database error occurs.
        """
        logger.info(f"Attempting to retrieve song with artist '{artist}', title '{title}', and year {year}")

        try:
            song = cls.query.filter_by(artist=artist.strip(), title=title.strip(), year=year).first()

            if not song:
                logger.info(f"Song with artist '{artist}', title '{title}', and year {year} not found")
                raise ValueError(f"Song with artist '{artist}', title '{title}', and year {year} not found")

            logger.info(f"Successfully retrieved song: {song.artist} - {song.title} ({song.year})")
            return song

        except SQLAlchemyError as e:
            logger.error(
                f"Database error while retrieving song by compound key "
                f"(artist '{artist}', title '{title}', year {year}): {e}"
            )
            raise

    @classmethod
    def get_all_songs(cls, sort_by_play_count: bool = False) -> list[dict]:
        """
        Retrieves all songs from the catalog as dictionaries.

        Args:
            sort_by_play_count (bool): If True, sort the songs by play count in descending order.

        Returns:
            list[dict]: A list of dictionaries representing all songs with play_count.

        Raises:
            SQLAlchemyError: If any database error occurs.
        """
        logger.info("Attempting to retrieve all songs from the catalog")

        try:
            query = cls.query
            if sort_by_play_count:
                query = query.order_by(cls.play_count.desc())

            songs = query.all()

            if not songs:
                logger.warning("The song catalog is empty.")
                return []

            results = [
                {
                    "id": song.id,
                    "artist": song.artist,
                    "title": song.title,
                    "year": song.year,
                    "genre": song.genre,
                    "duration": song.duration,
                    "play_count": song.play_count,
                }
                for song in songs
            ]

            logger.info(f"Retrieved {len(results)} songs from the catalog")
            return results

        except SQLAlchemyError as e:
            logger.error(f"Database error while retrieving all songs: {e}")
            raise

    @classmethod
    def get_random_song(cls) -> dict:
        """
        Retrieves a random song from the catalog as a dictionary.

        Returns:
            dict: A randomly selected song dictionary.
        """
        all_songs = cls.get_all_songs()

        if not all_songs:
            logger.warning("Cannot retrieve random song because the song catalog is empty.")
            raise ValueError("The song catalog is empty.")

        index = get_random(len(all_songs))
        logger.info(f"Random index selected: {index} (total songs: {len(all_songs)})")

        return all_songs[index - 1]

    def update_play_count(self) -> None:
        """
        Increments the play count of the current song instance.

        Raises:
            ValueError: If the song does not exist in the database.
            SQLAlchemyError: If any database error occurs.
        """

        logger.info(f"Attempting to update play count for song with ID {self.id}")

        try:
            song = Songs.query.get(self.id)
            if not song:
                logger.warning(f"Cannot update play count: Song with ID {self.id} not found.")
                raise ValueError(f"Song with ID {self.id} not found")

            song.play_count += 1
            db.session.commit()

            logger.info(f"Play count incremented for song with ID: {self.id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error while updating play count for song with ID {self.id}: {e}")
            db.session.rollback()
            raise

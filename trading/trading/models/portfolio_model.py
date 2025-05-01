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

    def add_stock_to_portfolio(self, ticker: str, quantity: int) -> None:
        """
        Adds quantity number of a stock to the portfolio by ticker, using the cache or database lookup.

        Args:
            ticker (string): The ticker of the stock to add to the portfolio.
            quantity (int): The number of shares of stock ticker to add to the portfolio

        Raises:
            ValueError: If the ticker is invalid.
        """

        logger.info(f"Received request to add {quantity} shares of stocke {ticker} to the portfolio")

        ticker = self.validate_stock_ticker(ticker, check_in_portfolio=False)

        if ticker in self.portfolio:
            self.portfolio[ticker] += quantity
        else:
            try:
                stock = self._get_stock_from_cache_or_db(stock)
            except ValueError as e:
                logger.error(f"Failed to add stock: {e}")
                raise
            self.portfolio[ticker] = quantity

        logger.info(f"Successfully added to portfolio: {ticker} - {quantity} shares")

    def remove_stock_from_portfolio(self, ticker: str, quantity: int) -> None:
        """Removes quantity of stock ticker from the portolio by its ticker.

        Args:
            ticker (str): The ticker of the stock to remove from the portfolio.
            quantity (int): The number of shares of stock to remove.

        Raises:
            ValueError: If the ticker is invalid, if stock is not in portfolio, or 
                there is less than quantity shares of stock in portfolio

        """
        logger.info(f"Received request to remove {quantity} shares of stock {ticker}")

        self.check_if_empty()
        ticker = self.validate_stock_ticker(ticker)

        if ticker not in self.portfolio:
            logger.warning(f"Stock {ticker} not found in the portfolio")
            raise ValueError(f"Stock {ticker} not found in the portfolio")

        if self.portfolio[ticker] < quantity:
            logger.warning(f"Tried to remove {quantity} shares of Stock {ticker} from portfolio but only found {self.portfolio[ticker]}")
            raise ValueError(f"Tried to remove {quantity} shares of Stock {ticker} from portfolio but only found {self.portfolio[ticker]}")
        elif self.portfolio[ticker] == quantity:
            del(self.portfolio[ticker])
        else:
            self.portfolio[ticker] -= quantity
        
        logger.info(f"Successfully removed {quantity} shares of stock {ticker} from the portfolio")

    def calculate_portfolio_value(self) -> float:
        """Calculates the full value of the user's portfolio
        
        Returns:
            float: the full value of the user's portfolio in USD

        Raises:
            ValueError: If the portfolio is empty
            500 error: If there is an issue retrieving current price
        """
        logger.info("Reveived request to calculate portfolio value")
        self.check_if_empty()

        total = 0.0
        for ticker, quantity in self.portfolio.items():
            try:
                logger.info(f"Fetching price for {ticker}")
                price = get_current_price(ticker)
                subtotal = price * quantity
                total += subtotal
                logger.info(f"{quantity} shares of {ticker} at ${price} each: ${subtotal}")
            except Exception as e:
                logger.warning(f"Failed to get price for {ticker}: {e}")

        logger.info(f"Successfully computed total portfolio value: ${total}")
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
    
    ##################################################
    # Stock Management Functions
    ##################################################

    def _get_stock_price_from_cache_or_market(self, stock_symbol: str) -> float:
        """
        Retrieves the current price of a stock, using the internal cache if possible.

        This method checks whether a cached price is available and still valid.
        If not, it queries the market API, updates the cache, and returns the price.

        Args:
            stock_symbol (str): The symbol of the stock to get the price for.

        Returns:
            float: The current market price of the stock.

        Raises:
            ValueError: If the stock symbol is invalid or market data cannot be retrieved.
        """
        now = time.time()
        stock_symbol = stock_symbol.upper() 

        if stock_symbol in self._price_cache and self._ttl.get(stock_symbol, 0) > now:
            logger.debug(f"Stock price for {stock_symbol} retrieved from cache")
            return self._price_cache[stock_symbol]

        try:
            price = get_current_price(stock_symbol)
            logger.info(f"Stock price for {stock_symbol}: ${price:.2f}")
        except Exception as e:
            logger.error(f"Failed to retrieve market price for {stock_symbol}: {e}")
            raise ValueError(f"Could not retrieve market price for {stock_symbol}") from e

        self._price_cache[stock_symbol] = price
        self._ttl[stock_symbol] = now + self.ttl_seconds
        return price

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

        stock_symbol = self.validate_stock_ticker(stock_symbol)
        shares = self.validate_shares_count(shares)

        # Get current market price
        try:
            price_per_share = self._get_stock_price_from_cache_or_market(stock_symbol)
        except ValueError as e:
            logger.error(f"Failed to buy stock: {e}")
            raise

        total_cost = price_per_share * shares

        # Update portfolio 
        if stock_symbol in self.portfolio:
            self.portfolio[stock_symbol] += shares
        else:
            self.portfolio[stock_symbol] = shares

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
            price_per_share = self._get_stock_price_from_cache_or_market(stock_symbol)
        except ValueError as e:
            logger.error(f"Failed to sell stock: {e}")
            raise

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


    
    def remove_song_by_track_number(self, track_number: int) -> None:
        """Removes a song from the playlist by its track number (1-indexed).

        Args:
            track_number (int): The track number of the song to remove.

        Raises:
            ValueError: If the playlist is empty or the track number is invalid.

        """
        logger.info(f"Received request to remove song at track number {track_number}")

        self.check_if_empty()
        track_number = self.validate_track_number(track_number)
        playlist_index = track_number - 1

        logger.info(f"Successfully removed song at track number {track_number}")
        del self.playlist[playlist_index]

    def clear_playlist(self) -> None:
        """Clears all songs from the playlist.

        Clears all songs from the playlist. If the playlist is already empty, logs a warning.

        """
        logger.info("Received request to clear the playlist")

        try:
            if self.check_if_empty():
                pass
        except ValueError:
            logger.warning("Clearing an empty playlist")

        self.playlist.clear()
        logger.info("Successfully cleared the playlist")


    ##################################################
    # Playlist Retrieval Functions
    ##################################################


    def get_all_songs(self) -> List[Songs]:
        """Returns a list of all songs in the playlist using cached song data.

        Returns:
            List[Song]: A list of all songs in the playlist.

        Raises:
            ValueError: If the playlist is empty.
        """
        self.check_if_empty()
        logger.info("Retrieving all songs in the playlist")
        return [self._get_song_from_cache_or_db(song_id) for song_id in self.playlist]

    def get_song_by_song_id(self, song_id: int) -> Songs:
        """Retrieves a song from the playlist by its song ID using the cache or DB.

        Args:
            song_id (int): The ID of the song to retrieve.

        Returns:
            Song: The song with the specified ID.

        Raises:
            ValueError: If the playlist is empty or the song is not found.
        """
        self.check_if_empty()
        song_id = self.validate_song_id(song_id)
        logger.info(f"Retrieving song with ID {song_id} from the playlist")
        song = self._get_song_from_cache_or_db(song_id)
        logger.info(f"Successfully retrieved song: {song.artist} - {song.title} ({song.year})")
        return song

    def get_song_by_track_number(self, track_number: int) -> Songs:
        """Retrieves a song from the playlist by its track number (1-indexed).

        Args:
            track_number (int): The track number of the song to retrieve.

        Returns:
            Song: The song at the specified track number.

        Raises:
            ValueError: If the playlist is empty or the track number is invalid.
        """
        self.check_if_empty()
        track_number = self.validate_track_number(track_number)
        playlist_index = track_number - 1

        logger.info(f"Retrieving song at track number {track_number} from playlist")
        song_id = self.playlist[playlist_index]
        song = self._get_song_from_cache_or_db(song_id)
        logger.info(f"Successfully retrieved song: {song.artist} - {song.title} ({song.year})")
        return song

    def get_current_song(self) -> Songs:
        """Returns the current song being played.

        Returns:
            Song: The currently playing song.

        Raises:
            ValueError: If the playlist is empty.
        """
        self.check_if_empty()
        logger.info("Retrieving the current song being played")
        return self.get_song_by_track_number(self.current_track_number)

    def get_playlist_length(self) -> int:
        """Returns the number of songs in the playlist.

        Returns:
            int: The total number of songs in the playlist.

        """
        length = len(self.playlist)
        logger.info(f"Retrieving playlist length: {length} songs")
        return length

    def get_playlist_duration(self) -> int:
        """
        Returns the total duration of the playlist in seconds using cached songs.

        Returns:
            int: The total duration of all songs in the playlist in seconds.
        """
        total_duration = sum(self._get_song_from_cache_or_db(song_id).duration for song_id in self.playlist)
        logger.info(f"Retrieving total playlist duration: {total_duration} seconds")
        return total_duration


    ##################################################
    # Playlist Movement Functions
    ##################################################


    def go_to_track_number(self, track_number: int) -> None:
        """Sets the current track number to the specified track number.

        Args:
            track_number (int): The track number to set as the current track.

        Raises:
            ValueError: If the playlist is empty or the track number is invalid.

        """
        self.check_if_empty()
        track_number = self.validate_track_number(track_number)
        logger.info(f"Setting current track number to {track_number}")
        self.current_track_number = track_number

    def go_to_random_track(self) -> None:
        """Sets the current track number to a randomly selected track.

        Raises:
            ValueError: If the playlist is empty.

        """
        self.check_if_empty()

        # Get a random index using the random.org API
        random_track = get_random(self.get_playlist_length())

        logger.info(f"Setting current track number to random track: {random_track}")
        self.current_track_number = random_track

    def move_song_to_beginning(self, song_id: int) -> None:
        """Moves a song to the beginning of the playlist.

        Args:
            song_id (int): The ID of the song to move.

        Raises:
            ValueError: If the playlist is empty or the song ID is invalid.

        """
        logger.info(f"Moving song with ID {song_id} to the beginning of the playlist")
        self.check_if_empty()
        song_id = self.validate_song_id(song_id)

        self.playlist.remove(song_id)
        self.playlist.insert(0, song_id)

        logger.info(f"Successfully moved song with ID {song_id} to the beginning")

    def move_song_to_end(self, song_id: int) -> None:
        """Moves a song to the end of the playlist.

        Args:
            song_id (int): The ID of the song to move.

        Raises:
            ValueError: If the playlist is empty or the song ID is invalid.

        """
        logger.info(f"Moving song with ID {song_id} to the end of the playlist")
        self.check_if_empty()
        song_id = self.validate_song_id(song_id)

        self.playlist.remove(song_id)
        self.playlist.append(song_id)

        logger.info(f"Successfully moved song with ID {song_id} to the end")

    def move_song_to_track_number(self, song_id: int, track_number: int) -> None:
        """Moves a song to a specific track number in the playlist.

        Args:
            song_id (int): The ID of the song to move.
            track_number (int): The track number to move the song to (1-indexed).

        Raises:
            ValueError: If the playlist is empty, the song ID is invalid, or the track number is out of range.

        """
        logger.info(f"Moving song with ID {song_id} to track number {track_number}")
        self.check_if_empty()
        song_id = self.validate_song_id(song_id)
        track_number = self.validate_track_number(track_number)

        playlist_index = track_number - 1

        self.playlist.remove(song_id)
        self.playlist.insert(playlist_index, song_id)

        logger.info(f"Successfully moved song with ID {song_id} to track number {track_number}")

    def swap_songs_in_playlist(self, song1_id: int, song2_id: int) -> None:
        """Swaps the positions of two songs in the playlist.

        Args:
            song1_id (int): The ID of the first song to swap.
            song2_id (int): The ID of the second song to swap.

        Raises:
            ValueError: If the playlist is empty, either song ID is invalid, or attempting to swap the same song.

        """
        logger.info(f"Swapping songs with IDs {song1_id} and {song2_id}")
        self.check_if_empty()
        song1_id = self.validate_song_id(song1_id)
        song2_id = self.validate_song_id(song2_id)

        if song1_id == song2_id:
            logger.error(f"Cannot swap a song with itself: {song1_id}")
            raise ValueError(f"Cannot swap a song with itself: {song1_id}")

        index1, index2 = self.playlist.index(song1_id), self.playlist.index(song2_id)

        self.playlist[index1], self.playlist[index2] = self.playlist[index2], self.playlist[index1]

        logger.info(f"Successfully swapped songs with IDs {song1_id} and {song2_id}")


    ##################################################
    # Playlist Playback Functions
    ##################################################


    def play_current_song(self) -> None:
        """Plays the current song and advances the playlist.

        Raises:
            ValueError: If the playlist is empty.

        """
        self.check_if_empty()
        current_song = self.get_song_by_track_number(self.current_track_number)

        logger.info(f"Playing song: {current_song.title} (ID: {current_song.id}) at track number: {self.current_track_number}")
        current_song.update_play_count()
        logger.info(f"Updated play count for song: {current_song.title} (ID: {current_song.id})")

        self.current_track_number = (self.current_track_number % self.get_playlist_length()) + 1
        logger.info(f"Advanced to track number: {self.current_track_number}")

    def play_entire_playlist(self) -> None:
        """Plays all songs in the playlist from the beginning.

        Raises:
            ValueError: If the playlist is empty.

        """
        self.check_if_empty()
        logger.info("Starting to play the entire playlist.")

        self.current_track_number = 1
        for _ in range(self.get_playlist_length()):
            self.play_current_song()

        logger.info("Finished playing the entire playlist.")

    def play_rest_of_playlist(self) -> None:
        """Plays the remaining songs in the playlist from the current track onward.

        Raises:
            ValueError: If the playlist is empty.

        """
        self.check_if_empty()
        logger.info(f"Playing the rest of the playlist from track number: {self.current_track_number}")

        for _ in range(self.get_playlist_length() - self.current_track_number + 1):
            self.play_current_song()

        logger.info("Finished playing the rest of the playlist.")

    def rewind_playlist(self) -> None:
        """Resets the playlist to the first track.

        Raises:
            ValueError: If the playlist is empty.

        """
        self.check_if_empty()
        self.current_track_number = 1
        logger.info("Rewound playlist to the first track.")


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

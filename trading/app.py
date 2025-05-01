from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, Response, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from config import ProductionConfig

from trading.db import db
from trading.models.stock_model import Stocks  # Stock model 
from trading.models.user_model import Users  # User model
from trading.models.portfolio_model import PortfolioModel
from trading.utils.logger import configure_logger
from trading.utils.api_utils import StockAPI

load_dotenv()


def create_app(config_class=ProductionConfig) -> Flask:
    """Create a Flask application with the specified configuration.

    Args:
        config_class (Config): The configuration class to use.

    Returns:
        Flask app: The configured Flask application.

    """
    app = Flask(__name__)
    configure_logger(app.logger)

    app.config.from_object(config_class)

    # Initialize database
    db.init_app(app)
    with app.app_context():
        db.create_all()

    # Initialize login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return Users.query.filter_by(username=user_id).first()

    @login_manager.unauthorized_handler
    def unauthorized():
        return make_response(jsonify({
            "status": "error",
            "message": "Authentication required"
        }), 401)

    portfolio_model = PortfolioModel()

    @app.route('/api/health', methods=['GET'])
    def healthcheck() -> Response:
        """Health check route to verify the service is running.

        Returns:
            JSON response indicating the health status of the service.

        """
        app.logger.info("Health check endpoint hit")
        return make_response(jsonify({
            'status': 'success',
            'message': 'Service is running'
        }), 200)

    ##########################################################
    #
    # User Management
    #
    #########################################################

    @app.route('/api/create-user', methods=['PUT'])
    def create_user() -> Response:
        """Register a new user account.

        Expected JSON Input:
            - username (str): The desired username.
            - password (str): The desired password.

        Returns:
            JSON response indicating the success of the user creation.

        Raises:
            400 error if the username or password is missing.
            500 error if there is an issue creating the user in the database.
        """
        try:
            data = request.get_json()
            username = data.get("username")
            password = data.get("password")

            if not username or not password:
                return make_response(jsonify({
                    "status": "error",
                    "message": "Username and password are required"
                }), 400)

            Users.create_user(username, password)
            return make_response(jsonify({
                "status": "success",
                "message": f"User '{username}' created successfully"
            }), 201)

        except ValueError as e:
            return make_response(jsonify({
                "status": "error",
                "message": str(e)
            }), 400)
        except Exception as e:
            app.logger.error(f"User creation failed: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while creating user",
                "details": str(e)
            }), 500)

    @app.route('/api/login', methods=['POST'])
    def login() -> Response:
        """Authenticate a user and log them in.

        Expected JSON Input:
            - username (str): The username of the user.
            - password (str): The password of the user.

        Returns:
            JSON response indicating the success of the login attempt.

        Raises:
            401 error if the username or password is incorrect.
        """
        try:
            data = request.get_json()
            username = data.get("username")
            password = data.get("password")

            if not username or not password:
                return make_response(jsonify({
                    "status": "error",
                    "message": "Username and password are required"
                }), 400)

            if Users.check_password(username, password):
                user = Users.query.filter_by(username=username).first()
                login_user(user)
                return make_response(jsonify({
                    "status": "success",
                    "message": f"User '{username}' logged in successfully"
                }), 200)
            else:
                return make_response(jsonify({
                    "status": "error",
                    "message": "Invalid username or password"
                }), 401)

        except ValueError as e:
            return make_response(jsonify({
                "status": "error",
                "message": str(e)
            }), 401)
        except Exception as e:
            app.logger.error(f"Login failed: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred during login",
                "details": str(e)
            }), 500)

    @app.route('/api/logout', methods=['POST'])
    @login_required
    def logout() -> Response:
        """Log out the current user.

        Returns:
            JSON response indicating the success of the logout operation.

        """
        logout_user()
        return make_response(jsonify({
            "status": "success",
            "message": "User logged out successfully"
        }), 200)

    @app.route('/api/change-password', methods=['POST'])
    @login_required
    def change_password() -> Response:
        """Change the password for the current user.

        Expected JSON Input:
            - new_password (str): The new password to set.

        Returns:
            JSON response indicating the success of the password change.

        Raises:
            400 error if the new password is not provided.
            500 error if there is an issue updating the password in the database.
        """
        try:
            data = request.get_json()
            new_password = data.get("new_password")

            if not new_password:
                return make_response(jsonify({
                    "status": "error",
                    "message": "New password is required"
                }), 400)

            username = current_user.username
            Users.update_password(username, new_password)
            return make_response(jsonify({
                "status": "success",
                "message": "Password changed successfully"
            }), 200)

        except ValueError as e:
            return make_response(jsonify({
                "status": "error",
                "message": str(e)
            }), 400)
        except Exception as e:
            app.logger.error(f"Password change failed: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while changing password",
                "details": str(e)
            }), 500)

    @app.route('/api/reset-users', methods=['DELETE'])
    def reset_users() -> Response:
        """Recreate the users table to delete all users.

        Returns:
            JSON response indicating the success of recreating the Users table.

        Raises:
            500 error if there is an issue recreating the Users table.
        """
        try:
            app.logger.info("Received request to recreate Users table")
            with app.app_context():
                Users.__table__.drop(db.engine)
                Users.__table__.create(db.engine)
            app.logger.info("Users table recreated successfully")
            return make_response(jsonify({
                "status": "success",
                "message": f"Users table recreated successfully"
            }), 200)

        except Exception as e:
            app.logger.error(f"Users table recreation failed: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while deleting users",
                "details": str(e)
            }), 500)

    ##########################################################
    #
    # Stocks
    #
    ##########################################################


    @app.route('/api/stock-price/<string:ticker>', methods=['GET'])
    @login_required
    def get_stock_price(ticker: str) -> Response:
        """Retrieve the current stock price from Alpha Vantage via RapidAPI.
        
        Returns:
            JSON response indicating success, the ticker, and the current price
        
        Raises:
            500 error if there is an unexpected error
            ValueError if there is an issue retrieving the price
        """
        try:
            app.logger.info(f"Fetching current price for {ticker}")
            price = StockAPI.get_current_price(ticker)
            return make_response(jsonify({
                "status": "success",
                "ticker": ticker.upper(),
                "current_price": price
            }), 200)
        except ValueError as e:
            app.logger.warning(f"Error fetching price for {ticker}: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": str(e)
            }), 400)
        except Exception as e:
            app.logger.error(f"Unexpected error: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "Unexpected error while fetching stock price"
            }), 500)
        

    @app.route('/api/create-stock', methods=['POST'])
    @login_required
    def create_stock() -> Response:
        """Route to create a new stock.

        Expected JSON Input:
            - ticker (str): The stock ticker

        Returns:
            JSON response indicating success or failure.

        Raises:
            500 error if there is an unexpected error
            ValueError if there is an issue removing the stock
        """
        app.logger.info("Received request to create a new stock")

        try:
            data = request.get_json()
            ticker = data.get("ticker", "").strip().upper()

            if not ticker or not isinstance(ticker, str):
                app.logger.warning("Missing or invalid ticker in request")
                return make_response(jsonify({
                    "status": "error",
                    "message": "Missing or invalid 'ticker' in request body"
                }), 400)

            Stocks.create_stock(ticker=ticker)

            app.logger.info(f"Stock '{ticker}' successfully added")
            return make_response(jsonify({
                "status": "success",
                "message": f"Stock '{ticker}' created successfully"
            }), 201)

        except ValueError as ve:
            app.logger.warning(f"Failed to create stock: {ve}")
            return make_response(jsonify({
                "status": "error",
                "message": str(ve)
            }), 400)

        except Exception as e:
            app.logger.error(f"Unexpected error during stock creation: {e}", exc_info=True)
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while creating the stock",
                "details": str(e)
            }), 500)

    @app.route('/api/delete-stock/<int:stock_id>', methods=['DELETE'])
    @login_required
    def delete_stock(stock_id: int) -> Response:
        """
        Route to delete a stock by ID.

        Path Parameter:
            - stock_id (int): The ID of the stock to delete.

        Returns:
            JSON response indicating success or failure.
        """
        try:
            app.logger.info(f"Received request to delete stock with ID {stock_id}")

            Stocks.delete_stock(stock_id)
            app.logger.info(f"Successfully deleted stock with ID {stock_id}")

            return make_response(jsonify({
                "status": "success",
                "message": f"Stock with ID {stock_id} deleted successfully"
            }), 200)

        except ValueError as ve:
            app.logger.warning(f"Stock not found: {ve}")
            return make_response(jsonify({
                "status": "error",
                "message": str(ve)
            }), 400)

        except Exception as e:
            app.logger.error(f"Failed to delete stock: {e}", exc_info=True)
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while deleting the stock",
                "details": str(e)
            }), 500)

    @app.route('/api/portfolio/buy', methods=['POST'])
    @login_required
    def buy_stock() -> Response:
        """Buy stock for the current user's portfolio.
        
        Expected JSON Input:
            - ticker (str): The stock ticker symbol
            - shares (float/int): Number of shares to buy
            
        Returns:
            JSON response with transaction details or error message
            
        Raises:
            400 error if ticker or shares are missing or invalid
            500 error if there is an unexpected error during the transaction
        """
        try:
            app.logger.info("Received request to buy stock")
            data = request.get_json()
            ticker = data.get("ticker", "").strip().upper()
            shares = data.get("shares")
            
            if not ticker or not shares:
                app.logger.warning("Missing ticker or shares in buy request")
                return make_response(jsonify({
                    "status": "error",
                    "message": "Stock ticker and shares are required"
                }), 400)
                
            try:
                shares = float(shares)
            except (ValueError, TypeError):
                return make_response(jsonify({
                    "status": "error",
                    "message": "Shares must be a valid number"
                }), 400)
                
            transaction = portfolio_model.buy_stock(
                current_user.username,
                ticker,
                shares
            )
            
            app.logger.info(f"Successfully bought {shares} shares of {ticker}")
            return make_response(jsonify({
                "status": "success",
                "transaction": transaction
            }), 200)
            
        except ValueError as ve:
            app.logger.warning(f"Buy transaction failed: {ve}")
            return make_response(jsonify({
                "status": "error",
                "message": str(ve)
            }), 400)
            
        except Exception as e:
            app.logger.error(f"Unexpected error during buy transaction: {e}", exc_info=True)
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while buying stock",
                "details": str(e)
            }), 500)

    @app.route('/api/portfolio/sell', methods=['POST'])
    @login_required
    def sell_stock() -> Response:
        """Sell stock from the current user's portfolio.
        
        Expected JSON Input:
            - ticker (str): The stock ticker symbol
            - shares (float/int): Number of shares to sell
            
        Returns:
            JSON response with transaction details or error message
            
        Raises:
            400 error if ticker or shares are missing or if user doesn't own enough shares
            500 error if there is an unexpected error during the transaction
        """
        try:
            app.logger.info("Received request to sell stock")
            data = request.get_json()
            ticker = data.get("ticker", "").strip().upper()
            shares = data.get("shares")
            
            if not ticker or not shares:
                app.logger.warning("Missing ticker or shares in sell request")
                return make_response(jsonify({
                    "status": "error",
                    "message": "Stock ticker and shares are required"
                }), 400)
                
            try:
                shares = float(shares)
            except (ValueError, TypeError):
                return make_response(jsonify({
                    "status": "error",
                    "message": "Shares must be a valid number"
                }), 400)
                
            transaction = portfolio_model.sell_stock(
                current_user.username,
                ticker,
                shares
            )
            
            app.logger.info(f"Successfully sold {shares} shares of {ticker}")
            return make_response(jsonify({
                "status": "success",
                "transaction": transaction
            }), 200)
            
        except ValueError as ve:
            app.logger.warning(f"Sell transaction failed: {ve}")
            return make_response(jsonify({
                "status": "error",
                "message": str(ve)
            }), 400)
            
        except Exception as e:
            app.logger.error(f"Unexpected error during sell transaction: {e}", exc_info=True)
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while selling stock",
                "details": str(e)
            }), 500)


    @app.route('/api/reset-songs', methods=['DELETE'])
    def reset_songs() -> Response:
        """Recreate the songs table to delete songs.

        Returns:
            JSON response indicating the success of recreating the Songs table.

        Raises:
            500 error if there is an issue recreating the Songs table.
        """
        try:
            app.logger.info("Received request to recreate Songs table")
            with app.app_context():
                Songs.__table__.drop(db.engine)
                Songs.__table__.create(db.engine)
            app.logger.info("Songs table recreated successfully")
            return make_response(jsonify({
                "status": "success",
                "message": f"Songs table recreated successfully"
            }), 200)

        except Exception as e:
            app.logger.error(f"Songs table recreation failed: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while deleting users",
                "details": str(e)
            }), 500)



    @app.route('/api/create-song', methods=['POST'])
    @login_required
    def add_song() -> Response:
        """Route to add a new song to the catalog.

        Expected JSON Input:
            - artist (str): The artist's name.
            - title (str): The song title.
            - year (int): The year the song was released.
            - genre (str): The genre of the song.
            - duration (int): The duration of the song in seconds.

        Returns:
            JSON response indicating the success of the song addition.

        Raises:
            400 error if input validation fails.
            500 error if there is an issue adding the song to the playlist.

        """
        app.logger.info("Received request to add a new song")

        try:
            data = request.get_json()

            required_fields = ["artist", "title", "year", "genre", "duration"]
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                app.logger.warning(f"Missing required fields: {missing_fields}")
                return make_response(jsonify({
                    "status": "error",
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }), 400)

            artist = data["artist"]
            title = data["title"]
            year = data["year"]
            genre = data["genre"]
            duration = data["duration"]

            if (
                not isinstance(artist, str)
                or not isinstance(title, str)
                or not isinstance(year, int)
                or not isinstance(genre, str)
                or not isinstance(duration, int)
            ):
                app.logger.warning("Invalid input data types")
                return make_response(jsonify({
                    "status": "error",
                    "message": "Invalid input types: artist/title/genre should be strings, year and duration should be integers"
                }), 400)

            app.logger.info(f"Adding song: {artist} - {title} ({year}), Genre: {genre}, Duration: {duration}s")
            Songs.create_song(artist=artist, title=title, year=year, genre=genre, duration=duration)

            app.logger.info(f"Song added successfully: {artist} - {title}")
            return make_response(jsonify({
                "status": "success",
                "message": f"Song '{title}' by {artist} added successfully"
            }), 201)

        except Exception as e:
            app.logger.error(f"Failed to add song: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while adding the song",
                "details": str(e)
            }), 500)


    @app.route('/api/delete-song/<int:song_id>', methods=['DELETE'])
    @login_required
    def delete_song(song_id: int) -> Response:
        """Route to delete a song by ID.

        Path Parameter:
            - song_id (int): The ID of the song to delete.

        Returns:
            JSON response indicating success of the operation.

        Raises:
            400 error if the song does not exist.
            500 error if there is an issue removing the song from the database.

        """
        try:
            app.logger.info(f"Received request to delete song with ID {song_id}")

            # Check if the song exists before attempting to delete
            song = Songs.get_song_by_id(song_id)
            if not song:
                app.logger.warning(f"Song with ID {song_id} not found.")
                return make_response(jsonify({
                    "status": "error",
                    "message": f"Song with ID {song_id} not found"
                }), 400)

            Songs.delete_song(song_id)
            app.logger.info(f"Successfully deleted song with ID {song_id}")

            return make_response(jsonify({
                "status": "success",
                "message": f"Song with ID {song_id} deleted successfully"
            }), 200)

        except Exception as e:
            app.logger.error(f"Failed to delete song: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while deleting the song",
                "details": str(e)
            }), 500)
        


    @app.route('/api/get-all-songs-from-catalog', methods=['GET'])
    @login_required
    def get_all_songs() -> Response:
        """Route to retrieve all songs in the catalog (non-deleted), with an option to sort by play count.

        Query Parameter:
            - sort_by_play_count (bool, optional): If true, sort songs by play count.

        Returns:
            JSON response containing the list of songs.

        Raises:
            500 error if there is an issue retrieving songs from the catalog.

        """
        try:
            # Extract query parameter for sorting by play count
            sort_by_play_count = request.args.get('sort_by_play_count', 'false').lower() == 'true'

            app.logger.info(f"Received request to retrieve all songs from catalog (sort_by_play_count={sort_by_play_count})")

            songs = Songs.get_all_songs(sort_by_play_count=sort_by_play_count)

            app.logger.info(f"Successfully retrieved {len(songs)} songs from the catalog")

            return make_response(jsonify({
                "status": "success",
                "message": "Songs retrieved successfully",
                "songs": songs
            }), 200)

        except Exception as e:
            app.logger.error(f"Failed to retrieve songs: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while retrieving songs",
                "details": str(e)
            }), 500)


    @app.route('/api/get-song-from-catalog-by-id/<int:song_id>', methods=['GET'])
    @login_required
    def get_song_by_id(song_id: int) -> Response:
        """Route to retrieve a song by its ID.

        Path Parameter:
            - song_id (int): The ID of the song.

        Returns:
            JSON response containing the song details.

        Raises:
            400 error if the song does not exist.
            500 error if there is an issue retrieving the song.

        """
        try:
            app.logger.info(f"Received request to retrieve song with ID {song_id}")

            song = Songs.get_song_by_id(song_id)
            if not song:
                app.logger.warning(f"Song with ID {song_id} not found.")
                return make_response(jsonify({
                    "status": "error",
                    "message": f"Song with ID {song_id} not found"
                }), 400)

            app.logger.info(f"Successfully retrieved song: {song.title} by {song.artist} (ID {song_id})")

            return make_response(jsonify({
                "status": "success",
                "message": "Song retrieved successfully",
                "song": song
            }), 200)

        except Exception as e:
            app.logger.error(f"Failed to retrieve song by ID: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while retrieving the song",
                "details": str(e)
            }), 500)



    ############################################################
    #
    # Portfolio Add / Remove
    #
    ############################################################


    @app.route('/api/portfolio/add', methods=['POST'])
    @login_required
    def add_stock_to_portfolio() -> Response:
        """Adds quantity shares of a stock ticker to the user's portfolio.

            Expected JSON input:
                ticker (str): the ticker of the company
                quantity (int): the number of shares to buy

            Returns:
                JSON response indicating the success of the stock addition.

            Raises:
                500 error if there is an unexpected error
                ValueError if there is an issue adding the stock
        """
        data = request.get_json()
        ticker = data.get("ticker", "").strip().upper()
        quantity = data.get("quantity")

        if not ticker or not isinstance(quantity, int) or quantity <= 0:
            return make_response(jsonify({
                "status": "error",
                "message": "Invalid input — must provide ticker and positive quantity"
            }), 400)

        try:
            portfolio_model.add_stock_to_portfolio(ticker, quantity)
            return make_response(jsonify({
                "status": "success",
                "message": f"Added {quantity} shares of {ticker} to portfolio"
            }), 200)
        except ValueError as e:
            return make_response(jsonify({
                "status": "error",
                "message": str(e)
            }), 400)
        except Exception as e:
            app.logger.error(f"Unexpected error: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "Internal server error"
            }), 500)
        
    @app.route('/api/portfolio/remove', methods=['POST'])
    @login_required
    def remove_stock_from_portfolio() -> Response:
        """Removes quantity shares of a stock ticker from the user's portfolio.

        Expected JSON input:
                ticker (str): the ticker of the company
                quantity (int): the number of shares to sell

            Returns:
                JSON response indicating the success of the stock sale.

            Raises:
                500 error if there is an unexpected error
                ValueError if there is an issue removing the stock
        """
        data = request.get_json()
        ticker = data.get("ticker", "").strip().upper()
        quantity = data.get("quantity")

        if not ticker or not isinstance(quantity, int) or quantity <= 0:
            return make_response(jsonify({
                "status": "error",
                "message": "Invalid input — must provide ticker and positive quantity"
            }), 400)

        try:
            portfolio_model.remove_stock_from_portfolio(ticker, quantity)
            return make_response(jsonify({
                "status": "success",
                "message": f"Removed {quantity} shares of {ticker} from portfolio"
            }), 200)
        except ValueError as e:
            return make_response(jsonify({
                "status": "error",
                "message": str(e)
            }), 400)
        except Exception as e:
            app.logger.error(f"Unexpected error: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "Internal server error"
            }), 500)

    @app.route('/api/clear-playlist', methods=['POST'])
    @login_required
    def clear_playlist() -> Response:
        """Route to clear all songs from the playlist.

        Returns:
            JSON response indicating success of the operation.

        Raises:
            500 error if there is an issue clearing the playlist.

        """
        try:
            app.logger.info("Received request to clear the playlist")

            playlist_model.clear_playlist()

            app.logger.info("Successfully cleared the playlist")
            return make_response(jsonify({
                "status": "success",
                "message": "Playlist cleared"
            }), 200)

        except Exception as e:
            app.logger.error(f"Failed to clear playlist: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while clearing the playlist",
                "details": str(e)
            }), 500)


    ############################################################
    #
    # Portfolio Functions
    #
    ############################################################
    @app.route('/api/portfolio/value', methods=['GET'])
    @login_required
    def get_portfolio_value() -> Response:
        """Returns the total current value of the user's portfolio.

        Returns:
            JSON response with total value or error message.

        Raises:
            500 error if there is an unexpected error
            ValueError if there is an issue removing the stock
        """
        app.logger.info("Received request for portfolio value")

        try:
            value = portfolio_model.calculate_portfolio_value()
            return make_response(jsonify({
                "status": "success",
                "portfolio_value": round(value, 2)
            }), 200)

        except ValueError as e:
            app.logger.warning(f"Portfolio error: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": str(e)
            }), 400)

        except Exception as e:
            app.logger.error(f"Unexpected error calculating portfolio value: {e}", exc_info=True)
            return make_response(jsonify({
                "status": "error",
                "message": "Internal error while calculating portfolio value",
                "details": str(e)
            }), 500)


    @app.route('/api/get-all-songs-from-playlist', methods=['GET'])
    @login_required
    def get_all_songs_from_playlist() -> Response:
        """Retrieve all songs in the playlist.

        Returns:
            JSON response containing the list of songs.

        Raises:
            500 error if there is an issue retrieving the playlist.

        """
        try:
            app.logger.info("Received request to retrieve all songs from the playlist.")

            songs = playlist_model.get_all_songs()

            app.logger.info(f"Successfully retrieved {len(songs)} songs from the playlist.")
            return make_response(jsonify({
                "status": "success",
                "songs": songs
            }), 200)

        except Exception as e:
            app.logger.error(f"Failed to retrieve songs from playlist: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while retrieving the playlist",
                "details": str(e)
            }), 500)


    @app.route('/api/get-current-song', methods=['GET'])
    @login_required
    def get_current_song() -> Response:
        """Retrieve the current song being played.

        Returns:
            JSON response containing current song details.

        Raises:
            500 error if there is an issue retrieving the current song.

        """
        try:
            app.logger.info("Received request to retrieve the current song.")

            current_song = playlist_model.get_current_song()

            app.logger.info(f"Successfully retrieved current song: {current_song.artist} - {current_song.title}.")
            return make_response(jsonify({
                "status": "success",
                "current_song": current_song
            }), 200)

        except Exception as e:
            app.logger.error(f"Failed to retrieve current song: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while retrieving the current song",
                "details": str(e)
            }), 500)


if __name__ == '__main__':
    app = create_app()
    app.logger.info("Starting Flask app...")
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        app.logger.error(f"Flask app encountered an error: {e}")
    finally:
        app.logger.info("Flask app has stopped.")
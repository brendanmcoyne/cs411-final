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

    from trading.api.stock_api import StockAPI

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
    # Playlist Add / Remove
    #
    ############################################################


    @app.route('/api/add-song-to-playlist', methods=['POST'])
    @login_required
    def add_song_to_playlist() -> Response:
        """Route to add a song to the playlist by compound key (artist, title, year).

        Expected JSON Input:
            - artist (str): The artist's name.
            - title (str): The song title.
            - year (int): The year the song was released.

        Returns:
            JSON response indicating success of the addition.

        Raises:
            400 error if required fields are missing or the song does not exist.
            500 error if there is an issue adding the song to the playlist.

        """
        try:
            app.logger.info("Received request to add song to playlist")

            data = request.get_json()
            required_fields = ["artist", "title", "year"]
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                app.logger.warning(f"Missing required fields: {missing_fields}")
                return make_response(jsonify({
                    "status": "error",
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }), 400)

            artist = data["artist"]
            title = data["title"]

            try:
                year = int(data["year"])
            except ValueError:
                app.logger.warning(f"Invalid year format: {data['year']}")
                return make_response(jsonify({
                    "status": "error",
                    "message": "Year must be a valid integer"
                }), 400)

            app.logger.info(f"Looking up song: {artist} - {title} ({year})")
            song = Songs.get_song_by_compound_key(artist, title, year)

            if not song:
                app.logger.warning(f"Song not found: {artist} - {title} ({year})")
                return make_response(jsonify({
                    "status": "error",
                    "message": f"Song '{title}' by {artist} ({year}) not found in catalog"
                }), 400)

            playlist_model.add_song_to_playlist(song)
            app.logger.info(f"Successfully added song to playlist: {artist} - {title} ({year})")

            return make_response(jsonify({
                "status": "success",
                "message": f"Song '{title}' by {artist} ({year}) added to playlist"
            }), 201)

        except Exception as e:
            app.logger.error(f"Failed to add song to playlist: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while adding the song to the playlist",
                "details": str(e)
            }), 500)


    @app.route('/api/remove-song-from-playlist', methods=['DELETE'])
    @login_required
    def remove_song_by_song_id() -> Response:
        """Route to remove a song from the playlist by compound key (artist, title, year).

        Expected JSON Input:
            - artist (str): The artist's name.
            - title (str): The song title.
            - year (int): The year the song was released.

        Returns:
            JSON response indicating success of the removal.

        Raises:
            400 error if required fields are missing or the song does not exist in the playlist.
            500 error if there is an issue removing the song.

        """
        try:
            app.logger.info("Received request to remove song from playlist")

            data = request.get_json()
            required_fields = ["artist", "title", "year"]
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                app.logger.warning(f"Missing required fields: {missing_fields}")
                return make_response(jsonify({
                    "status": "error",
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }), 400)

            artist = data["artist"]
            title = data["title"]

            try:
                year = int(data["year"])
            except ValueError:
                app.logger.warning(f"Invalid year format: {data['year']}")
                return make_response(jsonify({
                    "status": "error",
                    "message": "Year must be a valid integer"
                }), 400)

            app.logger.info(f"Looking up song to remove: {artist} - {title} ({year})")
            song = Songs.get_song_by_compound_key(artist, title, year)

            if not song:
                app.logger.warning(f"Song not found in catalog: {artist} - {title} ({year})")
                return make_response(jsonify({
                    "status": "error",
                    "message": f"Song '{title}' by {artist} ({year}) not found in catalog"
                }), 400)

            playlist_model.remove_song_by_song_id(song.id)
            app.logger.info(f"Successfully removed song from playlist: {artist} - {title} ({year})")

            return make_response(jsonify({
                "status": "success",
                "message": f"Song '{title}' by {artist} ({year}) removed from playlist"
            }), 200)

        except Exception as e:
            app.logger.error(f"Failed to remove song from playlist: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": "An internal error occurred while removing the song from the playlist",
                "details": str(e)
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
    # View Playlist
    #
    ############################################################


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
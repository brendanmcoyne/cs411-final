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


    ############################################################
    #
    # Portfolio Add / Remove
    #
    ############################################################


    @app.route('/api/portfolio/buy', methods=['POST'])
    @login_required
    def buy_stock() -> Response:
        """Buys shares of a specified stock and adds them to the user's portfolio.

        Expected JSON input:
            ticker (str): The ticker symbol of the company to buy.
            shares (int): The number of shares to purchase.

        Returns:
            JSON response containing transaction details if the purchase succeeds.

        Raises:
            400 error if the input is invalid or the purchase fails due to validation.
            500 error if there is an unexpected server-side issue.
        """
        data = request.get_json()
        ticker = data.get("ticker", "").strip().upper()
        shares = data.get("shares")

        app.logger.info(f"Received request to buy {shares} shares of {ticker}")

        # Basic validation
        if not ticker or not isinstance(shares, int) or shares <= 0:
            app.logger.warning("Invalid input: ticker must be string, shares must be positive int")
            return make_response(jsonify({
                "status": "error",
                "message": "Invalid input: must provide valid 'ticker' and positive integer 'shares'"
            }), 400)

        try:
            result = portfolio_model.buy_stock(ticker, shares)
            return make_response(jsonify({
                "status": "success",
                "message": f"Successfully bought {shares} shares of {ticker}",
                "transaction": result
            }), 200)

        except ValueError as e:
            app.logger.warning(f"Buy failed: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": str(e)
            }), 400)

        except Exception as e:
            app.logger.error(f"Unexpected error during stock purchase: {e}", exc_info=True)
            return make_response(jsonify({
                "status": "error",
                "message": "Unexpected server error during stock purchase"
            }), 500)
        
    @app.route('/api/portfolio/sell', methods=['POST'])
    @login_required
    def sell_stock() -> Response:
        """Sells shares of a specified stock from the user's portfolio.

            Expected JSON input:
                ticker (str): The ticker symbol of the company to sell.
                shares (int): The number of shares to sell.

            Returns:
                JSON response containing transaction details if the sale succeeds.

            Raises:
                400 error if the input is invalid or the user does not own the stock or has insufficient shares.
                500 error if there is an unexpected server-side issue.
        """
        data = request.get_json()
        ticker = data.get("ticker", "").strip().upper()
        shares = data.get("shares")

        app.logger.info(f"Received request to sell {shares} shares of {ticker}")

        if not ticker or not isinstance(shares, int) or shares <= 0:
            app.logger.warning("Invalid input: ticker must be string, shares must be positive int")
            return make_response(jsonify({
                "status": "error",
                "message": "Invalid input: must provide valid 'ticker' and positive integer 'shares'"
            }), 400)

        try:
            result = portfolio_model.sell_stock(ticker, shares)
            return make_response(jsonify({
                "status": "success",
                "message": f"Successfully sold {shares} shares of {ticker}",
                "transaction": result
            }), 200)

        except ValueError as e:
            app.logger.warning(f"Sell failed: {e}")
            return make_response(jsonify({
                "status": "error",
                "message": str(e)
            }), 400)

        except Exception as e:
            app.logger.error(f"Unexpected error during stock sale: {e}", exc_info=True)
            return make_response(jsonify({
                "status": "error",
                "message": "Unexpected server error during stock sale"
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
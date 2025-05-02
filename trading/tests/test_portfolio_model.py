import pytest
import time

from trading.models.portfolio_model import PortfolioModel
from trading.models.stock_model import Stocks
from trading.db import db
from sqlalchemy.exc import SQLAlchemyError

@pytest.fixture()
def portfolio_model():
    """Fixture to provide a new instance of PortfolioModel for each test."""
    return PortfolioModel()

"""Fixtures providing sample stocks for the tests."""
@pytest.fixture
def stock_apple(session):
    """Fixture for Apple stock."""
    stock = Stocks(
        ticker="AAPL",
        current_price=174.35
    )
    session.add(stock)
    session.commit()
    return stock


@pytest.fixture
def stock_google(session):
    """Fixture for Google stock."""
    stock = Stocks(
        ticker="GOOGL",
        current_price=2805.67
    )
    session.add(stock)
    session.commit()
    return stock

@pytest.fixture
def sample_portfolio(stock_apple, stock_google):
    """Fixture for a sample portfolio."""
    return [stock_apple, stock_google]

##################################################
# Buy Stock Test Cases
##################################################

def test_buy_new_stock_success(portfolio_model, stock_apple, mocker):
    """Test buying a stock not currently in the portfolio."""
    mocker.patch.object(portfolio_model, 'validate_stock_ticker', return_value="AAPL")
    mocker.patch.object(portfolio_model, 'validate_shares_count', return_value=10)
    mocker.patch.object(portfolio_model, '_get_stock_from_cache_or_db', return_value=stock_apple)
    
    mocker.patch.object(stock_apple, 'update_stock', return_value=174.35)
    
    result = portfolio_model.buy_stock("AAPL", 10)
    
    assert portfolio_model.portfolio == {"AAPL": 10}
    
    assert result["transaction_type"] == "BUY"
    assert result["stock_symbol"] == "AAPL"
    assert result["shares"] == 10
    assert result["price_per_share"] == 174.35
    assert result["total_cost"] == 174.35 * 10
    assert "timestamp" in result


def test_buy_existing_stock(portfolio_model, stock_apple, mocker):
    """Test buying more shares of a stock already in portfolio."""
    portfolio_model.portfolio = {"AAPL": 5}
    
    mocker.patch.object(portfolio_model, 'validate_stock_ticker', return_value="AAPL")
    mocker.patch.object(portfolio_model, 'validate_shares_count', return_value=5)
    mocker.patch.object(portfolio_model, '_get_stock_from_cache_or_db', return_value=stock_apple)
    
    mocker.patch.object(stock_apple, 'update_stock', return_value=180.00)
    
    result = portfolio_model.buy_stock("AAPL", 5)
    
    assert portfolio_model.portfolio["AAPL"] == 10  
    assert result["shares"] == 5
    assert result["price_per_share"] == 180.00
    assert result["total_cost"] == 900.00


def test_buy_stock_validation_error(portfolio_model, mocker):
    """Test buying stock with invalid ticker."""
    mocker.patch.object(portfolio_model, 'validate_stock_ticker', side_effect=ValueError("Invalid stock ticker"))
    
    with pytest.raises(ValueError, match="Invalid stock ticker"):
        portfolio_model.buy_stock("INVALID", 10)
    
    assert portfolio_model.portfolio == {}


def test_buy_stock_api_error(portfolio_model, stock_apple, mocker):
    """Test handling error when stock price update fails."""
    mocker.patch.object(portfolio_model, 'validate_stock_ticker', return_value="AAPL")
    mocker.patch.object(portfolio_model, 'validate_shares_count', return_value=10)
    mocker.patch.object(portfolio_model, '_get_stock_from_cache_or_db', return_value=stock_apple)
    
    mocker.patch.object(stock_apple, 'update_stock', side_effect=ValueError("API error"))
    
    with pytest.raises(ValueError, match="API error"):
        portfolio_model.buy_stock("AAPL", 10)
    
    assert portfolio_model.portfolio == {}


##################################################
# Sell Stock Test Cases
##################################################

def test_sell_stock_success(portfolio_model, stock_apple, mocker):
    """Test successfully selling shares of a stock."""
    portfolio_model.portfolio = {"AAPL": 20}
    
    mocker.patch.object(portfolio_model, 'validate_stock_ticker', return_value="AAPL")
    mocker.patch.object(portfolio_model, 'validate_shares_count', return_value=10)
    mocker.patch.object(portfolio_model, 'check_if_empty')
    mocker.patch.object(portfolio_model, '_get_stock_from_cache_or_db', return_value=stock_apple)
    
    mocker.patch.object(stock_apple, 'update_stock', return_value=190.00)
    
    result = portfolio_model.sell_stock("AAPL", 10)
    
    assert portfolio_model.portfolio["AAPL"] == 10  
    
    assert result["transaction_type"] == "SELL"
    assert result["stock_symbol"] == "AAPL"
    assert result["shares"] == 10
    assert result["price_per_share"] == 190.00
    assert result["total_proceeds"] == 190.00 * 10
    assert "timestamp" in result


def test_sell_all_shares(portfolio_model, stock_google, mocker):
    """Test selling all shares of a stock, removing it from portfolio."""
    portfolio_model.portfolio = {"GOOGL": 5}
    
    mocker.patch.object(portfolio_model, 'validate_stock_ticker', return_value="GOOGL")
    mocker.patch.object(portfolio_model, 'validate_shares_count', return_value=5)
    mocker.patch.object(portfolio_model, 'check_if_empty')
    mocker.patch.object(portfolio_model, '_get_stock_from_cache_or_db', return_value=stock_google)
    
    mocker.patch.object(stock_google, 'update_stock', return_value=2800.00)
    
    result = portfolio_model.sell_stock("GOOGL", 5)
    
    assert "GOOGL" not in portfolio_model.portfolio
    assert result["shares"] == 5
    assert result["price_per_share"] == 2800.00
    assert result["total_proceeds"] == 14000.00


def test_sell_stock_not_owned(portfolio_model, mocker):
    """Test error when trying to sell a stock not in portfolio."""
    portfolio_model.portfolio = {}
    
    mocker.patch.object(portfolio_model, 'validate_stock_ticker', return_value="TSLA")
    mocker.patch.object(portfolio_model, 'validate_shares_count', return_value=5)
    mocker.patch.object(portfolio_model, 'check_if_empty')
    
    with pytest.raises(ValueError, match="You don't own any shares of TSLA"):
        portfolio_model.sell_stock("TSLA", 5)


def test_sell_more_shares_than_owned(portfolio_model, mocker):
    """Test error when trying to sell more shares than owned."""
    portfolio_model.portfolio = {"GOOGL": 3}
    
    mocker.patch.object(portfolio_model, 'validate_stock_ticker', return_value="GOOGL")
    mocker.patch.object(portfolio_model, 'validate_shares_count', return_value=5)
    mocker.patch.object(portfolio_model, 'check_if_empty')
    
    with pytest.raises(ValueError, match="You only have 3 shares of GOOGL, but attempted to sell 5"):
        portfolio_model.sell_stock("GOOGL", 5)
    
    assert portfolio_model.portfolio["GOOGL"] == 3


def test_sell_stock_api_error(portfolio_model, stock_apple, mocker):
    """Test handling error when stock price update fails during sell."""
    portfolio_model.portfolio = {"AAPL": 10}
    
    mocker.patch.object(portfolio_model, 'validate_stock_ticker', return_value="AAPL")
    mocker.patch.object(portfolio_model, 'validate_shares_count', return_value=5)
    mocker.patch.object(portfolio_model, 'check_if_empty')
    mocker.patch.object(portfolio_model, '_get_stock_from_cache_or_db', return_value=stock_apple)
    
    mocker.patch.object(stock_apple, 'update_stock', side_effect=ValueError("API error"))
    
    with pytest.raises(ValueError, match="API error"):
        portfolio_model.sell_stock("AAPL", 5)
    
    assert portfolio_model.portfolio["AAPL"] == 10

##################################################
# Calculate Portfolio Value Test Cases
##################################################
def test_calculate_portfolio_value_valid(mocker, stock_apple, stock_google):
    """Tests that the total portfolio value is correctly calculated
    for a portfolio with two valid stocks and mocked current prices.
    """
    model = PortfolioModel()
    model.portfolio = {"AAPL": 2, "GOOGL": 1}

    # Mock stock lookup
    mocker.patch.object(model, "_get_stock_from_cache_or_db", side_effect=[stock_apple, stock_google])

    # Mock updated prices
    mocker.patch.object(stock_apple, "update_stock", return_value=174.35)
    mocker.patch.object(stock_google, "update_stock", return_value=2805.67)

    value = model.calculate_portfolio_value()
    expected = 2 * 174.35 + 1 * 2805.67
    assert value == pytest.approx(expected, 0.01)

def test_calculate_portfolio_value_with_price_update(mocker, stock_apple):
    """Tests that the total value uses the updated price from update_stock(),
    not the original stored price, when computing the portfolio value.
    """
    model = PortfolioModel()
    model.portfolio = {"AAPL": 3}

    mocker.patch.object(model, "_get_stock_from_cache_or_db", return_value=stock_apple)
    mocker.patch.object(stock_apple, "update_stock", return_value=200.0)

    value = model.calculate_portfolio_value()
    assert value == pytest.approx(600.0, 0.01)

##################################################
# Utility Function Test Cases
##################################################

def test_validate_stock_ticker_success(portfolio_model, mocker):
    """Test successful validation of an existing ticker in portfolio and DB."""
    portfolio_model.portfolio = {"AAPL": 10}
    mocker.patch.object(portfolio_model, "_get_stock_from_cache_or_db", return_value=object())

    result = portfolio_model.validate_stock_ticker("AAPL")
    assert result == "AAPL"

def test_validate_stock_ticker_not_in_portfolio(portfolio_model, mocker):
    """Test failure when ticker is missing from portfolio and check is on."""
    portfolio_model.portfolio = {}
    with pytest.raises(ValueError, match="not found in portfolio"):
        portfolio_model.validate_stock_ticker("AAPL", check_in_portfolio=True)

def test_validate_stock_ticker_invalid_db(portfolio_model, mocker):
    """Test failure when ticker is not found in the database."""
    portfolio_model.portfolio = {"AAPL": 10}
    mocker.patch.object(portfolio_model, "_get_stock_from_cache_or_db", side_effect=Exception("DB error"))

    with pytest.raises(ValueError, match="not found in database"):
        portfolio_model.validate_stock_ticker("AAPL", check_in_portfolio=True)

def test_validate_shares_count_valid(portfolio_model):
    """Test validation passes for a positive integer."""
    assert portfolio_model.validate_shares_count(5) == 5
    assert portfolio_model.validate_shares_count("3") == 3

def test_validate_shares_count_zero(portfolio_model):
    """Test validation fails for 0 shares."""
    with pytest.raises(ValueError, match="must be a positive integer"):
        portfolio_model.validate_shares_count(0)

def test_validate_shares_count_negative(portfolio_model):
    """Test validation fails for negative shares."""
    with pytest.raises(ValueError, match="must be a positive integer"):
        portfolio_model.validate_shares_count(-5)

def test_validate_shares_count_invalid_type(portfolio_model):
    """Test validation fails for non-numeric input."""
    with pytest.raises(ValueError, match="must be a positive integer"):
        portfolio_model.validate_shares_count("five")

def test_check_if_empty_raises(portfolio_model):
    """Test that ValueError is raised when portfolio is empty."""
    portfolio_model.portfolio = {}
    with pytest.raises(ValueError, match="Portfolio is empty"):
        portfolio_model.check_if_empty()

def test_check_if_empty_passes(portfolio_model):
    """Test that no exception is raised when portfolio has entries."""
    portfolio_model.portfolio = {"AAPL": 1}
    portfolio_model.check_if_empty()  

def test_get_stock_cache_hit(portfolio_model, stock_apple, mocker):
    """Test that a valid cached stock is returned without DB access."""
    portfolio_model._stock_cache["AAPL"] = stock_apple
    portfolio_model._ttl["AAPL"] = time.time() + 60  # valid TTL

    mock_get = mocker.patch("trading.models.portfolio_model.Stocks.get_stock_by_ticker")
    
    result = portfolio_model._get_stock_from_cache_or_db("AAPL")

    assert result is stock_apple
    mock_get.assert_not_called()

def test_get_stock_cache_miss_db_hit(portfolio_model, stock_apple, mocker):
    """Test that a cache miss causes a DB fetch and updates cache."""
    portfolio_model._ttl["AAPL"] = time.time() - 10
    portfolio_model._stock_cache.clear()

    mock_get = mocker.patch(
        "trading.models.portfolio_model.Stocks.get_stock_by_ticker",
        return_value=stock_apple
    )

    result = portfolio_model._get_stock_from_cache_or_db("AAPL")

    assert result is stock_apple
    assert portfolio_model._stock_cache["AAPL"] is stock_apple
    assert "AAPL" in portfolio_model._ttl
    assert portfolio_model._ttl["AAPL"] > time.time()
    mock_get.assert_called_once_with("AAPL")

def test_get_stock_cache_miss_db_miss(portfolio_model, mocker):
    """Test that if DB also fails, a ValueError is raised."""
    portfolio_model._ttl["AAPL"] = 0 
    portfolio_model._stock_cache.clear()

    mocker.patch(
        "trading.models.portfolio_model.Stocks.get_stock_by_ticker",
        side_effect=ValueError("Stock not found")
    )

    with pytest.raises(ValueError, match="not found in database"):
        portfolio_model._get_stock_from_cache_or_db("AAPL")

def test_get_stock_expired_cache(portfolio_model, stock_apple, mocker):
    """Test that if cache exists but TTL is expired, DB is re-queried."""
    portfolio_model._stock_cache["AAPL"] = stock_apple
    portfolio_model._ttl["AAPL"] = time.time() - 100  

    mock_get = mocker.patch(
        "trading.models.portfolio_model.Stocks.get_stock_by_ticker",
        return_value=stock_apple
    )

    result = portfolio_model._get_stock_from_cache_or_db("AAPL")
    assert result is stock_apple
    mock_get.assert_called_once()

##################################################
# Get User Portfolio Test Cases
##################################################

def test_get_user_portfolio_valid(portfolio_model, stock_apple, stock_google, mocker):
    """Test that get_user_portfolio returns correct summary with valid data."""
    portfolio_model.portfolio = {"AAPL": 3, "GOOGL": 2}

    # Mock methods
    mocker.patch.object(portfolio_model, "check_if_empty")
    mocker.patch.object(portfolio_model, "calculate_portfolio_value", return_value=10000.0)

    mocker.patch.object(portfolio_model, "_get_stock_from_cache_or_db", side_effect=[stock_apple, stock_google])
    mocker.patch.object(stock_apple, "update_stock", return_value=174.35)
    mocker.patch.object(stock_google, "update_stock", return_value=2805.67)

    stock_apple.current_price = 174.35
    stock_google.current_price = 2805.67

    result = portfolio_model.get_user_portfolio(user_id=1)

    assert result["total_value"] == 10000.0
    assert len(result["holdings"]) == 2

    aapl = next(item for item in result["holdings"] if item["ticker"] == "AAPL")
    googl = next(item for item in result["holdings"] if item["ticker"] == "GOOGL")

    assert aapl["quantity"] == 3
    assert aapl["current_price"] == 174.35
    assert aapl["total_value"] == 3 * 174.35

    assert googl["quantity"] == 2
    assert googl["current_price"] == 2805.67
    assert googl["total_value"] == 2 * 2805.67

def test_get_user_portfolio_empty_error(portfolio_model, mocker):
    """Test get_user_portfolio raises error when portfolio is empty."""
    portfolio_model.portfolio = {}

    mocker.patch.object(portfolio_model, "check_if_empty", side_effect=ValueError("Portfolio is empty"))

    with pytest.raises(ValueError, match="Portfolio is empty"):
        portfolio_model.get_user_portfolio(user_id=1)


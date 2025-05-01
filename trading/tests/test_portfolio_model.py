import pytest

from trading.models.portfolio_model import PortfolioModel
from trading.models.stock_model import Stocks
from trading.db import db


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


def test_sell_stock_empty_portfolio(portfolio_model, mocker):
    """Test error when trying to sell from an empty portfolio."""
    mocker.patch.object(portfolio_model, 'check_if_empty', side_effect=ValueError("Portfolio is empty"))
    
    with pytest.raises(ValueError, match="Portfolio is empty"):
        portfolio_model.sell_stock("AAPL", 5)


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

def test_calculate_portfolio_value_empty():
    """Tests that calculating the value of an empty portfolio
    correctly raises a ValueError.
    """
    model = PortfolioModel()
    model.portfolio = {}

    with pytest.raises(ValueError, match="empty"):
        model.calculate_portfolio_value()

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



import pytest

from trading.models.portfolio_model import PortfolioModel
from trading.models.stock_model import Stocks


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
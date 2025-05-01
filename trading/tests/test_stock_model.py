import pytest

from trading.models.stock_model import Stocks
from sqlalchemy.exc import SQLAlchemyError

# --- Fixtures ---

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

def test_update_stock_success(session, mocker, stock_apple):
    """Test that update_stock updates price and commits."""
    session.add(stock_apple)
    session.commit()

    mock_price = 250.00
    mocker.patch("trading.models.stock_model.get_current_price", return_value=mock_price)

    Stocks.update_stock("AAPL")

    updated = Stocks.query.filter_by(ticker="AAPL").first()
    assert updated.current_price == mock_price

def test_update_stock_not_found(mocker):
    """Test that a ValueError is raised when stock does not exist."""
    mocker.patch("trading.models.stock_model.get_current_price", return_value=300.00)

    with pytest.raises(ValueError, match="not found"):
        Stocks.update_stock("NOTREAL")

def test_update_stock_db_failure(session, mocker, stock_apple):
    """Test that a SQLAlchemyError triggers rollback and re-raises."""
    session.add(stock_apple)
    session.commit()

    mocker.patch("trading.models.stock_model.get_current_price", return_value=275.00)
    mocker.patch("trading.models.stock_model.db.session.commit", side_effect=SQLAlchemyError("DB fail"))
    rollback_mock = mocker.patch("trading.models.stock_model.db.session.rollback")

    with pytest.raises(SQLAlchemyError, match="DB fail"):
        Stocks.update_stock("AAPL")

    rollback_mock.assert_called_once()

def test_update_stock_db_failure(session, mocker, stock_apple):
    """Test that a SQLAlchemyError triggers rollback and re-raises."""
    session.add(stock_apple)
    session.commit()

    mocker.patch("trading.models.stock_model.get_current_price", return_value=275.00)
    mocker.patch("trading.models.stock_model.db.session.commit", side_effect=SQLAlchemyError("DB fail"))
    rollback_mock = mocker.patch("trading.models.stock_model.db.session.rollback")

    with pytest.raises(SQLAlchemyError, match="DB fail"):
        Stocks.update_stock("AAPL")

    rollback_mock.assert_called_once()

def test_create_stock_success(session, mocker):
    """Test successfully creating a new stock."""
    mocker.patch("trading.models.stock_model.is_valid_ticker", return_value=True)
    mocker.patch("trading.models.stock_model.get_current_price", return_value=200.00)

    Stocks.create_stock("MSFT", 200.00)
    created = session.query(Stocks).filter_by(ticker="MSFT").first()

    assert created is not None
    assert created.current_price == 200.00

def test_create_stock_invalid_ticker(mocker):
    """Test that an invalid ticker raises a ValueError."""
    mocker.patch("trading.models.stock_model.is_valid_ticker", return_value=False)

    with pytest.raises(ValueError, match="not a valid stock symbol"):
        Stocks.create_stock("FAKE", 100.00)

def test_create_stock_duplicate(session, stock_apple, mocker):
    """Test that duplicate ticker creation is rejected."""
    mocker.patch("trading.models.stock_model.is_valid_ticker", return_value=True)
    mocker.patch("trading.models.stock_model.get_current_price", return_value=174.35)

    with pytest.raises(ValueError, match="already exists"):
        Stocks.create_stock("AAPL", 174.35)

def test_create_stock_db_failure(mocker):
    """Test that a SQLAlchemyError during add triggers rollback and re-raises."""
    mocker.patch("trading.models.stock_model.is_valid_ticker", return_value=True)
    mocker.patch("trading.models.stock_model.get_current_price", return_value=150.00)
    mocker.patch("trading.models.stock_model.db.session.add")
    mocker.patch("trading.models.stock_model.db.session.commit", side_effect=SQLAlchemyError("DB error"))
    rollback_mock = mocker.patch("trading.models.stock_model.db.session.rollback")

    with pytest.raises(SQLAlchemyError, match="DB error"):
        Stocks.create_stock("NFLX", 150.00)

    rollback_mock.assert_called_once()

def test_delete_stock_success(session, stock_google):
    """Test successful deletion of a stock by ID."""
    stock_id = stock_google.id

    Stocks.delete_stock(stock_id)
    assert session.get(Stocks, stock_id) is None

def test_delete_stock_not_found():
    """Test deletion of non-existent stock raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        Stocks.delete_stock(99999)  # assuming this ID doesn’t exist

def test_delete_stock_db_failure(session, stock_apple, mocker):
    """Test that SQLAlchemyError during delete triggers rollback and re-raises."""
    mocker.patch("trading.models.stock_model.db.session.commit", side_effect=SQLAlchemyError("DB crash"))
    rollback_mock = mocker.patch("trading.models.stock_model.db.session.rollback")

    with pytest.raises(SQLAlchemyError, match="DB crash"):
        Stocks.delete_stock(stock_apple.id)

    rollback_mock.assert_called_once()

def test_lookup_stock_details_apple_success(mocker):
    """Test successful lookup of Apple stock details."""
    mock_details = {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "industry": "Technology",
        "price": 174.35
    }
    mocker.patch("trading.models.stock_model.fetch_stock_details", return_value=mock_details)

    result = Stocks.lookup_stock_details("AAPL")

    assert result["ticker"] == "AAPL"
    assert result["name"] == "Apple Inc."
    assert result["price"] == 174.35


def test_lookup_stock_details_google_success(mocker):
    """Test successful lookup of Google stock details."""
    mock_details = {
        "ticker": "GOOGL",
        "name": "Alphabet Inc.",
        "exchange": "NASDAQ",
        "industry": "Technology",
        "price": 2805.67
    }
    mocker.patch("trading.models.stock_model.fetch_stock_details", return_value=mock_details)

    result = Stocks.lookup_stock_details("GOOGL")

    assert result["ticker"] == "GOOGL"
    assert result["name"] == "Alphabet Inc."
    assert result["price"] == 2805.67


def test_lookup_stock_details_not_found(mocker):
    """Test lookup fails with invalid ticker."""
    mocker.patch("trading.models.stock_model.fetch_stock_details", return_value=None)

    with pytest.raises(ValueError, match="not found"):
        Stocks.lookup_stock_details("INVALID")


def test_lookup_stock_details_exception(mocker):
    """Test lookup raises on unexpected error."""
    mocker.patch("trading.models.stock_model.fetch_stock_details", side_effect=Exception("API error"))

    with pytest.raises(Exception, match="API error"):
        Stocks.lookup_stock_details("AAPL")



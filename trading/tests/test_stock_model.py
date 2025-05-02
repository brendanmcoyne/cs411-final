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

    stock_apple.update_stock()

    updated = Stocks.query.filter_by(ticker="AAPL").first()
    assert updated.current_price == mock_price

def test_update_stock_db_failure(session, mocker, stock_apple):
    """Test that a SQLAlchemyError triggers rollback and re-raises."""
    session.add(stock_apple)
    session.commit()

    mocker.patch("trading.models.stock_model.get_current_price", return_value=275.00)
    mocker.patch("trading.models.stock_model.db.session.commit", side_effect=SQLAlchemyError("DB fail"))
    rollback_mock = mocker.patch("trading.models.stock_model.db.session.rollback")

    with pytest.raises(SQLAlchemyError, match="DB fail"):
        stock_apple.update_stock()

    rollback_mock.assert_called_once()

def test_create_stock_success(session, mocker):
    """Test successfully creating a new stock."""
    mocker.patch("trading.models.stock_model.is_valid_ticker", return_value=True)
    mocker.patch("trading.models.stock_model.get_current_price", return_value=200.00)

    Stocks.create_stock("MSFT")
    created = session.query(Stocks).filter_by(ticker="MSFT").first()

    assert created is not None
    assert created.current_price == 200.00

def test_create_stock_invalid_ticker(mocker):
    """Test that an invalid ticker raises a ValueError."""
    mocker.patch("trading.models.stock_model.is_valid_ticker", return_value=False)

    with pytest.raises(ValueError, match="not a valid stock symbol"):
        Stocks.create_stock("FAKE")

def test_create_stock_duplicate(session, stock_apple, mocker):
    """Test that duplicate ticker creation is rejected."""
    mocker.patch("trading.models.stock_model.is_valid_ticker", return_value=True)
    mocker.patch("trading.models.stock_model.get_current_price", return_value=174.35)

    with pytest.raises(ValueError, match="already exists"):
        Stocks.create_stock("AAPL")

def test_create_stock_db_failure(mocker):
    """Test that a SQLAlchemyError during add triggers rollback and re-raises."""
    mocker.patch("trading.models.stock_model.is_valid_ticker", return_value=True)
    mocker.patch("trading.models.stock_model.get_current_price", return_value=150.00)
    mocker.patch("trading.models.stock_model.db.session.add")
    mocker.patch("trading.models.stock_model.db.session.commit", side_effect=SQLAlchemyError("DB error"))
    rollback_mock = mocker.patch("trading.models.stock_model.db.session.rollback")

    with pytest.raises(SQLAlchemyError, match="DB error"):
        Stocks.create_stock("NFLX")

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

def test_lookup_stock_details_success(mocker):
    """Test successful lookup of stock details."""
    # Patch price lookup
    mocker.patch("trading.models.stock_model.get_current_price", return_value=174.35)

    # First API call → TIME_SERIES_DAILY_ADJUSTED
    mock_hist_response = mocker.Mock()
    mock_hist_response.json.return_value = {
        "Time Series (Daily)": {
            "2024-01-02": {"4. close": "175.00"},
            "2024-01-01": {"4. close": "174.00"},
        }
    }

    # Second API call → OVERVIEW
    mock_overview_response = mocker.Mock()
    mock_overview_response.json.return_value = {
        "Description": "Apple Inc. designs and manufactures consumer electronics."
    }

    # Patch requests.get with both responses in order
    mocker.patch("trading.models.stock_model.requests.get", side_effect=[mock_hist_response, mock_overview_response])

    result = Stocks.lookup_stock_details("AAPL")

    assert result["ticker"] == "AAPL"
    assert result["current_price"] == 174.35
    assert result["description"] == "Apple Inc. designs and manufactures consumer electronics."
    assert len(result["historical_prices"]) == 2

def test_lookup_stock_details_not_found(mocker):
    """Test lookup fails with invalid ticker."""
    mocker.patch("trading.models.stock_model.get_current_price", return_value=None)

    with pytest.raises(ValueError, match="No historical data found"):
        Stocks.lookup_stock_details("INVALID")


def test_lookup_stock_details_exception(mocker):
    """Test lookup raises on unexpected error."""
    mocker.patch("trading.models.stock_model.get_current_price", side_effect=Exception("API error"))

    with pytest.raises(Exception, match="API error"):
        Stocks.lookup_stock_details("AAPL")



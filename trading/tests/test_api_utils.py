import pytest
import requests
from trading.utils.api_utils import get_current_price, is_valid_ticker

VALID_TICKER = "AAPL"
INVALID_TICKER = "NOTREAL"
MOCK_PRICE = 123.45


@pytest.fixture
def mock_get_price(mocker):
    """Mocks get_current_price to return a fixed value."""
    return mocker.patch("app.get_current_price", return_value=MOCK_PRICE)


def test_get_stock_price_success(client, mock_get_price):
    """Test /api/stock-price/<ticker> returns the correct mocked price."""
    ticker = "AAPL"
    response = client.get(f"/api/stock-price/{ticker}")
    json_data = response.get_json()

    assert response.status_code == 200
    assert json_data["status"] == "success"
    assert json_data["ticker"] == ticker
    assert json_data["current_price"] == MOCK_PRICE
    mock_get_price.assert_called_once_with(ticker)


def test_is_valid_ticker_success(mocker):
    """Test that is_valid_ticker returns True for a valid ticker."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "bestMatches": [
            {"1. symbol": "AAPL"}
        ]
    }
    mock_response.raise_for_status = mocker.Mock()
    mocker.patch("trading.utils.api_utils.requests.get", return_value=mock_response)

    assert is_valid_ticker(VALID_TICKER) is True


def test_is_valid_ticker_no_matches(mocker):
    """Test that is_valid_ticker returns False when no matches are found."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"bestMatches": []}
    mock_response.raise_for_status = mocker.Mock()
    mocker.patch("trading.utils.api_utils.requests.get", return_value=mock_response)

    assert is_valid_ticker(INVALID_TICKER) is False


def test_is_valid_ticker_request_exception(mocker):
    """Test that is_valid_ticker returns False when an exception is raised."""
    mocker.patch(
        "trading.utils.api_utils.requests.get",
        side_effect=requests.exceptions.RequestException("API error")
    )

    assert is_valid_ticker("ERROR") is False

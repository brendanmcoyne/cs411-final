import pytest
from flask import Flask
from trading.utils.api_utils import get_current_price, is_valid_ticker
from app import create_app
from trading.db import db
import requests

VALID_TICKER = "AAPL"
INVALID_TICKER = "NOTREAL"

MOCK_PRICE = 123.45

class TestingConfig:
    TESTING = True
    LOGIN_DISABLED = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

@pytest.fixture
def app():
    app = create_app(config_class=TestingConfig)

    with app.app_context():
        db.create_all()

    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def mock_get_price(mocker):
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
    """Test whether it works for a valid ticker."""
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
    """Test for when there is no valid symbol found."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"bestMatches": []}
    mock_response.raise_for_status = mocker.Mock()
    mocker.patch("trading.utils.api_utils.requests.get", return_value=mock_response)

    assert is_valid_ticker(INVALID_TICKER) is False

def test_is_valid_ticker_request_exception(mocker):
    """Test whether it correctly raises an exception."""
    mocker.patch("trading.utils.api_utils.requests.get", side_effect=requests.exceptions.RequestException("API error"))

    assert is_valid_ticker("ERROR") is False
import pytest
from flask import Flask
from trading.utils.api_utils import StockAPI
from app import create_app  

MOCK_PRICE = 123.45


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["LOGIN_DISABLED"] = True 
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_get_price(mocker):
    return mocker.patch.object(StockAPI, "get_current_price", return_value=MOCK_PRICE)


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

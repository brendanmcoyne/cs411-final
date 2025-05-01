import pytest

from app import create_app
from config import TestConfig
from trading.db import db

@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["LOGIN_DISABLED"] = True

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    with app.app_context():
        db.create_all()

    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def session(app):
    with app.app_context():
        yield db.session
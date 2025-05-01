import pytest

from app import create_app
from config import TestConfig
from trading.db import db

@pytest.fixture(scope="session")
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def session(app):
    """Provides a test database session scoped to a test function."""
    yield db.session
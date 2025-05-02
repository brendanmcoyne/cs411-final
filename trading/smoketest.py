import requests
import time

def run_smoketest():
    base_url = "http://localhost:5000/api"
    username = "testuser"
    password = "testpass"

    # Valid tickers to use in testing
    ticker1 = "AAPL"
    ticker2 = "GOOGL"

    # Health check
    health_response = requests.get(f"{base_url}/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "success"
    print("✅ Health check passed")

    # Reset users
    reset_users_response = requests.delete(f"{base_url}/reset-users")
    assert reset_users_response.status_code == 200
    assert reset_users_response.json()["status"] == "success"
    print("✅ Reset users successful")

    # Create user
    create_user_response = requests.put(f"{base_url}/create-user", json={
        "username": username,
        "password": password
    })
    assert create_user_response.status_code == 201
    assert create_user_response.json()["status"] == "success"
    print("✅ User creation successful")

    session = requests.Session()

    # Login
    login_response = session.post(f"{base_url}/login", json={
        "username": username,
        "password": password
    })
    assert login_response.status_code == 200
    assert login_response.json()["status"] == "success"
    print("✅ Login successful")

    # Change password
    change_password_resp = session.post(f"{base_url}/change-password", json={
        "new_password": "newpass123"
    })
    assert change_password_resp.status_code == 200
    assert change_password_resp.json()["status"] == "success"
    print("✅ Password change successful")

    # Login with new password
    relogin_response = session.post(f"{base_url}/login", json={
        "username": username,
        "password": "newpass123"
    })
    assert relogin_response.status_code == 200
    assert relogin_response.json()["status"] == "success"
    print("✅ Login with new password successful")

    # Create real stocks
    for ticker in [ticker1, ticker2]:
        create_stock_response = session.post(f"{base_url}/create-stock", json={"ticker": ticker})
        assert create_stock_response.status_code == 201, f"[ERROR] {create_stock_response.text}"
        assert create_stock_response.json()["status"] == "success"
        print(f"✅ Created stock {ticker} successfully")
    time.sleep(60)
    # Buy stock
    buy_response = session.post(f"{base_url}/portfolio/buy", json={
        "ticker": ticker1,
        "shares": 3
    })
    assert buy_response.status_code == 200, f"[ERROR] Buy failed: {buy_response.text}"
    assert buy_response.json()["status"] == "success"
    print("✅ Buy stock successful")

    # Sell stock
    sell_response = session.post(f"{base_url}/portfolio/sell", json={
        "ticker": ticker1,
        "shares": 1
    })

    assert sell_response.status_code == 200, f"[ERROR] Sell failed: {sell_response.text}"
    assert sell_response.json()["status"] == "success"
    print("✅ Sell stock successful")

    # Portfolio value
    value_response = session.get(f"{base_url}/portfolio/value")
    assert value_response.status_code == 200
    assert value_response.json()["status"] == "success"
    print("✅ Portfolio value retrieval successful")
    time.sleep(60)
    # Portfolio details
    details_response = session.get(f"{base_url}/portfolio/details")
    assert details_response.status_code == 200
    assert details_response.json()["status"] == "success"
    print("✅ Portfolio details retrieval successful")

    # Logout
    logout_response = session.post(f"{base_url}/logout")
    assert logout_response.status_code == 200
    assert logout_response.json()["status"] == "success"
    print("✅ Logout successful")

    # Confirm API protects from actions when logged out
    failed_buy_response = session.post(f"{base_url}/portfolio/buy", json={
        "ticker": ticker2,
        "shares": 1
    })
    assert failed_buy_response.status_code == 401
    assert failed_buy_response.json()["status"] == "error"
    print("✅ Unauthorized buy blocked as expected")


if __name__ == "__main__":
    run_smoketest()

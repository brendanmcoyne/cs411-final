# Trading App API

## Overview
This Flask-based trading application allows users to register, log in, and manage a virtual stock portfolio. Users can add stocks using ticker symbols, fetch real-time prices with the Alpha Vantage API, buy and sell shares, and calculate the total value of their holdings. Flask-Login is used for session management, and SQLAlchemy handles database interactions.

---

### Route: `/api/health`
- **Request Type**: GET  
- **Purpose**: Confirms that the service is running.  
- **Response Format**: JSON  
  - Content:  
    ```json
    { "status": "success", "message": "Service is running" }
    ```

---

### Route: `/api/create-user`
- **Request Type**: PUT  
- **Purpose**: Creates a new user account.  
- **Request Body**:  
  - `username` (String): Desired username.  
  - `password` (String): Desired password.  
- **Response Format**: JSON  
  - Content:  
    ```json
    { "status": "success", "message": "User 'username' created successfully" }
    ```  
- **Example Request**:  
    ```json
    { "username": "newuser", "password": "secure123" }
    ```  
- **Example Response**:  
    ```json
    { "status": "success", "message": "User 'newuser' created successfully" }
    ```

---

### Route: `/api/login`
- **Request Type**: POST  
- **Purpose**: Logs in a registered user.  
- **Request Body**:  
  - `username` (String)  
  - `password` (String)  
- **Response Format**: JSON  
  - Content:  
    ```json
    { "status": "success", "message": "User 'username' logged in successfully" }
    ```  
- **Example Request**:  
    ```json
    { "username": "newuser", "password": "secure123" }
    ```

---

### Route: `/api/logout`
- **Request Type**: POST  
- **Purpose**: Logs out the current user.  
- **Response Format**: JSON  
  - Content:  
    ```json
    { "status": "success", "message": "User logged out successfully" }
    ```

---

### Route: `/api/change-password`
- **Request Type**: POST  
- **Purpose**: Changes the password for the current user.  
- **Request Body**:  
  - `new_password` (String)  
- **Response Format**: JSON  
  - Content:  
    ```json
    { "status": "success", "message": "Password changed successfully" }
    ```

---

### Route: `/api/reset-users`
- **Request Type**: DELETE  
- **Purpose**: Deletes all users and recreates the users table.  
- **Response Format**: JSON  
  - Content:  
    ```json
    { "status": "success", "message": "Users table recreated successfully" }
    ```

---

### Route: `/api/stock-price/<ticker>`
- **Request Type**: GET  
- **Purpose**: Retrieves the current stock price from the API.  
- **Response Format**: JSON  
  - Content:  
    ```json
    { "status": "success", "ticker": "AAPL", "current_price": 174.35 }
    ```

---

### Route: `/api/stock-details/<ticker>`
- **Request Type**: GET  
- **Purpose**: Retrieves detailed information about a specific stock, including current price, description, and historical data.  
- **Request Parameter**:  
  - `ticker` (Path String): The stock ticker symbol to look up  
- **Response Format**: JSON  
  - Content:  
    ```json
    {
      "status": "success",
      "stock_details": {
        "ticker": "AAPL",
        "price": 172.55,
        "description": "Apple Inc. designs and sells consumer electronics...",
        "history": [
          { "date": "2024-04-29", "close": 169.30 },
          { "date": "2024-04-30", "close": 171.50 }
        ]
      }
    }
    ```

---

### Route: `/api/create-stock`
- **Request Type**: POST  
- **Purpose**: Adds a new stock to the database.  
- **Request Body**:  
  - `ticker` (String)  
- **Response Format**: JSON  
  - Content:  
    ```json
    { "status": "success", "message": "Stock 'AAPL' created successfully" }
    ```  
- **Example Request**:  
    ```json
    { "ticker": "AAPL" }
    ```

---

### Route: `/api/delete-stock/<stock_id>`
- **Request Type**: DELETE  
- **Purpose**: Deletes a stock by its ID.  
- **Response Format**: JSON  
  - Content:  
    ```json
    { "status": "success", "message": "Stock with ID 1 deleted successfully" }
    ```

---

### Route: `/api/portfolio/buy`
- **Request Type**: POST  
- **Purpose**: Buys a specified number of shares for the user.  
- **Request Body**:  
  - `ticker` (String)  
  - `shares` (Float or Integer)  
- **Response Format**: JSON  
  - Content:  
    ```json
    {
      "status": "success",
      "transaction": {
        "transaction_type": "BUY",
        "stock_symbol": "AAPL",
        "shares": 5,
        "price_per_share": 174.35,
        "total_cost": 871.75,
        "timestamp": 1714587812.785
      }
    }
    ```

---

### Route: `/api/portfolio/sell`
- **Request Type**: POST  
- **Purpose**: Sells a specified number of shares from the user’s portfolio.  
- **Request Body**:  
  - `ticker` (String)  
  - `shares` (Float or Integer)  
- **Response Format**: JSON  
  - Content:  
    ```json
    {
      "status": "success",
      "transaction": {
        "transaction_type": "SELL",
        "stock_symbol": "AAPL",
        "shares": 3,
        "price_per_share": 174.35,
        "total_proceeds": 523.05,
        "timestamp": 1714587900.441
      }
    }
    ```

---

### Route: `/api/portfolio/value`
- **Request Type**: GET  
- **Purpose**: Returns the total value of the user’s portfolio.  
- **Response Format**: JSON  
  - Content:  
    ```json
    { "status": "success", "portfolio_value": 2167.45 }
    ```

### Route: `/api/portfolio/details`
- **Request Type**: GET  
- **Purpose**: Retrieves a detailed breakdown of the current user’s portfolio, including stock holdings and their values.  
- **Response Format**: JSON  
  - Content:  
    ```json
    {
      "status": "success",
      "portfolio": {
        "AAPL": {
          "shares": 5,
          "price": 172.55,
          "value": 862.75
        },
        "GOOGL": {
          "shares": 2,
          "price": 2805.67,
          "value": 5611.34
        }
      }
    }
    ```
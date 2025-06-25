
# finrobot/data_source/indian_spec.py
import os
import inspect

DEBUG_LOG_PATH = "report/debug_log.txt"

def log_debug(message: str):
    os.makedirs("report", exist_ok=True)
    func = inspect.currentframe().f_back.f_code.co_name
    with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{func}] {message}\n")

import socket
import requests
from functools import wraps
from typing import Annotated, Optional, Dict

# ----------------------------
# ✅ Enforce IPv4 resolution
# ----------------------------
_original_getaddrinfo = socket.getaddrinfo
def force_ipv4(*args, **kwargs):
    return [info for info in _original_getaddrinfo(*args, **kwargs) if info[0] == socket.AF_INET]
socket.getaddrinfo = force_ipv4

# ----------------------------
# ✅ Configuration
# ----------------------------
API_BASE_URL = "https://stock.indianapi.in"
API_KEY = os.getenv("INDIAN_MARKET_API_KEY", "sk-live-E0WDmXyFSKg6jJDwbkkJdvUwO7gql825EBxqIc8W")  # Replace if needed



# ----------------------------
# ✅ Decorator for injecting headers
# ----------------------------
def init_indian_api(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not API_KEY:
            raise EnvironmentError("❌ API key is not set. Please set INDIAN_MARKET_API_KEY.")
        headers = {"x-api-key": API_KEY}
        print(f"🔗 Indian Market API initialized for: {func.__name__}")
        return func(*args, headers=headers, **kwargs)
    return wrapper

# ----------------------------
# ✅ Utility class
# ----------------------------
class IndianMarketUtils:

    @staticmethod
    @init_indian_api
    def get_stock_details(name: Annotated[str, "Stock Name"], headers: Optional[Dict[str, str]] = None):
        url = f"{API_BASE_URL}/stock?name={name}"
        print(f"🔍 Requesting: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    @staticmethod
    @init_indian_api
    def get_financial_statement(stock_name: Annotated[str, "Stock Name"],
                                stats: Annotated[str, "Statement type (e.g., income, balance)"], headers: Optional[Dict[str, str]] = None):
        url = f"{API_BASE_URL}/statement?stock_name={stock_name}&stats={stats}"
        print(f"🔍 Requesting: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    @staticmethod
    @init_indian_api
    def get_historical_data(stock_name: Annotated[str, "Stock Name"],
                            period: Annotated[str, "Period (1m, 1yr, max)"],
                            filter_type: Annotated[str, "Filter type (price, pe, etc.)"], headers: Optional[Dict[str, str]] = None):
        url = f"{API_BASE_URL}/historical_data?stock_name={stock_name}&period={period}&filter={filter_type}"
        print(f"🔍 Requesting: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    @staticmethod
    @init_indian_api
    def get_recent_announcements(stock_name: Annotated[str, "Stock Name"], headers: Optional[Dict[str, str]] = None):
        url = f"{API_BASE_URL}/recent_announcements?stock_name={stock_name}"
        print(f"🔍 Requesting: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    @staticmethod
    @init_indian_api
    def get_stock_forecasts(stock_id: Annotated[str, "Stock ID"],
                            measure_code: Annotated[str, "Measure Code (EPS, CPS)"],
                            period_type: Annotated[str, "Annual or Interim"],
                            data_type: Annotated[str, "Actuals or Estimates"],
                            age: Annotated[str, "Data Age (OneWeekAgo, Current)"], headers: Optional[Dict[str, str]] = None):
        url = (f"{API_BASE_URL}/stock_forecasts?stock_id={stock_id}"
               f"&measure_code={measure_code}&period_type={period_type}"
               f"&data_type={data_type}&age={age}")
        print(f"🔍 Requesting: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    utils = IndianMarketUtils
    print(utils.get_stock_details("Tata Steel"))
    print(utils.get_stock_details("DMART"))
    print(utils.get_financial_statement("Tata Steel", "balance"))
    print(utils.get_historical_data("Tata Steel", "1yr", "price"))
    print(utils.get_recent_announcements("Tata Steel"))
    print(utils.get_stock_forecasts("S0003026", "EPS", "Annual", "Estimates", "Current"))
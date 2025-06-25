# D:/dev/FinRobot/finrobot/data_source/__init__.py
"""data_source: Aggregates all financial data utility classes with conditional imports."""

# Explicitly import all data source utility classes found in your directory
# from .finance_data import FinanceDataUtils # New: Based on finance_data.py
from .fmp_utils import FMPUtils
from .indian_spec_utils import IndianMarketUtils # Renamed to IndianMarketUtils as per common usage
from .sec_utils import SECUtils

# Define what gets imported when someone does 'from data_source import *'
__all__ = [
    "FMPUtils",
    "IndianMarketUtils", # Updated name
    "SECUtils",
]

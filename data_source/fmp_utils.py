import os
import sys
import requests
import numpy as np
import pandas as pd
import json
import random
from datetime import datetime, timedelta
from typing import Annotated, List, Literal, Optional, Any, Dict, Union
import time
from functools import wraps
from collections import defaultdict
import traceback # Ensure this is imported at the top

# --- Added lines to ensure finrobot package is discoverable when run directly ---
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..'))

if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- End of added lines ---


# ------------------------------
# Decorator to initialize API key
# ------------------------------
def init_fmp_api(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global fmp_api_key
        fmp_api_key = os.getenv("FMP_API_KEY")
        if not fmp_api_key:
            #print("Please set the environment variable FMP_API_KEY to use the FMP API.")
            return None
        return func(*args, **kwargs)
    return wrapper


# --- FMPUtils Class ---

class FMPUtils:
    BASE_URL = "https://financialmodelingprep.com/api/v3"
    BASE_URL_V4 = "https://financialmodelingprep.com/api/v4"
    STABLE_URL = "https://financialmodelingprep.com/stable/"
    
    @staticmethod
    @init_fmp_api
    def get_stock_data(
        ticker_symbol: Annotated[str, "The stock ticker_symbol (e.g., 'SNAP')."],
        start_date: Annotated[str, "The start date for the data range in 'YYYY-MM-DD' format."],
        end_date: Annotated[str, "The end date for the data range in 'YYYY-MM-DD' format."],
    ) -> pd.DataFrame:
        """Fetches comprehensive stock data, including Open, High, Low, Close, and Volume."""
    
        url = "https://financialmodelingprep.com/stable/historical-price-eod/full"
        params = {
            "symbol": ticker_symbol,
            "from": start_date,
            "to": end_date,
            "apikey": fmp_api_key
        }


        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            parsed = response.json()
        except requests.exceptions.RequestException as e:
            #print(f"[Network Error] {e}", file=sys.stderr)
            return pd.DataFrame()
        except ValueError as e:
            #print(f"[JSON Parse Error] {e}", file=sys.stderr)
            return pd.DataFrame()

        # Extract historical data
        hist = parsed.get("historical", []) if isinstance(parsed, dict) else parsed if isinstance(parsed, list) else []
        if not hist:
            #print(f"No historical data for {ticker_symbol} from {start_date} to {end_date}.", file=sys.stderr)
            return pd.DataFrame()

        df = pd.DataFrame(hist)
        df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)

        selected_columns = ['open', 'high', 'low', 'close', 'volume']
        return df[selected_columns]

    # MODIFIED: fetch_historical_close_prices is now an instance method
    @staticmethod
    @init_fmp_api
    def fetch_historical_close_prices(
        ticker_symbol: Annotated[str, "The stock ticker_symbol (e.g., 'GOOGL')."],
        start_date: Annotated[str, "The start date for the data range in 'YYYY-MM-DD' format."],
        end_date: Annotated[str, "The end date for the data range in 'YYYY-MM-DD' format."],
    ) -> pd.Series:
        """Fetches historical daily close prices from FMP."""

        url = f"{FMPUtils.BASE_URL}/historical-price-full/{ticker_symbol}?from={start_date}&to={end_date}&apikey={fmp_api_key}"
        
        try:
            response = requests.get(url, timeout=15) # Use session
            response.raise_for_status()
            data = response.json()

            if 'historical' in data and data['historical']:
                df = pd.DataFrame(data['historical'])
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date').sort_index()
                return df['close']
            else:
                #print(f"Warning: No historical close prices found for {ticker_symbol} in the specified range.", file=sys.stderr)
                return pd.Series(dtype=float)
        except requests.exceptions.RequestException as e:
           # print(f"Error fetching historical close prices for {ticker_symbol}: {e}", file=sys.stderr)
            return pd.Series(dtype=float)
        except KeyError:
            #print(f"Error: Unexpected data structure for {ticker_symbol} when fetching close prices.", file=sys.stderr)
            return pd.Series(dtype=float)

    @staticmethod
    @init_fmp_api
    def get_analyst_rating(
        ticker_symbol: Annotated[str, "The ticker_symbol."] = None,
        date: Annotated[str, "The date in YYYY-MM-DD format."] = None,
    ) -> dict:
        """Fetches analyst rating for a specific symbol on a specific date from FMP."""


        # ✅ Normalize to datetime
        if isinstance(date, str):
            target_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            isinstance(date, datetime)
            target_date = date

        url = f"https://financialmodelingprep.com/stable/ratings-historical?"
        params = {
            "symbol": ticker_symbol,
            "limit": 820,  # You can increase this if needed
            "apikey": fmp_api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            for record in data:
                record_date_str = record.get("date")
                if not record_date_str:
                    continue

                try:
                    record_date = datetime.strptime(record_date_str, "%Y-%m-%d")
                    if record_date.year == target_date.year and record_date.month == target_date.month:
                        return record.get("rating", "Rating not found")
                except Exception:
                    continue

            return "NA"

        except requests.exceptions.RequestException as e:
            #print(f"Error fetching rating for {ticker_symbol}: {e}")
            return "Error: Request failed"

    # MODIFIED: get_company_profile is now an instance method
    @staticmethod
    @init_fmp_api
    def get_company_profile(
        ticker_symbol: Annotated[str | None, "The stock ticker_symbol. This is optional."] = None,
    ) -> dict:
        """Fetches basic company profile information from FMP."""


        """Fetches basic company profile information from FMP."""
        url = f"https://financialmodelingprep.com/stable/profile?symbol={ticker_symbol}&apikey={fmp_api_key}"

        try:
            response = requests.get(url, timeout=15) # Use session
            response.raise_for_status()
            data = response.json()
            return data[0] if isinstance(data, list) and data else {}
        except requests.exceptions.RequestException as e:
            #print(f"Error fetching company profile for {ticker_symbol}: {e}", file=sys.stderr)
            return {"error": "Failed to fetch company profile"}
        except KeyError:
            #print(f"Error: Unexpected data structure for company profile {ticker_symbol}.", file=sys.stderr)
            return {"error": "Unexpected data structure"}

    @staticmethod
    @init_fmp_api
    def get_income_statement(
        ticker_symbol: Annotated[str, "The stock ticker_symbol (e.g., 'MSFT')."],
        limit: Annotated[int, "The number of past periods to retrieve (e.g., 5 for 5 years)."] = 7,
        period: Annotated[str, "The reporting period, either 'annual' or 'quarter'."] = 'annual',
    ) -> Union[list[dict], str]:
        """Fetches the income statement for a given ticker_symbol from FMP."""

        url = f"{FMPUtils.STABLE_URL}/income-statement-as-reported?symbol={ticker_symbol}&limit={limit}&period={period}&apikey={fmp_api_key}"

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data:
                # This is the successful path
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date').sort_index()
                return df
            else:
                # --- CHANGE 2: Instead of a warning string, return an empty DataFrame ---
                print(f"Warning: No income statement found for {ticker_symbol}. Returning empty DataFrame.")
                return pd.DataFrame()

        except requests.exceptions.RequestException as e:
            # --- CHANGE 3: Instead of an error string, return an empty DataFrame ---
            print(f"Error during API request for {ticker_symbol}: {e}. Returning empty DataFrame.")
            return pd.DataFrame()
            
        except Exception as e:
            # --- CHANGE 4: For any other error, also return an empty DataFrame ---
            print(f"An unexpected error occurred for {ticker_symbol}: {e}. Returning empty DataFrame.")
            return pd.DataFrame()
                    
    @staticmethod
    @init_fmp_api
    def _make_request(endpoint: str, params: Optional[Dict[str, Any]] = None, use_v4: bool = False) -> requests.Response:
        """Internal helper to make authenticated FMP API requests. Returns requests.Response object."""
        url = f"{FMPUtils.BASE_URL}{endpoint}"
        if use_v4:
            url = f"{FMPUtils.BASE_URL_V4}{endpoint}"

        _params = params.copy() if params else {}
        _params['apikey'] = fmp_api_key

        return requests.get(url, params=_params, timeout=15)

    @staticmethod
    @init_fmp_api
    def get_balance_sheet(
        ticker_symbol: Annotated[str, "The stock ticker symbol (e.g., 'MSFT')"],
        freq: Annotated[Literal["annual", "quarter"], "Reporting frequency"] = "annual",
        limit: Annotated[int, "Number of periods to retrieve"] = 7,
    ) -> Union[pd.DataFrame, str]:
        """
        Fetches the balance sheet for a given ticker_symbol from FMP API.

        Args:
            ticker_symbol: Company stock symbol (e.g., 'MSFT').
            freq: 'annual' or 'quarter'.
            limit: Number of periods to retrieve.

        Returns:
            pd.DataFrame or empty DataFrame on error.
        """
        try:
            endpoint = f"/balance-sheet-statement/{ticker_symbol.upper()}"
            params = {
                "limit": limit,
                "period": "FY" if freq == "annual" else "Q4"
            }

            response = FMPUtils._make_request(endpoint, params=params)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list) or not data:
                print(f"Warning: No balance sheet data returned for {ticker_symbol}. Returning empty DataFrame.")
                return pd.DataFrame()

            df = pd.DataFrame(data)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            elif "period" in df.columns:
                df["date"] = pd.to_datetime(df["period"], errors="coerce")
            else:
                print(f"Warning: Neither 'date' nor 'period' columns found for {ticker_symbol}.")
                return pd.DataFrame()
            df = df.set_index("date").sort_index(ascending=False)
            return df

        except requests.exceptions.RequestException as e:
            print(f"API request error for {ticker_symbol}: {e}. Returning empty DataFrame.")
            return pd.DataFrame()

        except Exception as e:
            print(f"Unexpected error in get_balance_sheet for {ticker_symbol}: {e}. Returning empty DataFrame.")
            return pd.DataFrame()

    @staticmethod
    @init_fmp_api
    def get_target_price(
        ticker_symbol: Annotated[str, "The stock ticker_symbol (e.g., 'AAPL')."],
        date: Annotated[str, "The target date for the price analysis in 'YYYY-MM-DD' format."],
    ) -> float:
        """Get the target price for a given stock and returns it as a float."""
        url = f"/price-target?symbol={ticker_symbol}"
        response = FMPUtils._make_request(url, use_v4=True)

        if isinstance(response, str):
            return response  # error message propagated

        if not hasattr(response, 'json'):
            return "Invalid API response (no JSON returned)."

        try:
            data = response.json()
        except Exception as e:
            return f"Failed to parse JSON: {str(e)}"

        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return "Invalid date format. Use yyyy-mm-dd."
        estimates = []
        if isinstance(data, list):
            for item in data:
                try:
                    published_str = item.get("publishedDate", "").split("T")[0]
                    published_date = datetime.strptime(published_str, "%Y-%m-%d")
                    print("published: ", published_date,"date_obj: ", date_obj)
                    if abs((published_date - date_obj).days) <= 60:
                        price = item.get("priceTarget")
                        if isinstance(price, (int, float)):
                            estimates.append(price)
                except Exception as e:
                    print(f"[WARN] Date parsing failed: {e}", file=sys.stderr)

        if estimates:
            return f"{np.min(estimates)} - {np.max(estimates)} (md. {np.median(estimates)})"
        else:
            return "No target price found around the given date."

    @staticmethod
    @init_fmp_api
    def get_sec_report(
        ticker_symbol: Annotated[str, "ticker_symbol"],
        fyear: Annotated[str, "year of the 10-K report"] = "latest",

    ) -> dict | None:
        """Get the URL and filing date of the 10-K report for a given stock and year."""
        endpoint = f"/sec_filings/{ticker_symbol}"
        params = {"type": "10-K", "page": 0}
        response = FMPUtils._make_request(endpoint, params=params)

        if not response.ok:
            return {"error": f"Failed to retrieve data: {response.status_code}"}

        data = response.json()
        if not data:
            return {"error": "No filings returned from API."}

        if fyear == "latest":
            return {
                "link": data[0]["finalLink"],
                "date": data[0]["fillingDate"]
            }

        for filing in data:
            if filing["fillingDate"].split("-")[0] == fyear:
                print(f"Found filing for {ticker_symbol} in FY{fyear}: {filing['finalLink']} on {filing['fillingDate']}")
                input("Press Enter to continue after verifying the SEC report data...3")  # Debug   
                return {
                    "link": filing["finalLink"],
                    "date": filing["fillingDate"]
                }
        # If no filing found for the specified year
        return {"error": f"No 10-K filing found for {ticker_symbol} in FY{fyear}."}

    @staticmethod
    @init_fmp_api
    def get_historical_market_cap(
        ticker_symbol: Annotated[str, "Ticker_symbol"],
        date: Annotated[str, "Date of the market cap in 'yyyy-mm-dd' format"],
    ) -> str:
        """
        Returns the market capitalization for a specific company on a specific date.
        
        Format: 
        - If found: "Market Cap on {date}: {value} USD"
        - If not found or error: returns user-friendly error message
        """
        try:
            if isinstance(date, datetime):
                date = date.strftime("%Y-%m-%d")

            endpoint = f"/historical-market-capitalization/{ticker_symbol}"
            params = {"limit": 1, "from": date, "to": date}
            response = FMPUtils._make_request(endpoint, params=params)

            if not response.ok:
                return f"Failed to retrieve data: {response.status_code}"

            data = response.json()
            if isinstance(data, list) and data and "marketCap" in data[0]:
                market_cap = float(data[0]["marketCap"])
                return f"Market Cap on {date}: {market_cap:,.2f} USD"
            else:
                return f"No historical market cap data found for {ticker_symbol} on {date}."
        except Exception as e:
            return f"Error retrieving market cap for {ticker_symbol} on {date}: {e}"

    @staticmethod
    @init_fmp_api
    def get_historical_bvps(
        ticker_symbol: Annotated[str, "Ticker_symbol"],
        target_date: Annotated[str, "Date of the BVPS in 'yyyy-mm-dd' format"],
    ) -> str:
        """
        Returns the Book Value Per Share (BVPS) for a given stock on a date closest to the specified date.
        
        Output format:
        - Success: "BVPS on or near {date}: {value}"
        - Failure: clear message indicating why it failed
        """
        try:
            if isinstance(target_date, datetime):
                target_date_str = target_date.strftime("%Y-%m-%d")
            else:
                target_date_str = target_date

            try:
                target_date_obj = datetime.strptime(target_date_str, "%Y-%m-%d")
            except ValueError:
                return f"Invalid date format: {target_date}. Expected format is yyyy-mm-dd."

            endpoint = f"/key-metrics/{ticker_symbol}"
            params = {"limit": 40}
            response = FMPUtils._make_request(endpoint, params=params)

            if not response.ok:
                return f"Failed to retrieve data: {response.status_code}"

            data = response.json()
            if not isinstance(data, list) or not data:
                return f"No key metrics data found for {ticker_symbol}."

            # Find closest entry by date
            closest_data = None
            min_date_diff = float("inf")
            for entry in data:
                entry_date_str = entry.get("date")
                if entry_date_str:
                    try:
                        entry_date_obj = datetime.strptime(entry_date_str, "%Y-%m-%d")
                        diff = abs((target_date_obj - entry_date_obj).days)
                        if diff < min_date_diff:
                            min_date_diff = diff
                            closest_data = entry
                    except ValueError:
                        continue

            if closest_data and "bookValuePerShare" in closest_data:
                bvps_value = closest_data["bookValuePerShare"]
                return f"BVPS on or near {target_date_str}: {bvps_value:,.2f}"
            else:
                return f"Book Value Per Share not found for {ticker_symbol} near {target_date_str}."

        except Exception as e:
            return f"Error retrieving BVPS for {ticker_symbol} on {target_date}: {e}"

    @staticmethod
    @init_fmp_api
    def get_financial_metrics(
        ticker_symbol: Annotated[str, "Ticker_symbol"],
        years: Annotated[int, "Number of years to retrieve (default is 5)"] = 5,
    ) -> tuple[pd.DataFrame, str, str]:
        """
        Returns a DataFrame containing financial metrics over the last 'years' years for the given stock ticker_symbol.
        
        The DataFrame has years as columns and metrics as rows.
        If no valid data is found, an empty DataFrame is returned.
        """
        try:
            all_metrics_by_year = defaultdict(dict)

            # --- API endpoints ---
            endpoints = {
                "income": f"/income-statement/{ticker_symbol}",
                "metrics": f"/key-metrics/{ticker_symbol}",
                "ratios": f"/ratios/{ticker_symbol}",
                "cashflow": f"/cash-flow-statement/{ticker_symbol}",
                "profile": f"/profile/{ticker_symbol}",  # <-- NEW ENDPOINT
            }
            params = {"limit": years + 1}

            # --- API calls ---
            income_response = FMPUtils._make_request(endpoints["income"], params=params)
            key_metrics_response = FMPUtils._make_request(endpoints["metrics"], params=params)
            ratios_response = FMPUtils._make_request(endpoints["ratios"], params=params)
            cashflow_response = FMPUtils._make_request(endpoints["cashflow"], params=params)
            profile_response = FMPUtils._make_request(endpoints["profile"])  

            # --- Validate responses ---
            if not (income_response.ok and key_metrics_response.ok and ratios_response.ok and cashflow_response.ok):
                return pd.DataFrame(), "USD", ticker_symbol.upper()

            income_data = income_response.json()
            key_metrics_data = key_metrics_response.json()
            ratios_data = ratios_response.json()
            cashflow_data = cashflow_response.json()
            # --- Validate data format ---
            if not (isinstance(income_data, list) and isinstance(key_metrics_data, list)
                    and isinstance(ratios_data, list) and isinstance(cashflow_data, list)):
                return pd.DataFrame(), "USD", ticker_symbol.upper()

            # --- Process metrics by year ---
            for i in range(min(years, len(income_data))):
                if i < len(key_metrics_data) and i < len(ratios_data) and i < len(cashflow_data):
                    income = income_data[i]
                    key_metrics = key_metrics_data[i]
                    ratios = ratios_data[i]
                    cashflow = cashflow_data[i]
                    free_cash_flow = cashflow.get("freeCashFlow", 0)

                    revenue = income.get("revenue", 0)
                    gross_profit = income.get("grossProfit", 0)
                    net_income = income.get("netIncome", 1e-9) or 1e-9  # Avoid divide by zero

                    metrics = {
                        "Revenue": round(revenue / 1e6),
                        "Gross Profit": round(gross_profit / 1e6),
                        "Gross Margin": round((gross_profit / revenue) if revenue else 0, 2),
                        "EBITDA": round(income.get("ebitda", 0) / 1e6),
                        "EBITDA Margin": round(income.get("ebitdaratio", 0), 2),
                        "FCF": round(free_cash_flow / 1e6),
                        "FCF Conversion": round((free_cash_flow / net_income), 2),
                        "ROIC": f"{round(key_metrics.get('roic', 0) * 100, 1)}%",
                        "EV/EBITDA": round(key_metrics.get("enterpriseValueOverEBITDA", 0), 2),
                        "PE Ratio": round(ratios.get("priceEarningsRatio", 0), 2),
                        "PB Ratio": round(key_metrics.get("pbRatio", 0), 2),
                        "CFO": round(cashflow.get("operatingCashFlow", 0) / 1e6),  # <-- NEW METRIC
                    }

                    # Revenue growth (YoY)
                    revenue_growth_val = "N/A"
                    if i + 1 < len(income_data):
                        prev_revenue = income_data[i + 1].get("revenue", 0)
                        if prev_revenue:
                            growth = ((revenue - prev_revenue) / prev_revenue) * 100
                            revenue_growth_val = f"{round(growth, 1)}%"
                    metrics["Revenue Growth"] = revenue_growth_val

                    year = income.get("date", str(datetime.now().year - i))[:4]
                    all_metrics_by_year[year].update(metrics)

            # --- Create DataFrame ---
            df = pd.DataFrame(all_metrics_by_year)

            kpi_order = [
                "Revenue", "Revenue Growth", "Gross Profit", "Gross Margin", 
                "EBITDA", "EBITDA Margin", "Net Income", "CFO", "FCF", 
                "FCF Conversion", "ROIC", "EV/EBITDA", "PE Ratio", "PB Ratio"
            ]
            df = df.reindex(kpi_order).dropna(how='all')
            
            # --- Get currency and name from profile ---  <-- NEW BLOCK
            currency = income_data[0].get("reportedCurrency") or key_metrics_data[0].get("currency") or "USD"
            name = ticker_symbol.upper()
            
            if profile_response.ok:
                profile_data = profile_response.json()
                if isinstance(profile_data, list) and profile_data:
                    profile = profile_data[0]
                    currency = profile.get("currency", currency)
                    name = profile.get("companyName", name)

            return df.sort_index(axis=1), currency, name
        except Exception as e:
            return pd.DataFrame(), "USD", ticker_symbol.upper()

    @staticmethod
    @init_fmp_api
    def get_competitor_financial_metrics(
        ticker_symbol: Annotated[str, "ticker_symbol of the company"],
        competitors: Annotated[List[str], "List of competitor ticker_symbols"],
        years: Annotated[int, "Number of years to retrieve (default: 4)"] = 4,
    ) -> Dict[str, pd.DataFrame]:
        """
        Returns a dictionary mapping each ticker_symbol (including competitors) to its financial metrics DataFrame.
        
        The DataFrames are structured year-wise with financial metrics. If no data is available for a ticker_symbol,
        an empty DataFrame is returned for that ticker_symbol.
        """
        results = {}
        symbols = [ticker_symbol] + competitors

        for symbol in symbols:
            try:
                # EXPECTED RETURN: (df, currency, company_name)
                result = FMPUtils.get_financial_metrics(symbol, years=years)
                
                # Unpack the tuple
                if isinstance(result, tuple) and len(result) >= 1:
                    df = result[0]  # First element is the DataFrame
                else:
                    df = result  # Fallback if not tuple
                
                if isinstance(df, pd.DataFrame) and not df.empty:
                    results[symbol] = df
                else:
                    results[symbol] = pd.DataFrame()
            except Exception:
                results[symbol] = pd.DataFrame()

        return results

    @staticmethod
    @init_fmp_api
    def get_company_peers(
        symbol: Annotated[str, "ticker_symbol for the target company"]
    ) -> List[str]:
        """
        Returns a list of peer ticker_symbols for the given company.
        
        The result excludes the original symbol itself and handles inconsistent API responses gracefully.
        If no peers are found or the request fails, an empty list is returned.
        """
        try:
            endpoint = f"/stock_peers"
            params = {"symbol": symbol}
            response = FMPUtils._make_request(endpoint, params=params, use_v4=True)

            if not response.ok:
                return []

            data = response.json()
            peers_list = []

            if isinstance(data, list):
                # Case 1: [{'symbol': 'ABC', 'peersList': ['DEF', 'GHI']}]
                if data and isinstance(data[0], dict) and 'peersList' in data[0]:
                    for entry in data:
                        if isinstance(entry.get('peersList'), list):
                            peers_list.extend(entry['peersList'])
                else:
                    # Case 2: Direct list of symbols
                    peers_list = data

            # Remove original symbol if present
            return [p for p in peers_list if p != symbol]
        
        except Exception:
            return []


# Example usage (if this file is run directly)
if __name__ == "__main__":
    from utils import register_keys_from_json
    import re
    # Corrected path for direct execution from finrobot/data_source
    register_keys_from_json(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config_api_keys.json'))) # Ensure .json extension

    try:
        api_key=os.environ.get("FMP_API_KEY")


        income_statment = FMPUtils.get_income_statement ("AAPL","Annual")
        print(income_statment)
        input("Income Statement Done! Press Enter to continue...")

        market_cap_raw = FMPUtils.get_historical_market_cap("AAPL", "2024-06-17")
        print("Raw Market Cap:", market_cap_raw)

        market_cap_formatted = "0.00"  # Default value

        if isinstance(market_cap_raw, str):
            match = re.search(r'(\d{1,3}(?:,\d{3})+(?:\.\d+)?)', market_cap_raw)
            print("Match object:", match)
            if match:
                try:
                    market_cap_value = float(match.group(0).replace(",", ""))
                    market_cap_formatted = f"{market_cap_value / 1e6:.2f}"  # Convert to millions
                except ValueError:
                    print("Failed to convert market cap to float.")

        print("Market Cap (in millions):", market_cap_formatted)
        input("Press Enter to continue...")

        balance_sheet = FMPUtils.get_balance_sheet("AAPL","annual")
        print(balance_sheet)
        input("Press Enter to continue...")
        company_profile = FMPUtils.get_company_profile("AAPL")
        print(company_profile)  
        input("Press Enter to continue...")

        print("\n--- Testing get_sec_report (MSFT 2024) ---")
        sec_report = FMPUtils.get_sec_report("MSFT", "2023")
        print(sec_report)
        input("Press Enter to continue...")
        print("\n--- Testing get_target_price (AAPL 2024-01-31) ---")
        target_price = FMPUtils.get_target_price("AAPL", "2025-06-17")
        print(target_price)
        input("Press Enter to continue...")

        print("\n--- Testing get_financial_metrics (GOOGL, 5 years) ---")
        df, currency, name = FMPUtils.get_financial_metrics("GOOGL", years=5)

        print(f"\nCurrency: {currency}")
        print(df)
        print("Curreny: ", currency)
        print("Name: ", name)
        input("Press Enter to continue...")

        print("\n--- Testing get_competitor_financial_metrics (GOOGL, competitors, 2 years) ---")
        competitor_metrics = FMPUtils.get_competitor_financial_metrics("GOOGL", ["AAPL", "MSFT"], years=2)
        for sym, df in competitor_metrics.items():
            print(f"--- {sym} ---")
            print(df)
        
        print("\n--- Testing get_company_peers (AAPL) ---")
        peers = FMPUtils.get_company_peers("AAPL")
        print(peers)
        input("Press Enter to continue...")

    except ValueError as ve:
        print(f"Initialization Error: {ve}", file=sys.stderr)
    except Exception as e:
        print(f"An error occurred during testing: {e}", file=sys.stderr)
        traceback.print_exc() # Print full traceback for unexpected errors
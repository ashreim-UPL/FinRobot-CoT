# D:/dev/FinRobot/finrobot/company_resolver.py

import logging
import json
import re
import os
import sys 
from typing import Optional, Dict, Any
import aiohttp
import socket # For force_ipv4, which will be moved as per our previous discussion

# Import FMPUtils and IndianMarketUtils here, as they are explicitly used for competitor lookup
from finrobot.data_source import FMPUtils, IndianMarketUtils

# --- HARDCODED CONFIGURATION VALUES ---
# These values are now directly embedded in the module.
YAHOO_FINANCE_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# --- Module-level logger for company resolver ---
# This logger assumes setup_logging() has been called globally at application startup.
company_resolver_logger = logging.getLogger("CompanyResolver")

# --- Network related overrides (MOVE THIS BLOCK to finrobot/utils.py or finrobot/networking.py) ---
# This is general network configuration, not specific to company resolution.
# It should be moved and called once at application startup.
_original_getaddrinfo = socket.getaddrinfo
def force_ipv4(*args, **kwargs):
    return [info for info in _original_getaddrinfo(*args, **kwargs) if info[0] == socket.AF_INET]
socket.getaddrinfo = force_ipv4


# --- Company Identification and Classification ---
async def identify_company_and_region(company_query: str) -> dict:
    """
    Identifies a company's official name, region (IN, US, or Unknown),
    various tickers/identifiers, AND its top 3 main competitors using Yahoo Finance search and FMP API.
    """
    if not isinstance(company_query, str) or not company_query.strip():
        company_resolver_logger.error("Invalid 'company_query': Must be a non-empty string.")
        return {"validation_error": "Invalid 'company_query': Must be a non-empty string."}

    # --- Use hardcoded values directly ---
    base_url = YAHOO_FINANCE_SEARCH_URL
    headers = {
        'User-Agent': DEFAULT_USER_AGENT
    }

    # No need to check if base_url is None, as it's hardcoded.
    # We can still add a basic validation if the hardcoded value itself was somehow an empty string.
    if not base_url:
        company_resolver_logger.error("Hardcoded Yahoo Finance search URL is empty.")
        return {"company_query": company_query, "tool_error": "Internal configuration error: Yahoo Finance search URL is empty."}

    search_url = f"{base_url}?q={company_query.strip()}"
    
    # Initialize company_info structure as expected by run_financial_analysis
    company_info = {
        "company_query": company_query,
        "company_details": {
            "official_name": None,
            "region": "Unknown",
            "identifiers": {},
            "message": "",
            "competitors": []
        },
        "region": "Unknown"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(search_url, timeout=10) as resp:
                resp.raise_for_status() # Raises an exception for 4xx/5xx responses
                data = await resp.json()

        if not data.get("quotes"):
            company_info["tool_error"] = "No matching company found for primary identification."
            company_resolver_logger.warning(f"No matching company found for '{company_query}' via Yahoo Finance search.")
            return company_info

        top = data["quotes"][0]
        official_name = top.get("longname") or top.get("shortname") or top.get("symbol")
        exchange = top.get("exchange")
        symbol = top.get("symbol")

        indian_exchanges = ("NSE", "BSE", "IND")
        us_exchanges = ("NMS", "NYQ", "PCX", "NAS", "ASE", "NYSE", "NASDAQ")

        region = "Unknown"
        if symbol and (symbol.endswith(".NS") or symbol.endswith(".BO")):
            region = "IN"
        elif exchange in indian_exchanges:
            region = "IN"
        elif exchange in us_exchanges:
            region = "US"

        company_info["company_details"] = {
            "official_name": official_name,
            "region": region,
            "identifiers": {
                "ticker": symbol,
                "yfinance_ticker": symbol,
                "fmp_ticker": symbol.split('.')[0] if symbol else None,
                "finnhub_symbol": symbol.split('.')[0] if symbol else None,
                "sec_cik": None,
                "indian_stock_name": official_name if region == "IN" else None,
                "indian_stock_id": None
            },
            "message": f"Company identified as {official_name} ({symbol} on {exchange}, Region: {region})",
            "competitors": []
        }
        company_info["region"] = region

    except aiohttp.ClientError as e: # Catch aiohttp specific errors
        company_resolver_logger.error(f"Network or HTTP error during primary company identification for '{company_query}': {e}", exc_info=True)
        company_info["tool_error"] = f"Network or API communication error: {str(e)}"
        return company_info
    except json.JSONDecodeError as e: # Catch JSON parsing errors
        company_resolver_logger.error(f"JSON parsing error during primary company identification for '{company_query}': {e}", exc_info=True)
        company_info["tool_error"] = f"API response format error: {str(e)}"
        return company_info
    except Exception as e: # Catch any other unexpected errors
        company_resolver_logger.error(f"Unexpected error during primary company identification for '{company_query}': {e}", exc_info=True)
        company_info["tool_error"] = f"An unexpected error occurred during identification: {str(e)}"
        return company_info

    # --- Competitor Lookup using FMPUtils ---
    competitor_list = []
    # Ensure FMP_API_KEY is registered globally (e.g., at app startup via register_keys_from_json)
    if company_info["company_details"]["identifiers"].get("fmp_ticker"):
        try:
            company_resolver_logger.info(f"🕵️‍♀️ Searching for competitors for {company_info['company_details']['official_name']} using FMP API...")
            
            fmp_utils_instance = FMPUtils() 
            peers = fmp_utils_instance.get_company_peers(symbol=company_info["company_details"]["identifiers"]["fmp_ticker"])
            
            if peers and isinstance(peers, list):
                competitor_list = [peer.strip() for peer in peers if isinstance(peer, str)][:3]
                
                primary_name_lower = company_info['company_details']['official_name'].lower()
                primary_ticker_lower = company_info['company_details']['identifiers']['fmp_ticker'].lower()
                
                competitor_list = [
                    comp for comp in competitor_list
                    if primary_name_lower not in comp.lower() and primary_ticker_lower not in comp.lower()
                ]
                
                company_resolver_logger.info(f"✅ Found competitors via FMP API: {competitor_list}")
            else:
                company_resolver_logger.warning(f"No peers found or invalid response from FMP for {company_info['company_details']['official_name']}.")
            
        except Exception as e:
            company_resolver_logger.error(f"Error during FMP competitor lookup for {company_info['company_details']['official_name']}: {e}", exc_info=True)
            competitor_list = []

    company_info["company_details"]["competitors"] = competitor_list
    company_info["competitors"] = competitor_list # Redundant but kept for previous compatibility for now

    return company_info
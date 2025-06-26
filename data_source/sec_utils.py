import os
import sys
import requests
from sec_api import ExtractorApi, QueryApi, RenderApi
from functools import wraps
from typing import Annotated

#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
#from finrobot.utils import SavePathType, decorate_all_methods
#from finrobot.data_source import FMPUtils
from functional.utils import SavePathType, decorate_all_methods

PDF_GENERATOR_API = "https://api.sec-api.io/filing-reader"


def init_sec_api(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global extractor_api, query_api, render_api
        if os.environ.get("SEC_API_KEY") is None:
            print("Please set the environment variable SEC_API_KEY to use sec_api.")
            return None
        else:
            extractor_api = ExtractorApi(os.environ["SEC_API_KEY"])
            query_api = QueryApi(os.environ["SEC_API_KEY"])
            render_api = RenderApi(os.environ["SEC_API_KEY"])
            print("Sec Api initialized")
            return func(*args, **kwargs)

    return wrapper


@decorate_all_methods(init_sec_api)
class SECUtils:

    CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")

    def get_10k_metadata(
        ticker: Annotated[str, "ticker symbol"],
        start_date: Annotated[
            str, "start date of the 10-k file search range, in yyyy-mm-dd format"
        ],
        end_date: Annotated[
            str, "end date of the 10-k file search range, in yyyy-mm-dd format"
        ],
    ):
        """
        Search for 10-k filings within a given time period, and return the meta data of the latest one
        """
        query = {
            "query": f'ticker:"{ticker}" AND formType:"10-K" AND filedAt:[{start_date} TO {end_date}]',
            "from": 0,
            "size": 10,
            "sort": [{"filedAt": {"order": "desc"}}],
        }
        response = query_api.get_filings(query)
        if response["filings"]:
            return response["filings"][0]
        return None

    def download_10k_filing(
        ticker: Annotated[str, "ticker symbol"],
        start_date: Annotated[
            str, "start date of the 10-k file search range, in yyyy-mm-dd format"
        ],
        end_date: Annotated[
            str, "end date of the 10-k file search range, in yyyy-mm-dd format"
        ],
        save_folder: Annotated[
            str, "name of the folder to store the downloaded filing"
        ],
    ) -> str:
        """Download the latest 10-K filing as htm for a given ticker within a given time period."""
        metadata = SECUtils.get_10k_metadata(ticker, start_date, end_date)
        if metadata:
            ticker = metadata["ticker"]
            url = metadata["linkToFilingDetails"]

            try:
                date = metadata["filedAt"][:10]
                file_name = date + "_" + metadata["formType"] + "_" + url.split("/")[-1]

                if not os.path.isdir(save_folder):
                    os.makedirs(save_folder)

                file_content = render_api.get_filing(url)
                file_path = os.path.join(save_folder, file_name)
                with open(file_path, "w") as f:
                    f.write(file_content)
                return f"{ticker}: download succeeded. Saved to {file_path}"
            except:
                return f"❌ {ticker}: downloaded failed: {url}"
        else:
            return f"No 2023 10-K filing found for {ticker}"

    def download_10k_pdf(
        ticker: Annotated[str, "ticker symbol"],
        start_date: Annotated[
            str, "start date of the 10-k file search range, in yyyy-mm-dd format"
        ],
        end_date: Annotated[
            str, "end date of the 10-k file search range, in yyyy-mm-dd format"
        ],
        save_folder: Annotated[
            str, "name of the folder to store the downloaded pdf filing"
        ],
    ) -> str:
        """Download the latest 10-K filing as pdf for a given ticker within a given time period."""
        metadata = SECUtils.get_10k_metadata(ticker, start_date, end_date)
        if metadata:
            ticker = metadata["ticker"]
            filing_url = metadata["linkToFilingDetails"]

            try:
                date = metadata["filedAt"][:10]
                print(filing_url.split("/")[-1])
                file_name = (
                    date
                    + "_"
                    + metadata["formType"].replace("/A", "")
                    + "_"
                    + filing_url.split("/")[-1]
                    + ".pdf"
                )

                if not os.path.isdir(save_folder):
                    os.makedirs(save_folder)

                api_url = f"{PDF_GENERATOR_API}?token={os.environ['SEC_API_KEY']}&type=pdf&url={filing_url}"
                response = requests.get(api_url, stream=True)
                response.raise_for_status()

                file_path = os.path.join(save_folder, file_name)
                with open(file_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                return f"{ticker}: download succeeded. Saved to {file_path}"
            except Exception as e:
                return f"❌ {ticker}: downloaded failed: {filing_url}, {e}"
        else:
            return f"No 2023 10-K filing found for {ticker}"

    def get_10k_section(
        ticker_symbol: str,
        fyear: str,
        section: str | int,
        report_address: str = None,
        save_path: SavePathType = None,
        use_cache: bool = True,
    ) -> str:
        if isinstance(section, int):
            section = str(section)

        valid_sections = [str(i) for i in range(1, 16)] + ["1A", "1B", "7A", "9A", "9B"]
        if section not in valid_sections:
            raise ValueError(f"Invalid section: {section}")

        # Define cache path
        cache_file = os.path.join(SECUtils.CACHE_DIR, f"{ticker_symbol}_{fyear}_section_{section}.txt")

        # Use cache if available
        if use_cache and os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                return f.read()

        # Get report address if not provided
        if report_address is None:
            metadata = SECUtils.get_10k_metadata(ticker_symbol, f"{fyear}-01-01", f"{fyear}-12-31")
            report_address = metadata.get("linkToHtml") or metadata.get("linkToFilingDetails")
            if not report_address:
                raise ValueError(f"Could not resolve report address for {ticker_symbol} in {fyear}")

        print(f"[SECUtils] Fetching Section {section} from SEC for {ticker_symbol} ({fyear})")
        section_text = extractor_api.get_section(report_address, section, "text")

        # Save to cache
        if use_cache:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(section_text)

        # Optionally save to other location
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(section_text)

        return section_text


# Example usage (if this file is run directly)
if __name__ == "__main__":
    from utils import register_keys_from_json, decorate_all_methods
    import re
    # Corrected path for direct execution from finrobot/data_source
    register_keys_from_json(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config_api_keys.json'))) # Ensure .json extension

    print("SEC_API_KEY loaded:", os.environ.get("SEC_API_KEY") is not None)

    section_text = SECUtils.get_10k_section("MSFT", "2024", 7)

    print(">>> section_text type:", type(section_text))

    if isinstance(section_text, dict):
        print(">>> section_text keys:", section_text.keys())
        print(">>> section_text content (dict):", section_text)
    else:
        print(">>> section_text preview (string):\n", section_text[:300])
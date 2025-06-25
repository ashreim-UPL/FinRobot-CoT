
import os
import re
import pandas as pd
from textwrap import dedent
from typing import Annotated, List, Any
from datetime import timedelta, datetime
from pathlib import Path

#from ..data_source import SECUtils, FMPUtils, IndianMarketUtils
#from ..utils import save_to_file

# --- Added lines to ensure finrobot package is discoverable when run directly ---
import sys
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..'))

if project_root not in sys.path:
    sys.path.insert(0, project_root)
def some_function():
    from data_source import SECUtils, FMPUtils, IndianMarketUtils
    # function code

from functional.utils import save_to_file
import re


def combine_prompt(instruction, resource, table_str=None):
    if table_str:
        prompt = f"{table_str}\n\nResource: {resource}\n\nInstruction: {instruction}"
    else:
        prompt = f"Resource: {resource}\n\nInstruction: {instruction}"
    return prompt

class ReportAnalysisUtils:

    def analyze_income_stmt(
        ticker_symbol: Annotated[str, "ticker_symbol"],
        fyear: Annotated[str, "fiscal year of the 10-K report"],
        save_path: Annotated[str, "txt file path, to which the returned instruction & resources are written."],
    ) -> str:
        """
        Retrieve the income statement for the given ticker_symbol with the related section of its 10-K report.
        Then return with an instruction on how to analyze the income statement.
        """
        # Retrieve the income statement
        
        income_stmt = FMPUtils.get_income_statement(
            ticker_symbol=ticker_symbol,
            period="annual"
        )

        if not isinstance(income_stmt, pd.DataFrame):
            return f"Error: Expected a DataFrame, got {type(income_stmt)} - {income_stmt}"

        # ✅ Ensure 'date' is a column before using it
        if 'date' not in income_stmt.columns:
            income_stmt.reset_index(inplace=True)

        # ✅ Normalize and filter by fiscal year
        income_stmt['date'] = pd.to_datetime(income_stmt['date'])
        income_stmt.set_index('date', inplace=True)

        specific_year_df = income_stmt[income_stmt['fiscalYear'] == int(fyear)]
        if specific_year_df.empty:
            return f"Error: No income statement data found for fiscal year {fyear} for {ticker_symbol}."

        # ✅ Flatten the nested 'data' field
        data_dict = specific_year_df.iloc[0]['data']
        if not isinstance(data_dict, dict):
            return f"Error: Expected a dictionary in 'data' column but got {type(data_dict)}."

        flat_df = pd.DataFrame([data_dict]).T.reset_index()
        flat_df.columns = ['Metric', 'Value']
        df_string = f"Income statement for {fyear}:\n" + flat_df.to_string(index=False)

        # Analysis instruction
        instruction = dedent(
            """
            Conduct a comprehensive analysis of the company's income statement for the current fiscal year. 
            Start with an overall revenue record, including Year-over-Year or Quarter-over-Quarter comparisons, 
            and break down revenue sources to identify primary contributors and trends. Examine the Cost of 
            Goods Sold for potential cost control issues. Review profit margins such as gross, operating, 
            and net profit margins to evaluate cost efficiency, operational effectiveness, and overall profitability. 
            Analyze Earnings Per Share to understand investor perspectives. Compare these metrics with historical 
            data and industry or competitor benchmarks to identify growth patterns, profitability trends, and 
            operational challenges. The output should be a strategic overview of the company’s financial health 
            in a single paragraph, less than 130 words, summarizing the previous analysis into 4-5 key points under 
            respective subheadings with specific discussion and strong data support.
            """
        )

        # Retrieve the related section from the 10-K report
        section_text = SECUtils.get_10k_section(ticker_symbol, fyear, 7)

        # Combine everything into the prompt
        prompt = combine_prompt(instruction, section_text, df_string)
        save_to_file(prompt, save_path)
        return f"instruction & resources saved to {save_path}"

    def analyze_balance_sheet(
        ticker_symbol: Annotated[str, "ticker_symbol"],
        fyear: Annotated[str, "fiscal year of the 10-K report"],
        save_path: Annotated[str, "txt file path, to which the returned instruction & resources are written."]
    ) -> str:
        """
        Retrieve the balance sheet for the given ticker_symbol with the related section of its 10-K report.
        Then return with an instruction on how to analyze the balance sheet.
        """
        import pandas as pd
        # balance_sheet = YFinanceUtils.get_balance_sheet(ticker_symbol)
        balance_sheet = FMPUtils.get_balance_sheet(
            ticker_symbol=ticker_symbol,
            freq="annual"
        )
        # Filter by fiscal year
        fyear_matches = balance_sheet[balance_sheet.index.year.astype(str) == fyear]

        if fyear_matches.empty:
            return f"No balance sheet data found for fiscal year {fyear} for {ticker_symbol}."

        # Use only the matching year (typically one row)
        df_string = f"Balance sheet for fiscal year {fyear}:\n" + fyear_matches.to_string().strip()
        instruction = dedent(
            """
            Delve into a detailed scrutiny of the company's balance sheet for the most recent fiscal year, pinpointing 
            the structure of assets, liabilities, and shareholders' equity to decode the firm's financial stability and 
            operational efficiency. Focus on evaluating the liquidity through current assets versus current liabilities, 
            the solvency via long-term debt ratios, and the equity position to gauge long-term investment potential. 
            Contrast these metrics with previous years' data to highlight financial trends, improvements, or deteriorations. 
            Finalize with a strategic assessment of the company's financial leverage, asset management, and capital structure, 
            providing insights into its fiscal health and future prospects in a single paragraph. Less than 130 words.
            """
        )

        section_text = SECUtils.get_10k_section(ticker_symbol, fyear, 7)

        prompt = combine_prompt(instruction, section_text, df_string)

        save_to_file(prompt, save_path)
        return f"instruction & resources saved to {save_path}"

    def analyze_cash_flow(
        ticker_symbol: Annotated[str, "ticker_symbol"],
        fyear: Annotated[str, "fiscal year of the 10-K report"],
        save_path: Annotated[str, "txt file path, to which the returned instruction & resources are written."]
    ) -> str:
        """
        Retrieve the cash flow statement for the given ticker_symbol with the related section of its 10-K report.
        Then return with an instruction on how to analyze the cash flow statement.
        """
        # cash_flow = YFinanceUtils.get_cash_flow(ticker_symbol)


        cash_flow, _, _ = FMPUtils.get_financial_metrics(
            ticker_symbol=ticker_symbol,
            years=5
        )

        try:
            cfo_value = cash_flow.loc["CFO", fyear]
            df_string = f"Cash Flow from Operations (CFO) in {fyear}: {cfo_value:,}"
        except KeyError:
            return f"CFO data for year {fyear} not found in financial metrics for {ticker_symbol}."

        instruction = dedent(
            """
            Dive into a comprehensive evaluation of the company's cash flow for the latest fiscal year, focusing on cash inflows 
            and outflows across operating, investing, and financing activities. Examine the operational cash flow to assess the 
            core business profitability, scrutinize investing activities for insights into capital expenditures and investments, 
            and review financing activities to understand debt, equity movements, and dividend policies. Compare these cash movements 
            to prior periods to discern trends, sustainability, and liquidity risks. Conclude with an informed analysis of the company's 
            cash management effectiveness, liquidity position, and potential for future growth or financial challenges in a single paragraph. 
            Less than 130 words.
            """
        )

        section_text = SECUtils.get_10k_section(ticker_symbol, fyear, 7)
        prompt = combine_prompt(instruction, section_text, df_string)
        save_to_file(prompt, save_path)
        return f"instruction & resources saved to {save_path}"

    def analyze_segment_stmt(
        ticker_symbol: Annotated[str, "ticker_symbol"],
        fyear: Annotated[str, "fiscal year of the 10-K report"],
        save_path: Annotated[str, "txt file path, to which the returned instruction & resources are written."]
    ) -> str:
        """
        Retrieve the income statement and the related section of its 10-K report for the given ticker_symbol.
        Then return with an instruction on how to create a segment analysis.
        """
        # income_stmt = YFinanceUtils.get_income_stmt(ticker_symbol

        income_stmt = FMPUtils.get_income_statement(
            ticker_symbol=ticker_symbol,
            period="annual"
        )

        if not isinstance(income_stmt, pd.DataFrame):
            return f"Error: Expected a DataFrame, got {type(income_stmt)} - {income_stmt}"

        # ✅ Ensure 'date' is a column before using it
        if 'date' not in income_stmt.columns:
            income_stmt.reset_index(inplace=True)

        # ✅ Normalize and filter by fiscal year
        income_stmt['date'] = pd.to_datetime(income_stmt['date'])
        income_stmt.set_index('date', inplace=True)

        specific_year_df = income_stmt[income_stmt['fiscalYear'] == int(fyear)]
        if specific_year_df.empty:
            return f"Error: No income statement data found for fiscal year {fyear} for {ticker_symbol}."

        # ✅ Flatten the nested 'data' field
        data_dict = specific_year_df.iloc[0]['data']
        if not isinstance(data_dict, dict):
            return f"Error: Expected a dictionary in 'data' column but got {type(data_dict)}."

        flat_df = pd.DataFrame([data_dict]).T.reset_index()
        flat_df.columns = ['Metric', 'Value']
        df_string = f"Income statement for {fyear}:\n" + flat_df.to_string(index=False)

        instruction = dedent(
            """
            Identify the company's business segments and create a segment analysis using the Management's Discussion and Analysis 
            and the income statement, subdivided by segment with clear headings. Address revenue and net profit with specific data, 
            and calculate the changes. Detail strategic partnerships and their impacts, including details like the companies or organizations. 
            Describe product innovations and their effects on income growth. Quantify market share and its changes, or state market position 
            and its changes. Analyze market dynamics and profit challenges, noting any effects from national policy changes. Include the cost side, 
            detailing operational costs, innovation investments, and expenses from channel expansion, etc. Support each statement with evidence, 
            keeping each segment analysis concise and under 60 words, accurately sourcing information. For each segment, consolidate the most 
            significant findings into one clear, concise paragraph, excluding less critical or vaguely described aspects to ensure clarity and 
            reliance on evidence-backed information. For each segment, the output should be one single paragraph within 150 words.
            """
        )

        section_text = SECUtils.get_10k_section(ticker_symbol, fyear, 7)
        prompt = combine_prompt(instruction, section_text, df_string)
        return f"instruction & resources saved to {save_path}"

    def income_summarization(
        ticker_symbol: Annotated[str, "ticker_symbol"],
        fyear: Annotated[str, "fiscal year of the 10-K report"],
        income_stmt_analysis: Annotated[str, "in-depth income statement analysis"],
        segment_analysis: Annotated[str, "in-depth segment analysis"],
        save_path: Annotated[str, "txt file path, to which the returned instruction & resources are written."]
    ) -> str:
        """
        With the income statement and segment analysis for the given ticker_symbol.
        Then return with an instruction on how to synthesize these analyses into a single coherent paragraph.
        """
        # income_stmt_analysis = analyze_income_stmt(ticker_symbol)
        # segment_analysis = analyze_segment_stmt(ticker_symbol)

        instruction = dedent(
            f"""
            Income statement analysis: {income_stmt_analysis},
            Segment analysis: {segment_analysis},
            Synthesize the findings from the in-depth income statement analysis and segment analysis into a single, coherent paragraph. 
            It should be fact-based and data-driven. First, present and assess overall revenue and profit situation, noting significant 
            trends and changes. Second, examine the performance of the various business segments, with an emphasis on their revenue and 
            profit changes, revenue contributions and market dynamics. For information not covered in the first two areas, identify and 
            integrate key findings related to operation, potential risks and strategic opportunities for growth and stability into the analysis. 
            For each part, integrate historical data comparisons and provide relevant facts, metrics or data as evidence. The entire synthesis 
            should be presented as a continuous paragraph without the use of bullet points. Use subtitles and numbering for each key point. 
            The total output should be less than 160 words.
            """
        )

        section_text = SECUtils.get_10k_section(ticker_symbol, fyear, 7)
        prompt = combine_prompt(instruction, section_text, "")
        save_to_file(prompt, save_path)
        return f"instruction & resources saved to {save_path}"

    def get_risk_assessment(
        ticker_symbol: Annotated[str, "ticker_symbol"],
        fyear: Annotated[str, "fiscal year of the 10-K report"],
        save_path: Annotated[str, "txt file path, to which the returned instruction & resources are written."],
    ) -> str:
        """
        Retrieve the risk factors for the given ticker_symbol with the related section of its 10-K report.
        Then return with an instruction on how to summarize the top 3 key risks of the company.
        """
        # company_name = YFinanceUtils.get_stock_info(ticker_symbol)["shortName"]

        profile_json = FMPUtils.get_company_profile(ticker_symbol=ticker_symbol) # Use the instance's method
        company_name = profile_json.get("name", "N/A")

        risk_factors = SECUtils.get_10k_section(ticker_symbol, fyear, "1A")
        section_text = (
            "Company Name: "
            + company_name
            + "\n\n"
            + "Risk factors:\n"
            + risk_factors
            + "\n\n"
        )
        instruction = (
            """
            According to the given information in the 10-k report, summarize the top 3 key risks of the company. 
            Then, for each key risk, break down the risk assessment into the following aspects:
            1. Industry Vertical Risk: How does this industry vertical compare with others in terms of risk? Consider factors such as regulation, market volatility, and competitive landscape.
            2. Cyclicality: How cyclical is this industry? Discuss the impact of economic cycles on the company’s performance.
            3. Risk Quantification: Enumerate the key risk factors with supporting data if the company or segment is deemed risky.
            4. Downside Protections: If the company or segment is less risky, discuss the downside protections in place. Consider factors such as diversification, long-term contracts, and government regulation.

            Finally, provide a detailed and nuanced assessment that reflects the true risk landscape of the company. And Avoid any bullet points in your response.
            """
        )
        prompt = combine_prompt(instruction, section_text, "")
        save_to_file(prompt, save_path)
        return f"instruction & resources saved to {save_path}"
    
    # removed June 16,25:   fyear: Annotated[str, "fiscal year of the 10-K report"], never used in code    
    def get_competitors_analysis(
        ticker_symbol: Annotated[str, "ticker_symbol"], 
        competitors: Annotated[List[str], "competitors company"],
        save_path: Annotated[str, "txt file path, to which the returned instruction & resources are written."]
    ) -> str:
        """
        Analyze financial metrics differences between a company and its competitors.
        Prepare a prompt for analysis and save it to a file.
        """
        # Retrieve financial data
        financial_data = FMPUtils.get_competitor_financial_metrics(ticker_symbol, competitors, years=4)

        # Construct the financial data summary
        table_str = ""
        for metric in financial_data[ticker_symbol].index:
            table_str += f"\n\n{metric}:\n"
            company_value = financial_data[ticker_symbol].loc[metric]
            table_str += f"{ticker_symbol}: {company_value}\n"
            for competitor in competitors:
                competitor_value = financial_data[competitor].loc[metric]
                table_str += f"{competitor}: {competitor_value}\n"
        # Prepare the instructions for analysis
        instruction = dedent(
          """
          Analyze the financial metrics for {company}/ticker_symbol and its competitors: {competitors} across multiple years (indicated as 0, 1, 2, 3, with 0 being the latest year and 3 the earliest year). Focus on the following metrics: EBITDA Margin, EV/EBITDA, FCF Conversion, Gross Margin, ROIC, Revenue, and Revenue Growth. 
          For each year: Year-over-Year Trends: Identify and discuss the trends for each metric from the earliest year (3) to the latest year (0) for {company}. But when generating analysis, you need to write 1: year 3 = year 2023, 2: year 2 = year 2022, 3: year 1 = year 2021 and 4: year 0 = year 2020. Highlight any significant improvements, declines, or stability in these metrics over time.
          Competitor Comparison: For each year, compare {company} against its {competitors} for each metric. Evaluate how {company} performs relative to its {competitors}, noting where it outperforms or lags behind.
          Metric-Specific Insights:

          EBITDA Margin: Discuss the profitability of {company} compared to its {competitors}, particularly in the most recent year.
          EV/EBITDA: Provide insights on the valuation and whether {company} is over or undervalued compared to its {competitors} in each year.
          FCF Conversion: Evaluate the cash flow efficiency of {company} relative to its {competitors} over time.
          Gross Margin: Analyze the cost efficiency and profitability in each year.
          ROIC: Discuss the return on invested capital and what it suggests about the company's efficiency in generating returns from its investments, especially focusing on recent trends.
          Revenue and Revenue Growth: Provide a comprehensive view of {company}’s revenue performance and growth trajectory, noting any significant changes or patterns.
          Conclusion: Summarize the overall financial health of {company} based on these metrics. Discuss how {company}’s performance over these years and across these metrics might justify or contradict its current market valuation (as reflected in the EV/EBITDA ratio).
          Avoid using any bullet points.
          """
        )

        # Combine the prompt
        company_name = ticker_symbol  # Assuming the ticker_symbol is the company name, otherwise, retrieve it.
        resource = f"Financial metrics for {company_name} and {competitors}."
        prompt = combine_prompt(instruction, resource, table_str)
        save_to_file(prompt, save_path)
        return f"instruction & resources saved to {save_path}"
        
    def analyze_business_highlights(
        ticker_symbol: Annotated[str, "ticker_symbol"],
        fyear: Annotated[str, "fiscal year of the 10-K report"],
        save_path: Annotated[str, "txt file path, to which the returned instruction & resources are written."]
    ) -> str:
        """
        Retrieve the business summary and related section of its 10-K report for the given ticker_symbol.
        Then return with an instruction on how to describe the performance highlights per business of the company.
        """
        business_summary = SECUtils.get_10k_section(ticker_symbol, fyear, 1)
        section_7 = SECUtils.get_10k_section(ticker_symbol, fyear, 7)
        section_text = (
            "Business summary:\n"
            + business_summary
            + "\n\n"
            + "Management's Discussion and Analysis of Financial Condition and Results of Operations:\n"
            + section_7
        )
        instruction = dedent(
            """
            According to the given information, describe the performance highlights for each company's business line.
            Each business description should contain one sentence of a summarization and one sentence of explanation.
            """
        )
        prompt = combine_prompt(instruction, section_text, "")
        save_to_file(prompt, save_path)
        return f"instruction & resources saved to {save_path}"

    def analyze_company_description(
        ticker_symbol: Annotated[str, "ticker_symbol"],
        fyear: Annotated[str, "fiscal year of the 10-K report"],
        save_path: Annotated[str, "txt file path, to which the returned instruction & resources are written."]
    ) -> str:
        """
        Retrieve the company description and related sections of its 10-K report for the given ticker_symbol.
        Then return with an instruction on how to describe the company's industry, strengths, trends, and strategic initiatives.
        """
        #company_name = YFinanceUtils.get_stock_info(ticker_symbol).get(
        #    "shortName", "N/A"
        #)

        profile = FMPUtils.get_company_profile(ticker_symbol=ticker_symbol)
        company_name = profile.get("name") if profile and profile.get("name") else ticker_symbol

        business_summary = SECUtils.get_10k_section(ticker_symbol, fyear, 1)
        section_7 = SECUtils.get_10k_section(ticker_symbol, fyear, 7)
        section_text = (
            "Company Name: "
            + company_name
            + "\n\n"
            + "Business summary:\n"
            + business_summary
            + "\n\n"
            + "Management's Discussion and Analysis of Financial Condition and Results of Operations:\n"
            + section_7
        )
        instruction = dedent(
            """
            According to the given information, 
            1. Briefly describe the company overview and company’s industry, using the structure: "Founded in xxxx, 'company name' is a xxxx that provides .....
            2. Highlight core strengths and competitive advantages key products or services,
            3. Include topics about end market (geography), major customers (blue chip or not), market share for market position section,
            4. Identify current industry trends, opportunities, and challenges that influence the company’s strategy,
            5. Outline recent strategic initiatives such as product launches, acquisitions, or new partnerships, and describe the company's response to market conditions. 
            Less than 300 words.
            """
        )
        prompt = combine_prompt(instruction, section_text, "")
        save_to_file(prompt, save_path)
        return f"instruction & resources saved to {save_path}"

    def get_key_data(
        ticker_symbol: Annotated[str, "ticker_symbol"],
        filing_date: Annotated[str | datetime, "filing date of the financial report"]
    ) -> dict[str, str]:
        """
        Returns key financial data for the given ticker and filing date using only FMP.
        Includes analyst rating, price range, market cap, target price, BVPS, and currency.
        """

        # --- Convert filing_date to datetime ---
        if isinstance(filing_date, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    filing_date_obj = datetime.strptime(filing_date, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Invalid filing_date format: {filing_date}")
        elif isinstance(filing_date, datetime):
            filing_date_obj = filing_date
        elif isinstance(filing_date, date):
            filing_date_obj = datetime(filing_date.year, filing_date.month, filing_date.day)
        else:
            raise TypeError(f"Unsupported type for filing_date: {type(filing_date)}")

        # --- Date ranges ---
        start = (filing_date_obj - timedelta(weeks=52)).strftime("%Y-%m-%d")
        end = filing_date_obj.strftime("%Y-%m-%d")
        six_months_start = (filing_date_obj - timedelta(weeks=26)).strftime("%Y-%m-%d")
        fmp_date_str = end

        # --- Historical market data ---
        hist = FMPUtils.get_stock_data(ticker_symbol, start, end)
        profile = FMPUtils.get_company_profile(ticker_symbol=ticker_symbol)
        currency = profile.get("currency") or profile.get("reportedCurrency")

        if hist.empty:
            close_price = 0.0
            fifty_two_week_low = 0.0
            fifty_two_week_high = 0.0
            avg_daily_volume_6m = 0.0
        else:
            close_price = hist["close"].iloc[-1]
            hist_last_6_months = hist.loc[six_months_start:end]
            avg_daily_volume_6m = hist_last_6_months["volume"].mean() if not hist_last_6_months.empty else 0.0
            fifty_two_week_low = hist["low"].min() if not hist["low"].empty else 0.0
            fifty_two_week_high = hist["high"].max() if not hist["high"].empty else 0.0

        # --- Analyst rating ---
        rating = FMPUtils.get_analyst_rating(ticker_symbol, filing_date_obj)

        # --- Target price ---
        target_price = FMPUtils.get_target_price(ticker_symbol, fmp_date_str)
        if not isinstance(target_price, str) or "403" in target_price:
            target_price = "Failed to retrieve data: 403 or N/A"

        # --- Market cap ---
        market_cap_raw = FMPUtils.get_historical_market_cap(ticker_symbol, fmp_date_str)

        market_cap_formatted = "0.00"  # Default value

        if isinstance(market_cap_raw, str):
            match = re.search(r'(\d{1,3}(?:,\d{3})+(?:\.\d+)?)', market_cap_raw)
            market_cap_value = float(match.group(0).replace(",", ""))
            market_cap_formatted = f"{market_cap_value / 1e6:.2f}"  # Convert to millions

        # --- Book Value Per Share (BVPS) ---
        bvps_raw = FMPUtils.get_historical_bvps(ticker_symbol, fmp_date_str)
        bvps_formatted = "N/A"
        if isinstance(bvps_raw, (int, float)):
            bvps_formatted = f"{bvps_raw:.2f}"
        elif isinstance(bvps_raw, str):
            match = re.search(r'[\d,\.]+', bvps_raw)
            if match:
                try:
                    bvps_value = float(match.group(0).replace(",", ""))
                    bvps_formatted = f"{bvps_value:.2f}"
                except Exception:
                    pass

        # --- Assemble result ---
        suffix = f"({currency})" if currency else ""
        suffix_mn = f"({currency}mn)" if currency else ""

        return {
            "Rating": rating,
            "Target Price": target_price,
            "Currency": currency or "N/A",
            f"6m avg daily vol {suffix_mn}": f"{avg_daily_volume_6m / 1e6:.2f}",
            f"Closing Price {suffix}": f"{close_price:.2f}",
            f"Market Cap {suffix_mn}": market_cap_formatted,
            f"52 Week Price Range {suffix}": f"{fifty_two_week_low:.2f} - {fifty_two_week_high:.2f}",
            f"BVPS {suffix}": bvps_formatted,
        }


if __name__ == "__main__":
    from functional.utils import register_keys_from_json
    # Corrected path for direct execution from finrobot/data_source
    register_keys_from_json(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config_api_keys.json'))) # Ensure .json extension

    save_dir = "D:/dev/FinRobot-CoT/report/test_outputs"
    os.makedirs(save_dir, exist_ok=True)

    TEST_TICKER = "MSFT"
    TEST_YEAR = "2024"


    """try:
        print(ReportAnalysisUtils.analyze_income_stmt(TEST_TICKER, TEST_YEAR, f"{save_dir}/{TEST_TICKER}_income.txt"))
    except Exception as e:
        print("❌ analyze_income_stmt failed:", str(e))

    try:
        print(ReportAnalysisUtils.analyze_balance_sheet(TEST_TICKER, TEST_YEAR, f"{save_dir}/{TEST_TICKER}_balance.txt"))
    except Exception as e:
        print("❌ analyze_balance_sheet failed:", str(e))

    try:
        print(ReportAnalysisUtils.analyze_cash_flow(TEST_TICKER, TEST_YEAR, f"{save_dir}/{TEST_TICKER}_cash.txt"))
    except Exception as e:
        print("❌ analyze_cash_flow failed:", str(e))

    try:
        print(ReportAnalysisUtils.analyze_segment_stmt(TEST_TICKER, TEST_YEAR, f"{save_dir}/{TEST_TICKER}_segment.txt"))
    except Exception as e:
        print("❌ analyze_segment_stmt failed:", str(e))

    try:
        print(ReportAnalysisUtils.analyze_business_highlights(TEST_TICKER, TEST_YEAR, f"{save_dir}/{TEST_TICKER}_highlights.txt"))
    except Exception as e:
        print("❌ analyze_business_highlights failed:", str(e))

    try:
        print(ReportAnalysisUtils.analyze_company_description(TEST_TICKER, TEST_YEAR, f"{save_dir}/{TEST_TICKER}_company.txt"))
    except Exception as e:
        print("❌ analyze_company_description failed:", str(e))

    try:
        print(ReportAnalysisUtils.get_risk_assessment(TEST_TICKER, TEST_YEAR, f"{save_dir}/{TEST_TICKER}_risk.txt"))
    except Exception as e:
        print("❌ get_risk_assessment failed:", str(e))"""

    try:
        competitors_list = ["AAPL", "GOOGL"]  # example list; replace as needed
        print(
            ReportAnalysisUtils.get_competitors_analysis(
                TEST_TICKER,
                competitors_list,
                f"{save_dir}/{TEST_TICKER}_competitor_analysis.txt"
            )
        )
    except Exception as e:
        print("❌ get_competitors_analysis failed:", str(e))
        

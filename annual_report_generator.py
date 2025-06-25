# annual_report_generator.py

import os
import sys
import argparse
import asyncio
import logging
import time
import uuid
from textwrap import dedent
from pathlib import Path
import aiohttp
from agents.agent_pipeline import CoTPipeline

# Core logging/events
from event_logger import (
    setup_logging,
    pipeline_run,
    agent_run,
    log_agent_setup,
    log_pipeline_error,
    log_pipeline_end,
    log_llm_metrics,
)

from functional.utils import register_keys_from_json
from data_source import FMPUtils

os.environ["PYTHONIOENCODING"] = "utf-8"
project_root = os.path.abspath(".")
sys.path.append(project_root)
WORK_DIR = os.path.join(project_root, "report")
os.makedirs(WORK_DIR, exist_ok=True)

# --- Logging setup
setup_logging()
app_logger = logging.getLogger("FinRobot")
app_logger.info("FinRobot Annual Report Generator starting up.")

# --- Model selection logic (same as before)
available_models = {
    0: "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
    1: "gpt-4.1-mini-2025-04-14",
    2: "gpt-4.1-nano-2025-04-14",
    3: "mistralai/Mistral-7B-Instruct-v0.2",
    4: "Qwen/Qwen3-235B-A22B-fp8-tput",
    5: "gpt-4.1-2025-04-14",
    6: "deepseek-ai/DeepSeek-V3"
}
model_choice = 6
default_model = available_models[model_choice]

# CLI model selection
parser = argparse.ArgumentParser(description="Run FinRobot analysis for a single company.")
parser.add_argument("company", help="Company name or ticker to analyze")
parser.add_argument("--year", default="2024", help="Financial year to analyze (default: 2024)")
parser.add_argument("--verbose", action="store_true", help="Enable verbose logging for debugging")
parser.add_argument("--target_model", default="gpt-4.1-nano-2025-04-14", help="LLM model used by Agents")
parser.add_argument("--report_type", default="kpi_bullet_insights", help="Type of report to generate")
args = parser.parse_args()

target_model = args.target_model if args.target_model in available_models.values() else default_model
app_logger.info(f"Using target model: {target_model}")


# --- LLM config loading (same as before, log errors structurally)
try:
    import autogen
    config_list = autogen.config_list_from_json(
        os.path.join(project_root, "OAI_CONFIG_LIST.json"),
        filter_dict={"model": target_model}
    )
    if not config_list:
        log_pipeline_error("No configurations found for target model", model=target_model)
    else:
        app_logger.info(f"LLM config loaded for model: {target_model}")
except Exception as e:
    log_pipeline_error("Error loading OAI_CONFIG_LIST.json", error=str(e))
    sys.exit(1)
llm_config = {
    "config_list": config_list,
    "timeout": 60,
    "temperature": 0.4,
    "max_tokens": 4096,
    "cache_seed": None
}

# --- API Keys (with error logging)
try:
    register_keys_from_json(os.path.join(project_root, "config_api_keys.json"))
    app_logger.info("API keys loaded successfully.")
except Exception as e:
    log_pipeline_error("Failed to register API keys", error=str(e))
    sys.exit(2)

def default_hook(event_type, data):
    # Replace with a Flask, SSE, or websocket emitter in your web context.
    pass

   
async def process_company_with_analysis(
    company_query: str,
    analysis_year: str,
    hook_callback=default_hook
):
    with pipeline_run(query=company_query, custom_data={"year": analysis_year}) as (run_id, log_end_pipeline, log_error_pipeline):
        result = {"run_id": run_id}

        # Step 1 - Company + Peers resolution
        resolver_inputs = {"query": company_query}
        with agent_run(run_id=run_id, agent_id="company_resolver_1", agent_name="CompanyResolver", inputs=resolver_inputs) as (log_end_resolver, log_error_resolver):
            company_info = await resolve_company_and_peers(company_query)
            if company_info.get("error_message"):
                result.update(company_info)
                if hook_callback:
                    hook_callback("error", {"stage": "resolve_company", "error": result["error_message"]})
                log_error_resolver(error=result["error_message"])
                raise ValueError(result["error_message"])
            log_end_resolver(output=company_info)
            if hook_callback:
                hook_callback("company_resolved", company_info)

        result.update(company_info)

        # Step 2 - Pipeline (CoT)
        region = company_info.get("region", "US")
        pipeline = CoTPipeline(region=region)
        pipeline_input = {
            "ticker_symbol": company_info["ticker"],
            "fyear": analysis_year,
            'region': region,
            "work_dir": WORK_DIR,
            "run_id": run_id,
        }
        with agent_run(run_id, "cot_pipeline", "CoTPipeline", pipeline_input) as (log_end, log_error):
            pipeline_result = pipeline.run(pipeline_input)
            log_end(output=pipeline_result)
            if hook_callback:
                hook_callback("pipeline_complete", {"result": pipeline_result})

        result.update({
            "status": "analysis_completed" if pipeline_result else "analysis_failed",
            "chat_summary": pipeline_result.get("summary", "Analysis skipped or incomplete"),
            "chat_history": pipeline_result.get("history", []) if pipeline_result else [],
        })
        log_end_pipeline(result["chat_summary"])
        return result


async def resolve_company_and_peers(company_query: str):
    """New helper function to contain company resolution logic."""
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    YAHOO_FINANCE_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"

    result = {}

    if not company_query or not isinstance(company_query, str):
        return {"status": "company_not_found", "error_message": "Empty or invalid company query"}

    try:
        async with aiohttp.ClientSession(headers={"User-Agent": DEFAULT_USER_AGENT}) as session:
            async with session.get(f"{YAHOO_FINANCE_SEARCH_URL}?q={company_query.strip()}", timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
    except Exception as e:
        return {"status": "company_not_found", "error_message": f"Yahoo Finance API error: {e}"}

    quotes = data.get("quotes", [])
    if not quotes:
        return {"status": "company_not_found", "error_message": f"No company found for: {company_query}"}
    
    top = quotes[0]
    official_name = top.get("longname") or top.get("shortname") or top.get("symbol")
    ticker = top.get("symbol")
    exchange = top.get("exchange")

    if not ticker or not official_name:
        return {"status": "company_not_found", "error_message": "Missing ticker or official name"}
    
    indian_exchanges = ("NSE", "BSE", "IND")
    us_exchanges = ("NMS", "NYQ", "PCX", "NAS", "ASE", "NYSE", "NASDAQ")
    region = "IN" if (ticker.endswith((".NS", ".BO")) or exchange in indian_exchanges) else "US" if exchange in us_exchanges else "Unknown"

    try:
        raw_peers = FMPUtils.get_company_peers(symbol=ticker)
        # Simplified peer fetching for brevity
        filtered_peers = [{"name": p, "ticker": p} for p in raw_peers[:3] if p != ticker]
    except Exception as e:
        app_logger.warning(f"Could not fetch peers for {ticker}: {e}")
        filtered_peers = []
    
    result.update({
        "official_name": official_name, "ticker": ticker, "exchange": exchange, "region": region,
        "competitors": filtered_peers, "status": "company_found", "error_message": None,
    })
    return result


# --- CLI Main Entry Point ---
if __name__ == "__main__":
    import traceback
    try:
        result = asyncio.run(
            process_company_with_analysis(
                company_query=args.company.strip(),
                analysis_year=args.year.strip(),
                hook_callback=default_hook
            )
        )
        status = result.get("status", "")
        summary = result.get("chat_summary", "")
        run_id = result.get("run_id")
        if status in ["company_not_found", "analysis_failed"]:
            app_logger.error(f"Pipeline run {run_id} failed with status: {status}. Error: {result.get('error_message')}")
            sys.exit(1)
        app_logger.info(f"✅ Pipeline run {run_id} completed successfully.")
        if summary:
            app_logger.info("\nFinal Summary:\n" + "-" * 60 + f"\n{summary}\n" + "-" * 60)
    except Exception as e:
        app_logger.critical(f"Unhandled error during execution: {e}", exc_info=True)
        traceback.print_exc()
        sys.exit(99)
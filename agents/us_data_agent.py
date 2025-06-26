import os
import time
import inspect

from data_source.report_analysis_utils import ReportAnalysisUtils
from data_source.report_chart_utils import ReportChartUtils
from .agent_base import AgentBase
import event_logger
from llm_evaluation import llm_judge_explanation, llm_should_retry, generate_placeholder_summary, classify_hallucination_type


def call_with_rate_limit_handling(api_call_fn, max_retries=3, backoff_factor=2):
    for attempt in range(max_retries):
        response = api_call_fn()
        if isinstance(response, dict) and response.get("status") == 429:
            wait_time = backoff_factor ** attempt
            print(f"Rate limit hit. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
        else:
            return response
    return {"error": "Max retries exceeded due to rate limiting."}


def discover_tools():
    tool_registry = {}

    # From ReportAnalysisUtils
    for name, fn in inspect.getmembers(ReportAnalysisUtils, predicate=inspect.isfunction):
        if name.startswith("analyze_") or name.startswith("get_"):
            tool_registry[name] = fn

    # From ReportChartUtils
    def wrap_chart_tool(fn):
        sig = inspect.signature(fn)

        def wrapper(ticker, report_date, output_file):
            kwargs = {}
            for param in sig.parameters:
                if param in ["ticker", "ticker_symbol"]:
                    kwargs[param] = ticker
                elif param in ["fyear", "date", "filing_date"]:
                    kwargs[param] = report_date
                elif param in ["output_file", "save_path"]:
                    kwargs[param] = output_file
            return fn(**kwargs)

        wrapper.__name__ = fn.__name__
        return wrapper

    for name, fn in inspect.getmembers(ReportChartUtils, predicate=inspect.isfunction):
        if name.startswith("get_"):
            tool_registry[name] = wrap_chart_tool(fn)

    return tool_registry


class DataCoTAgentUS(AgentBase):
    def run(self, input_data, run_id=None, agent_id=None, stage: str = ""):
        agent_name = self.name
        if agent_id is None:
            agent_id = f"{agent_name}-{int(time.time()*1000)}"

        t_start = time.time()
        event_logger.log_agent_start(run_id, agent_id, agent_name, {"input_data": input_data, "stage": stage})

        ticker = input_data.get('ticker_symbol', 'UNKNOWN')
        fyear = input_data.get('fyear', '2024')
        work_dir = input_data.get('work_dir', './report')
        os.makedirs(work_dir, exist_ok=True)

        tool_registry = discover_tools()

        report_date = f"{fyear}-12-31" 

        outputs = [
            {"name": "Income Statement",      "tool": tool_registry["analyze_income_stmt"],         "output_file": "01_income_statement.txt",      "type": "txt"},
            {"name": "Balance Sheet",         "tool": tool_registry["analyze_balance_sheet"],        "output_file": "02_balance_sheet.txt",         "type": "txt"},
            {"name": "Cash Flow",             "tool": tool_registry["analyze_cash_flow"],            "output_file": "03_cash_flow.txt",             "type": "txt"},
            {"name": "Risk Analysis",         "tool": tool_registry["analyze_segment_stmt"],         "output_file": "04_risk_analysis.txt",         "type": "txt"},
            {"name": "Competitor Analysis",   "tool": tool_registry["get_competitors_analysis"],      "output_file": "05_competitor_analysis.txt",   "type": "txt"},
            {"name": "Business Highlights",   "tool": tool_registry["analyze_business_highlights"],   "output_file": "06_business_highlights.txt",   "type": "txt"},
            {"name": "Company Description",   "tool": tool_registry["analyze_company_description"],   "output_file": "07_company_description.txt",   "type": "txt"},
            {"name": "PE/EPS Chart",          "tool": tool_registry["get_pe_eps_performance"],       "output_file": "pe_eps_performance.png",       "type": "img"},
            {"name": "Share Price Chart",     "tool": tool_registry["get_share_performance"],        "output_file": "share_price_performance.png",  "type": "img"}
        ]

        validated_files = []
        failed_calls = []
        hallucinations = []
        tool_stats = []
        generated_files_registry = set()

        for output in outputs:
            fname = output["output_file"]
            fpath = os.path.join(work_dir, fname)
            tool_call = output["tool"]
            tool_name = tool_call.__name__
            tool_input = {"ticker": ticker, "fyear": fyear, "output_file": fpath}

            if fpath in generated_files_registry:
                halluc_type = "duplicate_output"
                reason = f"File written multiple times: {fpath}"
                hallucinations.append(reason)
                event_logger.log_hallucination_metric(run_id, 0.0, reason, {"agent": agent_name, "tool": tool_name, "type": halluc_type})
                continue
            generated_files_registry.add(fpath)

            event_logger.log_tool_call(run_id, agent_name, tool_name, tool_input)
            t0 = time.time()
            success = False
            try:
                result = call_with_rate_limit_handling(lambda: tool_call(ticker, report_date, fpath))
                elapsed = (time.time() - t0) * 1000

                if output["type"] == 'txt':
                    if os.path.exists(fpath) and os.path.getsize(fpath) > 3:
                        validated_files.append(fpath)
                        success = True
                    else:
                        decision = llm_should_retry(tool_name, f"Empty or missing file: {fpath}")
                        if decision == "retry":
                            tool_call(ticker, fyear, fpath)
                        elif decision == "switch":
                            content = generate_placeholder_summary(output["name"], ticker)
                            with open(fpath, 'w', encoding='utf-8') as f:
                                f.write(content)
                        failed_calls.append(fname)
                        halluc_type = classify_hallucination_type(fname, tool_name, "invalid_text_output")
                        hallucinations.append(f"{tool_name} failed: {halluc_type}")
                        event_logger.log_hallucination_metric(run_id, 0.0, f"Missing or invalid file {fname}", {"agent": agent_name, "tool": tool_name, "type": halluc_type})
                else:
                    if os.path.exists(fpath) and os.path.getsize(fpath) > 10 * 1024:
                        validated_files.append(fpath)
                        success = True
                    else:
                        failed_calls.append(fname)
                        halluc_type = classify_hallucination_type(fname, tool_name, "invalid_image")
                        hallucinations.append(f"{tool_name} failed: {halluc_type}")
                        event_logger.log_hallucination_metric(run_id, 0.0, f"Missing or invalid image {fname}", {"agent": agent_name, "tool": tool_name, "type": halluc_type})

            except Exception as e:
                elapsed = (time.time() - t0) * 1000
                failed_calls.append(fname)
                halluc_type = classify_hallucination_type(fname, tool_name, "tool_crash")
                hallucinations.append(str(e))
                event_logger.log_tool_result(run_id, agent_name, tool_name, str(e), False, elapsed)
                event_logger.log_hallucination_metric(run_id, 0.0, f"Tool call exception: {e}", {"agent": agent_name, "tool": tool_name, "type": halluc_type})
                continue

            event_logger.log_tool_result(run_id, agent_name, tool_name, {"file": fpath}, success, elapsed)
            tool_stats.append({"tool": tool_name, "file": fpath, "valid": success, "latency_ms": elapsed})

        t_end = time.time()
        total_time = (t_end - t_start) * 1000
        event_logger.log_llm_metrics(run_id, agent_name, "N/A", tokens=0, cost=0.0, latency_ms=total_time)

        reasoning_summary = llm_judge_explanation(hallucinations, context="tool_failures") if hallucinations else "All tools succeeded."
        event_logger.log_evaluation_metric(run_id, "Tool Failure Analysis", 1.0 if not hallucinations else 0.0, reasoning_summary)

        agent_output = {
            "validated_files": validated_files,
            "failed_files": failed_calls,
            "hallucinations": hallucinations,
            "tool_stats": tool_stats,
            "status": "TERMINATE" if len(validated_files) == len(outputs) else "FAILED"
        }
        event_logger.log_agent_end(run_id, agent_id, agent_name, agent_output, total_time)
        return agent_output





if __name__ == "__main__":
    import pprint
    agent = DataCoTAgentUS(name="Data_CoT_Agent_US")

    input_data = {
        "ticker_symbol": "AAPL",
        "fyear": "2023",
        "work_dir": "./tmp_test_reports"
    }

    result = agent.run(input_data=input_data, run_id="test_run_001")
    pprint.pprint(result)
from data_source.report_analysis_utils import ReportAnalysisUtilsIN
from data_source.report_chart_utils import ReportChartUtilsIN
from .agent_base import AgentBase
import os
import time
import event_logger
from llm_evaluation import llm_should_retry, generate_placeholder_summary, classify_hallucination_type, llm_judge_explanation


def call_with_rate_limit_handling(api_call_fn, max_retries=3, backoff_factor=2):
    for attempt in range(max_retries):
        try:
            response = api_call_fn()
            if isinstance(response, dict) and "status" in response and response["status"] == 429:
                wait_time = backoff_factor ** attempt
                print(f"Rate limit hit. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                return response
        except Exception as e:
            if "429" in str(e):
                wait_time = backoff_factor ** attempt
                print(f"Rate limit exception. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise e
    return {"error": "Max retries exceeded due to rate limiting."}


class DataCoTAgentIN(AgentBase):
    def run(self, input_data, run_id=None, agent_id=None, stage: str = ""):
        agent_name = self.name
        if agent_id is None:
            agent_id = f"{agent_name}-{int(time.time()*1000)}"
        t_agent_start = time.time()
        event_logger.log_agent_start(run_id, agent_id, agent_name, {"input_data": input_data, "stage": stage})

        ticker = input_data.get('ticker_symbol', 'UNKNOWN')
        fyear = input_data.get('fyear', '2024')
        work_dir = input_data.get('work_dir', './report')
        os.makedirs(work_dir, exist_ok=True)

        outputs = [
            ("01_income_statement.txt", 'txt', lambda: ReportAnalysisUtilsIN.analyze_income_stmt(ticker, fyear, f"{work_dir}/01_income_statement.txt")),
            ("02_balance_sheet.txt", 'txt', lambda: ReportAnalysisUtilsIN.analyze_balance_sheet(ticker, fyear, f"{work_dir}/02_balance_sheet.txt")),
            ("03_cash_flow.txt", 'txt', lambda: ReportAnalysisUtilsIN.analyze_cash_flow(ticker, fyear, f"{work_dir}/03_cash_flow.txt")),
            ("04_risk_analysis.txt", 'txt', lambda: ReportAnalysisUtilsIN.get_risk_assessment(ticker, fyear, f"{work_dir}/04_risk_analysis.txt")),
            ("05_competitor_analysis.txt", 'txt', lambda: ReportAnalysisUtilsIN.get_competitors_analysis(ticker, [], f"{work_dir}/05_competitor_analysis.txt")),
            ("06_business_highlights.txt", 'txt', lambda: ReportAnalysisUtilsIN.analyze_business_highlights(ticker, fyear, f"{work_dir}/06_business_highlights.txt")),
            ("07_company_description.txt", 'txt', lambda: ReportAnalysisUtilsIN.analyze_company_description(ticker, fyear, f"{work_dir}/07_company_description.txt")),
            ("pe_eps_performance.png", 'png', lambda: ReportChartUtilsIN.get_pe_eps_performance(ticker, f"{fyear}-01-01", 4, f"{work_dir}/pe_eps_performance.png")),
            ("share_price_performance.png", 'png', lambda: ReportChartUtilsIN.get_share_performance(ticker, f"{fyear}-01-01", f"{work_dir}/share_price_performance.png")),
        ]

        validated_files = []
        hallucinations = []
        failed_calls = []
        tool_stats = []
        generated_files_registry = set()

        for fname, ftype, tool_call in outputs:
            fpath = f"{work_dir}/{fname}"
            tool_name = tool_call.__name__ if hasattr(tool_call, '__name__') else str(tool_call)

            if fpath in generated_files_registry:
                halluc_type = "duplicate_output"
                reason = f"File written multiple times: {fpath}"
                hallucinations.append(reason)
                event_logger.log_hallucination_metric(run_id, 0.0, reason, {"agent": agent_name, "tool": tool_name, "type": halluc_type})
                continue
            generated_files_registry.add(fpath)

            event_logger.log_tool_call(run_id, agent_name, tool_name, {"output_file": fpath})
            t_tool = time.time()
            try:
                call_with_rate_limit_handling(tool_call)
                elapsed = (time.time() - t_tool) * 1000
                success = False
                if ftype == 'txt':
                    if os.path.exists(fpath) and os.path.getsize(fpath) > 3:
                        validated_files.append(fpath)
                        success = True
                    else:
                        decision = llm_should_retry(tool_name, f"Empty or missing file: {fpath}")
                        if decision == "retry":
                            call_with_rate_limit_handling(tool_call)
                        elif decision == "switch":
                            content = generate_placeholder_summary(fname, ticker)
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

                event_logger.log_tool_result(run_id, agent_name, tool_name, {"output_file": fpath}, success, elapsed)
            except Exception as e:
                elapsed = (time.time() - t_tool) * 1000
                failed_calls.append(fname)
                halluc_type = classify_hallucination_type(fname, tool_name, "tool_crash")
                hallucinations.append(str(e))
                event_logger.log_tool_result(run_id, agent_name, tool_name, f"exception: {e}", False, elapsed)
                event_logger.log_hallucination_metric(run_id, 0.0, f"Tool call exception: {e}", {"agent": agent_name, "tool": tool_name, "type": halluc_type})

        total_time = (time.time() - t_agent_start) * 1000
        event_logger.log_llm_metrics(run_id, agent_name, "N/A", tokens=0, cost=0.0, latency_ms=total_time)

        reasoning_summary = llm_judge_explanation(hallucinations, context="tool_failures") if hallucinations else "All tools succeeded."
        event_logger.log_evaluation_metric(run_id, "Tool Failure Analysis", 1.0 if not hallucinations else 0.0, reasoning_summary)

        agent_output = {
            "created_files": validated_files,
            "hallucinations": hallucinations,
            "failed_files": failed_calls,
            "tool_stats": tool_stats,
            "status": "TERMINATE" if len(validated_files) == len(outputs) else "FAILED"
        }
        event_logger.log_agent_end(run_id, agent_id, agent_name, agent_output, total_time)
        return agent_output

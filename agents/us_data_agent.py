from data_source.report_analysis_utils import ReportAnalysisUtils
from data_source.report_chart_utils import ReportChartUtils
from .agent_base import AgentBase
import os
import time
import event_logger

class DataCoTAgentUS(AgentBase):
    def run(self, input_data, run_id=None, agent_id=None, stage: str = ""):
        agent_name = self.name
        # If agent_id not given, create one (for log traceability)
        if agent_id is None:
            agent_id = f"{agent_name}-{int(time.time()*1000)}"

        # --- Agent Start Logging ---
        t_start = time.time()
        event_logger.log_agent_start(run_id, agent_id, agent_name, {"input_data": input_data, "stage": stage})

        ticker = input_data.get('ticker_symbol', 'UNKNOWN')
        fyear = input_data.get('fyear', '2024')
        work_dir = input_data.get('work_dir', './report')
        os.makedirs(work_dir, exist_ok=True)
        outputs = [
            ('01_income_statement.txt', 'txt', lambda: ReportAnalysisUtils.analyze_income_stmt(ticker, fyear, f"{work_dir}/01_income_statement.txt")),
            ('02_balance_sheet.txt', 'txt', lambda: ReportAnalysisUtils.analyze_balance_sheet(ticker, fyear, f"{work_dir}/02_balance_sheet.txt")),
            ('03_cash_flow.txt', 'txt', lambda: ReportAnalysisUtils.analyze_cash_flow(ticker, fyear, f"{work_dir}/03_cash_flow.txt")),
            ('04_risk_analysis.txt', 'txt', lambda: ReportAnalysisUtils.get_risk_assessment(ticker, fyear, f"{work_dir}/04_risk_analysis.txt")),
            ('05_competitor_analysis.txt', 'txt', lambda: ReportAnalysisUtils.get_competitors_analysis(ticker, [], f"{work_dir}/05_competitor_analysis.txt")),
            ('06_business_highlights.txt', 'txt', lambda: ReportAnalysisUtils.analyze_business_highlights(ticker, fyear, f"{work_dir}/06_business_highlights.txt")),
            ('07_company_description.txt', 'txt', lambda: ReportAnalysisUtils.analyze_company_description(ticker, fyear, f"{work_dir}/07_company_description.txt")),
            ('pe_eps_performance.png', 'png', lambda: ReportChartUtils.get_pe_eps_performance(ticker, f"{fyear}-01-01", 4, f"{work_dir}/pe_eps_performance.png")),
            ('share_price_performance.png', 'png', lambda: ReportChartUtils.get_share_performance(ticker, f"{fyear}-01-01", f"{work_dir}/share_price_performance.png")),
        ]
        validated_files = []
        failed_calls = []
        hallucinations = []
        tool_stats = []

        for fname, ftype, tool_call in outputs:
            fpath = os.path.join(work_dir, fname)
            tool_name = tool_call.__name__ if hasattr(tool_call, '__name__') else str(tool_call)
            tool_input = {"ticker": ticker, "fyear": fyear, "output_file": fpath}

            # --- Tool Call Log ---
            event_logger.log_tool_call(run_id, agent_name, tool_name, tool_input)
            t0 = time.time()
            success = False
            tool_result = None
            try:
                tool_call()
                elapsed = (time.time() - t0) * 1000
                # --- Output Validation ---
                valid = False
                if ftype == 'txt':
                    if os.path.exists(fpath) and os.path.getsize(fpath) > 3:
                        validated_files.append(fpath)
                        valid = True
                        success = True
                    else:
                        failed_calls.append(fname)
                        reason = f"File too short or missing: {fpath}"
                        event_logger.log_hallucination(run_id, agent_name, tool_name, reason, stage)
                        hallucinations.append(reason)
                else:
                    if os.path.exists(fpath) and os.path.getsize(fpath) > 10 * 1024:
                        validated_files.append(fpath)
                        valid = True
                        success = True
                    else:
                        failed_calls.append(fname)
                        reason = f"Image too small or missing: {fpath}"
                        event_logger.log_hallucination(run_id, agent_name, tool_name, reason, stage)
                        hallucinations.append(reason)
                tool_result = {"file": fpath, "valid": valid}
            except Exception as e:
                elapsed = (time.time() - t0) * 1000
                failed_calls.append(fname)
                reason = f"Tool call exception: {e}"
                event_logger.log_tool_result(run_id, agent_name, tool_name, str(e), False, elapsed)
                event_logger.log_hallucination(run_id, agent_name, tool_name, reason, stage)
                hallucinations.append(reason)
                tool_result = {"file": fpath, "exception": str(e), "valid": False}
                continue

            # --- Tool Result Log ---
            event_logger.log_tool_result(run_id, agent_name, tool_name, tool_result, success, elapsed)
            tool_stats.append({
                "tool": tool_name, "file": fpath, "valid": success, "latency_ms": elapsed
            })

        t_end = time.time()
        total_time = (t_end - t_start) * 1000

        # --- LLM Metrics & Agent End ---
        # (Here, you might log model/cost tokens if this agent called an LLM)
        # For tool-only agents, log stats as a proxy.
        event_logger.log_llm_metrics(run_id, agent_name, "N/A", tokens=0, cost=0.0, latency_ms=total_time)

        agent_output = {
            "validated_files": validated_files,
            "failed_files": failed_calls,
            "hallucinations": hallucinations,
            "tool_stats": tool_stats,
            "status": "TERMINATE" if len(validated_files) == len(outputs) else "FAILED"
        }
        event_logger.log_agent_end(run_id, agent_id, agent_name, agent_output, total_time)
        return agent_output

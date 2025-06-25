# in_data_agent.py

from data_source.report_analysis_utils import ReportAnalysisUtilsIN
from data_source.report_chart_utils import ReportChartUtilsIN
from .agent_base import AgentBase
import os
import time
import event_logger

class DataCoTAgentIN(AgentBase):
    def run(self, input_data, run_id=None, agent_id=None, stage: str = ""):
        agent_name = self.name
        if agent_id is None:
            agent_id = f"{agent_name}-{int(time.time()*1000)}"
        t_agent_start = time.time()
        event_logger.log_agent_start(run_id, agent_id, agent_name, {"input_data": input_data, "stage": stage})

        print(f"[{self.name}] Gathering India data for {input_data}")
        ticker = input_data.get('ticker_symbol', 'UNKNOWN')
        fyear = input_data.get('fyear', '2024')
        work_dir = input_data.get('work_dir', './report')
        os.makedirs(work_dir, exist_ok=True)
        outputs = [
            ('01_income_statement.txt', 'txt', lambda: ReportAnalysisUtilsIN.analyze_income_stmt(ticker, fyear, f"{work_dir}/01_income_statement.txt")),
            ('02_balance_sheet.txt', 'txt', lambda: ReportAnalysisUtilsIN.analyze_balance_sheet(ticker, fyear, f"{work_dir}/02_balance_sheet.txt")),
            ('03_cash_flow.txt', 'txt', lambda: ReportAnalysisUtilsIN.analyze_cash_flow(ticker, fyear, f"{work_dir}/03_cash_flow.txt")),
            ('04_risk_analysis.txt', 'txt', lambda: ReportAnalysisUtilsIN.get_risk_assessment(ticker, fyear, f"{work_dir}/04_risk_analysis.txt")),
            ('05_competitor_analysis.txt', 'txt', lambda: ReportAnalysisUtilsIN.get_competitors_analysis(ticker, [], f"{work_dir}/05_competitor_analysis.txt")),
            ('06_business_highlights.txt', 'txt', lambda: ReportAnalysisUtilsIN.analyze_business_highlights(ticker, fyear, f"{work_dir}/06_business_highlights.txt")),
            ('07_company_description.txt', 'txt', lambda: ReportAnalysisUtilsIN.analyze_company_description(ticker, fyear, f"{work_dir}/07_company_description.txt")),
            ('pe_eps_performance.png', 'png', lambda: ReportChartUtilsIN.get_pe_eps_performance(ticker, f"{fyear}-01-01", 4, f"{work_dir}/pe_eps_performance.png")),
            ('share_price_performance.png', 'png', lambda: ReportChartUtilsIN.get_share_performance(ticker, f"{fyear}-01-01", f"{work_dir}/share_price_performance.png")),
        ]
        validated_files = []
        hallucinations = []
        for fname, ftype, tool_call in outputs:
            tool_name = tool_call.__name__ if hasattr(tool_call, '__name__') else str(tool_call)
            fpath = f"{work_dir}/{fname}"
            event_logger.log_tool_call(run_id, agent_name, tool_name, {"output_file": fpath})
            t_tool = time.time()
            try:
                tool_call()
                elapsed = (time.time() - t_tool) * 1000
                success = False
                if ftype == 'txt':
                    if os.path.exists(fpath) and os.path.getsize(fpath) > 3:
                        print(f"  - Validated {fpath}")
                        validated_files.append(fpath)
                        success = True
                    else:
                        print(f"  - Validation failed for {fpath} (text file too short or missing)")
                        hallucinations.append(fname)
                else:
                    if os.path.exists(fpath) and os.path.getsize(fpath) > 10 * 1024:
                        print(f"  - Validated {fpath} (image > 10KB)")
                        validated_files.append(fpath)
                        success = True
                    else:
                        print(f"  - Validation failed for {fpath} (image too small or missing)")
                        hallucinations.append(fname)
                event_logger.log_tool_result(run_id, agent_name, tool_name, {"output_file": fpath}, success, elapsed)
                if not success:
                    event_logger.log_hallucination(
                        run_id, agent_name, tool_name,
                        f"Validation failed or missing for {fpath}", stage
                    )
            except Exception as e:
                elapsed = (time.time() - t_tool) * 1000
                event_logger.log_tool_result(run_id, agent_name, tool_name, f"exception: {e}", False, elapsed)
                event_logger.log_hallucination(
                    run_id, agent_name, tool_name, str(e), stage
                )
                print(f"  - Tool failed for {fpath}: {e}")

        total_time = (time.time() - t_agent_start) * 1000
        # Log LLM metrics for standardization; no actual LLM call in this agent
        event_logger.log_llm_metrics(run_id, agent_name, "N/A", tokens=0, cost=0.0, latency_ms=total_time)
        agent_output = {
            "created_files": validated_files,
            "hallucinations": hallucinations,
            "status": "TERMINATE" if len(validated_files) == len(outputs) else "FAILED"
        }
        event_logger.log_agent_end(run_id, agent_id, agent_name, agent_output, total_time)
        return agent_output

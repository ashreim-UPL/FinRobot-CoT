import os
import time
from .agent_base import AgentBase
from functional.text import TextUtils   # Adjust if needed
from functional.report_writer import ReportLabUtils   # Adjust if needed
import event_logger

class ThesisCoTAgent(AgentBase):
    SECTION_TO_FILENAME = {
        "business_overview": "company_overview",
        "key_financials": "key_financials",
        "valuation": "valuation",
        "risk_assessment": "risks",
        "sell_side_summary": "sell_side_summary",
        "competitor_comparison": "competitor_comparison"
    }

    def __init__(self, name):
        super().__init__(name)

    def run(self, input_data, run_id=None, agent_id=None, stage: str = ""):
        agent_name = self.name
        if agent_id is None:
            agent_id = f"{agent_name}-{int(time.time()*1000)}"
        t_start = time.time()
        event_logger.log_agent_start(run_id, agent_id, agent_name, {"input_data": input_data, "stage": stage})

        work_dir = input_data.get("work_dir", "./report")
        ticker = input_data.get("ticker_symbol", "Company")
        fyear = input_data.get("fyear", "2024")

        available_files = TextUtils.list_available_files(work_dir)
        event_logger.log_tool_call(run_id, agent_name, "list_available_files", {"work_dir": work_dir, "ext": ".txt"})

        section_file_map = {}
        hallucinations = []
        for section, substr in self.SECTION_TO_FILENAME.items():
            found = None
            for fname in available_files:
                if substr.lower() in fname.lower():
                    found = os.path.join(work_dir, fname)
                    break
            if found:
                section_file_map[section] = found
            else:
                section_file_map[section] = None
                event_logger.log_hallucination(
                    run_id, agent_name, "section_file_map",
                    f"No file found for section '{section}' (looking for '{substr}')",
                    stage
                )
                hallucinations.append(section)

        out_path = os.path.join(work_dir, f"{ticker}_{fyear}_Annual_Report.pdf")

        # Compile PDF
        filtered_section_map = {k: v for k, v in section_file_map.items() if v}
        build_status = None
        build_latency = 0

        if not filtered_section_map:
            msg = "No summary files found, cannot build report."
            event_logger.log_agent_error(run_id, agent_id, agent_name, msg, (time.time() - t_start) * 1000)
            return {"status": "FAILED", "message": msg}

        try:
            event_logger.log_tool_call(run_id, agent_name, "build_annual_report", {
                "section_file_map": filtered_section_map, "out_path": out_path,
                "ticker_symbol": ticker, "fyear": fyear
            })
            t_tool = time.time()
            result = ReportLabUtils.build_annual_report(
                section_file_map=filtered_section_map,
                out_path=out_path,
                ticker_symbol=ticker,
                fyear=fyear
            )
            build_latency = (time.time() - t_tool) * 1000
            event_logger.log_tool_result(run_id, agent_name, "build_annual_report", str(result), True, build_latency)
            build_status = "success"
            msg = f"Annual report successfully compiled: {out_path}"
            print(f"[{self.name}] {msg}")
        except Exception as e:
            build_latency = (time.time() - t_tool) * 1000 if 't_tool' in locals() else 0
            event_logger.log_tool_result(run_id, agent_name, "build_annual_report", str(e), False, build_latency)
            build_status = "fail"
            msg = f"Report compilation failed: {e}"
            event_logger.log_agent_error(run_id, agent_id, agent_name, msg, (time.time() - t_start) * 1000)
            return {"status": "FAILED", "message": msg}

        # Agent end log, LLM metrics (N/A here, but log for structure)
        total_time = (time.time() - t_start) * 1000
        event_logger.log_llm_metrics(run_id, agent_name, "N/A", tokens=0, cost=0.0, latency_ms=total_time)
        agent_output = {
            "pdf_path": out_path,
            "sections": list(filtered_section_map.keys()),
            "hallucinations": hallucinations,
            "build_status": build_status,
            "status": "TERMINATE"
        }
        event_logger.log_agent_end(run_id, agent_id, agent_name, agent_output, total_time)
        return agent_output

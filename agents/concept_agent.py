import os
from event_logger import log_tool_call, log_tool_result, log_agent_start, log_agent_end, log_agent_error, log_hallucination_metric, log_evaluation_metric
from llm_evaluation import llm_judge_explanation, classify_hallucination_type, match_file_to_concept
from .agent_base import AgentBase

class TextUtils:
    @staticmethod
    def list_available_files(work_dir, ext=".txt"):
        return [f for f in os.listdir(work_dir) if f.endswith(ext)]

    @staticmethod
    def read_file_content(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    @staticmethod
    def save_to_file(filepath, content):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def check_text_length(text, min_words=140):
        return len(text.split()) >= min_words

class ConceptCoTAgent(AgentBase):
    OUTPUTS = [
        ("01_company_overview.txt", ["07_company_description.txt", "06_business_highlights.txt"]),
        ("02_key_financials.txt",   ["02_balance_sheet.txt", "01_income_statement.txt", "03_cash_flow.txt"]),
        ("03_valuation.txt",        ["01_income_statement.txt", "02_balance_sheet.txt"]),
        ("04_risks.txt",            ["04_risk_analysis.txt"]),
        ("05_sell_side_summary.txt", [
            "07_company_description.txt", "06_business_highlights.txt", "02_balance_sheet.txt",
            "01_income_statement.txt", "03_cash_flow.txt", "04_risk_analysis.txt", "05_competitor_analysis.txt"
        ]),
        ("06_competitor_comparison.txt", ["05_competitor_analysis.txt", "02_balance_sheet.txt", "01_income_statement.txt"]),
    ]

    def __init__(self, name):
        super().__init__(name)

    def run(self, input_data):
        work_dir = input_data.get("work_dir", "./report")
        run_id = input_data.get("run_id", "no_run_id")

        agent_id = f"{self.name}-{run_id}"
        log_agent_start(run_id, agent_id, self.name, {"input_data": input_data})

        try:
            log_tool_call(run_id, self.name, "list_available_files", {"work_dir": work_dir})
            files = TextUtils.list_available_files(work_dir, ext=".txt")
            log_tool_result(run_id, self.name, "list_available_files", files, True, 0.0)

            def match_file(req_name):
                for f in files:
                    if req_name.replace('.txt', '').lower() in f.lower():
                        return os.path.join(work_dir, f)
                matched = match_file_to_concept(req_name, files)
                return os.path.join(work_dir, matched) if matched else None

            results = {}
            summary_stats = {"missing": 0, "generated": 0}
            hallucinations = []

            for output_name, req_files in self.OUTPUTS:
                content_chunks = []
                missing = False
                for req in req_files:
                    fpath = match_file(req)
                    log_tool_call(run_id, self.name, "match_file", {"requirement": req, "resolved_path": fpath})
                    if fpath:
                        log_tool_call(run_id, self.name, "read_file_content", {"filepath": fpath})
                        data = TextUtils.read_file_content(fpath)
                        valid_length = TextUtils.check_text_length(data) if data else False
                        log_tool_result(run_id, self.name, "read_file_content", {"filepath": fpath, "data_found": bool(data)}, True, 0.0)
                        if data and valid_length:
                            content_chunks.append(data.strip())
                        else:
                            missing = True
                            halluc_type = classify_hallucination_type(req, self.name, "low_content_density")
                            hallucinations.append(f"Too short or missing content for: {req}")
                            log_hallucination_metric(run_id, 0.0, f"Invalid content: {req}", {"agent": self.name, "type": halluc_type})
                    else:
                        missing = True
                        halluc_type = classify_hallucination_type(req, self.name, "unmatched_file")
                        hallucinations.append(f"Missing source file for: {req}")
                        log_hallucination_metric(run_id, 0.0, f"No match for {req}", {"agent": self.name, "type": halluc_type})

                if missing or not content_chunks:
                    summary = "Data Not Available"
                    summary_stats["missing"] += 1
                else:
                    text = "\n\n".join(content_chunks)
                    words = text.split()
                    summary = " ".join(words[:150]) if len(words) > 150 else text
                    summary_stats["generated"] += 1

                out_path = os.path.join(work_dir, output_name)
                try:
                    TextUtils.save_to_file(out_path, summary)
                    log_tool_result(run_id, self.name, "save_to_file", {"filepath": out_path, "content_length": len(summary)}, True, 0.0)
                    log_tool_result(run_id, self.name, "summary_word_count", {"file": out_path, "words": len(summary.split())}, True, 0.0)
                except Exception as e:
                    log_tool_result(run_id, self.name, "save_to_file", f"exception: {str(e)}", False, 0.0)
                    hallucinations.append(f"Failed to save: {out_path}")

                results[output_name] = summary

            reasoning_summary = llm_judge_explanation(hallucinations, context="summary construction") if hallucinations else "All summaries constructed successfully."
            log_evaluation_metric(run_id, "Summary Construction Faithfulness", 1.0 if not hallucinations else 0.0, reasoning_summary)

            final_output = {
                "status": "TERMINATE" if summary_stats["missing"] == 0 else "FAILED",
                "outputs": list(results.keys()),
                "summary_stats": summary_stats,
                "hallucinations": hallucinations
            }
            log_agent_end(run_id, agent_id, self.name, final_output, 0.0)
            return final_output

        except Exception as e:
            log_agent_error(run_id, agent_id, self.name, str(e), 0.0)
            raise

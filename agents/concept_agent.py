import os
from event_logger import log_tool_call, log_tool_result, log_agent_start, log_agent_end, log_agent_error
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
        except Exception as e:
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
        ("01_company_overview.txt", ["Company_Description.txt", "Business_Highlights.txt"]),
        ("02_key_financials.txt",    ["Balance_Sheet.txt", "Income_Statement.txt", "Cash_Flow.txt"]),
        ("03_valuation.txt",         ["Income_Statement.txt", "Balance_Sheet.txt"]),
        ("04_risks.txt",             ["Risk_Factors.txt"]),
        ("05_sell_side_summary.txt", [
            "Company_Description.txt", "Business_Highlights.txt", "Balance_Sheet.txt",
            "Income_Statement.txt", "Cash_Flow.txt", "Risk_Factors.txt", "Competitors_Analysis.txt"
        ]),
        ("06_competitor_comparison.txt", ["Competitors_Analysis.txt", "Balance_Sheet.txt", "Income_Statement.txt"]),
    ]

    def __init__(self, name):
        super().__init__(name)

    def run(self, input_data):
        work_dir = input_data.get("work_dir", "./report")
        run_id = input_data.get("run_id", "no_run_id")

        agent_id = f"{self.name}-{run_id}"
        # Log agent start
        log_agent_start(run_id, agent_id, self.name, {"input_data": input_data})

        try:
            files = None
            # List files (tool call)
            log_tool_call(run_id, self.name, "list_available_files", {"work_dir": work_dir})
            files = TextUtils.list_available_files(work_dir, ext=".txt")
            log_tool_result(run_id, self.name, "list_available_files", files, True, 0.0)

            def match_file(req_name):
                for f in files:
                    if req_name.replace('.txt', '').lower() in f.lower():
                        return os.path.join(work_dir, f)
                return None

            results = {}
            summary_stats = {"missing": 0, "generated": 0}

            for output_name, req_files in self.OUTPUTS:
                content_chunks = []
                missing = False
                for req in req_files:
                    fpath = match_file(req)
                    log_tool_call(run_id, self.name, "match_file", {"requirement": req, "resolved_path": fpath})
                    if fpath:
                        log_tool_call(run_id, self.name, "read_file_content", {"filepath": fpath})
                        data = TextUtils.read_file_content(fpath)
                        log_tool_result(run_id, self.name, "read_file_content", {"filepath": fpath, "data_found": bool(data)}, True, 0.0)
                        if data:
                            content_chunks.append(data.strip())
                        else:
                            missing = True
                    else:
                        missing = True
                if missing or not content_chunks:
                    summary = "Data Not Available"
                    summary_stats["missing"] += 1
                else:
                    text = "\n\n".join(content_chunks)
                    words = text.split()
                    summary = " ".join(words[:150]) if len(words) > 150 else text
                    summary_stats["generated"] += 1
                out_path = os.path.join(work_dir, output_name)
                log_tool_call(run_id, self.name, "save_to_file", {"filepath": out_path, "content_preview": summary[:40]})
                TextUtils.save_to_file(out_path, summary)
                log_tool_result(run_id, self.name, "save_to_file", {"filepath": out_path, "content_length": len(summary)}, True, 0.0)
                results[output_name] = summary

            print(f"[{self.name}] Generated all summaries.")
            final_output = {"status": "TERMINATE", "outputs": list(results.keys()), "summary_stats": summary_stats}
            # Log agent end
            log_agent_end(run_id, agent_id, self.name, final_output, 0.0)
            return final_output

        except Exception as e:
            # Log error if any
            log_agent_error(run_id, agent_id, self.name, str(e), 0.0)
            raise

import time
from typing import Any
from .agent_base import AgentBase
import event_logger
from llm_evaluation import llm_judge_explanation

class ExpertInvestorShadow(AgentBase):
    """
    Role: Shadow Auditor
    Domain: QA & Validation
    Primary Responsibility: Audit the full orchestration sequence for compliance.
    """
    def run(self, input_data: Any, run_id=None, agent_id=None, stage: str = "") -> Any:
        agent_name = self.name
        if agent_id is None:
            agent_id = f"{agent_name}-{int(time.time()*1000)}"
        t_agent_start = time.time()
        event_logger.log_agent_start(run_id, agent_id, agent_name, {
            "input_data": input_data,
            "stage": stage
        })

        print(f"[{self.name}] Auditing {stage} stage.")

        issues = []
        hallucinations = input_data.get("hallucinations", []) if isinstance(input_data, dict) else []

        expected_keys = ["created_files", "status"]
        for key in expected_keys:
            if key not in input_data:
                issues.append({
                    "issue": f"Missing key: {key}",
                    "fix": f"Check data generation in stage: {stage}",
                    "result": "FAIL"
                })

        if hallucinations:
            summary = llm_judge_explanation(hallucinations, context=f"shadow QA - {stage}")
            issues.append({
                "issue": "Hallucinations found in output",
                "fix": "Review model response logic or tool input handling.",
                "reasoning": summary,
                "result": "WARN"
            })

        for issue in issues:
            event_logger.log_evaluation_metric(
                run_id,
                metric_name="QA Issue",
                score=0.0,
                reasoning=issue.get("reasoning", issue["issue"]),
                details=issue
            )

        t_agent_end = time.time()
        audit_output = {
            "stage": stage,
            "issues": issues,
            "status": "TERMINATE" if not issues else "FAILED"
        }
        event_logger.log_agent_end(run_id, agent_id, agent_name, audit_output, (t_agent_end - t_agent_start) * 1000)

        return audit_output if issues else input_data
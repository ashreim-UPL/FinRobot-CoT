# expert_investor_shadow.py

import time
from typing import Any
from .agent_base import AgentBase
import event_logger

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
        # Start log for this shadow audit agent
        event_logger.log_agent_start(run_id, agent_id, agent_name, {
            "input_data": input_data,
            "stage": stage
        })

        print(f"[{self.name}] Auditing {stage} stage.")

        # === QA Checks Example (customize this logic for real validation) ===
        issues = []
        # Example: check if expected keys exist in input_data
        expected_keys = ["created_files", "status"]
        for key in expected_keys:
            if key not in input_data:
                issues.append({"issue": f"Missing key: {key}", "fix": f"Check data generation in stage: {stage}", "result": "FAIL"})

        audit_output = {
            "stage": stage,
            "issues": issues,
            "status": "TERMINATE" if not issues else "FAILED"
        }
        # Audit log: add QA metric event for transparency
        for issue in issues:
            event_logger.log_evaluation_metric(
                run_id, 
                metric_name="QA Issue", 
                score=0.0,
                reasoning=issue["issue"],
                details=issue
            )

        t_agent_end = time.time()
        total_time = (t_agent_end - t_agent_start) * 1000
        # Finalize the agent_end log with all output, including issues
        event_logger.log_agent_end(run_id, agent_id, agent_name, audit_output, total_time)

        return audit_output if issues else input_data

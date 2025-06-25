# expert_investor.py

import time
from typing import Any
from .agent_base import AgentBase
import event_logger

class ExpertInvestor(AgentBase):
    """
    Role: Strategic Orchestrator for Financial Reports.
    Domain: Executive-level Coordination & Delegation.
    Primary Responsibility: Manage and delegate the end-to-end generation of a financial report based on runtime parameters.
    """
    def run(self, input_data: Any, run_id=None, agent_id=None, stage: str = "") -> Any:
        agent_name = self.name
        if agent_id is None:
            agent_id = f"{agent_name}-{int(time.time()*1000)}"
        t_start = time.time()
        
        # Log agent start (delegation begins)
        event_logger.log_agent_start(run_id, agent_id, agent_name, {
            "input_data": input_data,
            "stage": stage
        })

        print(f"[{self.name}] Delegating {stage} stage.")

        # Optionally log the "delegation" event itself for transparency
        event_logger._log_event(
            "orchestrator_delegation",
            {
                "run_id": run_id,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "delegated_stage": stage,
                "inputs": input_data,
                "timestamp": time.time()
            }
        )

        # Placeholder: In real orchestration, you'd call subordinate agents here

        t_end = time.time()
        event_logger.log_agent_end(
            run_id, agent_id, agent_name, 
            {"delegated_to_stage": stage, "output": input_data},
            (t_end - t_start) * 1000
        )

        return input_data

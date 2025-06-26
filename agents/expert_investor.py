# expert_investor.py

import time
from typing import Any
from .agent_base import AgentBase
import event_logger
from llm_evaluation import llm_judge_explanation

class ExpertInvestor(AgentBase):
    """
    Role: Strategic Orchestrator for Financial Reports.
    Domain: Executive-level Coordination & Delegation.
    Primary Responsibility: Manage and delegate the end-to-end generation of a financial report based on runtime parameters.
    """

    def run(self, context: dict) -> Any:
        run_id = context.get("run_id")
        agent_name = self.name
        agent_id = f"{agent_name}-{int(time.time() * 1000)}"
        t_start = time.time()

        event_logger.log_agent_start(run_id, agent_id, agent_name, {"context": "orchestration_start"})

        input_query = context["input_query"]
        data_agent = context["data_agent"]
        concept_agent = context["concept_agent"]
        thesis_agent = context["thesis_agent"]
        shadow = context["shadow"]

        try:
            all_hallucinations = []

            # --- Stage 1: Data Agent ---
            data_agent_id = f"{data_agent.name}-{run_id}"
            event_logger.log_agent_start(run_id, data_agent_id, data_agent.name, input_query)
            t0 = time.perf_counter()
            data = data_agent.run({**input_query, "run_id": run_id})
            latency = (time.perf_counter() - t0) * 1000
            event_logger.log_agent_end(run_id, data_agent_id, data_agent.name, data, latency)
            shadow.run(data, stage="Data Gathering")
            all_hallucinations += data.get("hallucinations", [])

            # --- Stage 2: Concept Agent ---
            concept_agent_id = f"{concept_agent.name}-{run_id}"
            event_logger.log_agent_start(run_id, concept_agent_id, concept_agent.name, data)
            t1 = time.perf_counter()
            analysis = concept_agent.run({**data, "run_id": run_id})
            latency = (time.perf_counter() - t1) * 1000
            event_logger.log_agent_end(run_id, concept_agent_id, concept_agent.name, analysis, latency)
            shadow.run(analysis, stage="Analysis")
            all_hallucinations += analysis.get("hallucinations", [])

            # --- Stage 3: Thesis Agent ---
            thesis_agent_id = f"{thesis_agent.name}-{run_id}"
            event_logger.log_agent_start(run_id, thesis_agent_id, thesis_agent.name, analysis)
            t2 = time.perf_counter()
            report = thesis_agent.run({**analysis, "run_id": run_id})
            latency = (time.perf_counter() - t2) * 1000
            event_logger.log_agent_end(run_id, thesis_agent_id, thesis_agent.name, report, latency)
            shadow.run(report, stage="Final Compilation")
            all_hallucinations += report.get("hallucinations", [])

            # --- Evaluate Orchestration Quality ---
            if all_hallucinations:
                reasoning = llm_judge_explanation(all_hallucinations, context="cross-stage hallucination trace")
                score = 0.0
            else:
                reasoning = "All stages completed successfully without any hallucination indicators."
                score = 1.0

            event_logger.log_evaluation_metric(
                run_id,
                metric_name="Orchestration Faithfulness",
                score=score,
                reasoning=reasoning,
                details={"total_hallucinations": len(all_hallucinations)}
            )

            t_end = time.time()
            event_logger.log_agent_end(
                run_id,
                agent_id,
                agent_name,
                {"final_report": report},
                (t_end - t_start) * 1000,
            )
            return report

        except Exception as e:
            latency = (time.time() - t_start) * 1000
            event_logger.log_agent_error(run_id, agent_id, agent_name, str(e), latency)
            raise

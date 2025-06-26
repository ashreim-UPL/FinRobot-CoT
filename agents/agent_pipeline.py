from .us_data_agent import DataCoTAgentUS
from .in_data_agent import DataCoTAgentIN
from .concept_agent import ConceptCoTAgent
from .thesis_agent import ThesisCoTAgent
from .expert_investor import ExpertInvestor
from .expert_investor_shadow import ExpertInvestorShadow

from event_logger import (
    log_agent_start,
    log_agent_end,
    log_agent_error,
    log_pipeline_start,
    log_pipeline_end,
    log_pipeline_error,
    log_evaluation_metric
)
from llm_evaluation import llm_judge_explanation

import uuid
import time

class CoTPipeline:
    def __init__(self, region='US'):
        self.region = region
        self.data_agent = DataCoTAgentUS('Data_CoT_Agent_US') if region == 'US' else DataCoTAgentIN('Data_CoT_Agent_IN')
        self.concept_agent = ConceptCoTAgent('Concept_CoT_Agent')
        self.thesis_agent = ThesisCoTAgent('Thesis_CoT_Agent')
        self.expert_investor = ExpertInvestor('Expert_Investor')
        self.shadow = ExpertInvestorShadow('Expert_Investor_Shadow')

    def run(self, input_query):
        run_id = str(uuid.uuid4())
        start_time = time.time()
        log_pipeline_start(run_id, input_query, custom_data={"region": self.region})

        try:
            report = self.expert_investor.run({
                "run_id": run_id,
                "region": self.region,
                "input_query": input_query,
                "data_agent": self.data_agent,
                "concept_agent": self.concept_agent,
                "thesis_agent": self.thesis_agent,
                "shadow": self.shadow,
            })

            # Optional top-level hallucination audit (e.g., consistency check)
            hallucinations = report.get("hallucinations") if isinstance(report, dict) else []
            if hallucinations:
                summary = llm_judge_explanation(hallucinations, context="final pipeline output")
                score = 0.0
            else:
                summary = "Report appears internally consistent and free of hallucinations."
                score = 1.0

            log_evaluation_metric(
                run_id,
                metric_name="Pipeline Output Faithfulness",
                score=score,
                reasoning=summary,
                details={"hallucination_count": len(hallucinations) if hallucinations else 0}
            )

            latency_ms = int((time.time() - start_time) * 1000)
            log_pipeline_end(run_id, report, latency_ms)
            print("[Expert_Investor] TERMINATE: Report and audit complete.")
            return report

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            log_pipeline_error(run_id, str(e), latency_ms)
            print(f"Pipeline failed: {e}")
            raise
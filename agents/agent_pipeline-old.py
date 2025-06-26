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
)
import uuid
import time

class CoTPipeline:
    def __init__(self, region='US'):
        self.region = region
        if region == 'US':
            self.data_agent = DataCoTAgentUS('Data_CoT_Agent_US')
        else:
            self.data_agent = DataCoTAgentIN('Data_CoT_Agent_IN')
        self.concept_agent = ConceptCoTAgent('Concept_CoT_Agent')
        self.thesis_agent = ThesisCoTAgent('Thesis_CoT_Agent')
        self.expert_investor = ExpertInvestor('Expert_Investor')
        self.shadow = ExpertInvestorShadow('Expert_Investor_Shadow')

    def run(self, input_query):
        run_id = str(uuid.uuid4())
        start_time = time.time()
        latency_ms = (time.time() - start_time) * 1000
        log_pipeline_start(run_id, input_query, custom_data={"region": self.region})
        try:
            # --- Data Gathering Stage ---
            agent_id = f"{self.data_agent.name}-{run_id}"
            log_agent_start(run_id, agent_id, self.data_agent.name, input_query)
            t0 = time.perf_counter()
            try:
                data = self.data_agent.run({**input_query, "run_id": run_id})
                latency = (time.perf_counter() - t0) * 1000
                log_agent_end(run_id, agent_id, self.data_agent.name, data, latency)
            except Exception as e:
                latency = (time.perf_counter() - t0) * 1000
                log_agent_error(run_id, agent_id, self.data_agent.name, str(e), latency)
                raise
            # Shadow log
            self.shadow.run(data, stage="Data Gathering")

            # --- Analysis Stage ---
            agent_id = f"{self.concept_agent.name}-{run_id}"
            log_agent_start(run_id, agent_id, self.concept_agent.name, data)
            t1 = time.perf_counter()
            try:
                analysis = self.concept_agent.run({**data, "run_id": run_id})
                latency = (time.perf_counter() - t1) * 1000
                log_agent_end(run_id, agent_id, self.concept_agent.name, analysis, latency)
            except Exception as e:
                latency = (time.perf_counter() - t1) * 1000
                log_agent_error(run_id, agent_id, self.concept_agent.name, str(e), latency)
                raise
            self.shadow.run(analysis, stage="Analysis")

            # --- Final Compilation Stage ---
            agent_id = f"{self.thesis_agent.name}-{run_id}"
            log_agent_start(run_id, agent_id, self.thesis_agent.name, analysis)
            t2 = time.perf_counter()
            try:
                report = self.thesis_agent.run({**analysis, "run_id": run_id})
                latency = (time.perf_counter() - t2) * 1000
                log_agent_end(run_id, agent_id, self.thesis_agent.name, report, latency)
            except Exception as e:
                latency = (time.perf_counter() - t2) * 1000
                log_agent_error(run_id, agent_id, self.thesis_agent.name, str(e), latency)
                raise
            self.shadow.run(report, stage="Final Compilation")

            log_pipeline_end(run_id, report, latency_ms)
            print("[Expert_Investor] TERMINATE: Report and audit complete.")
            return report

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            log_pipeline_error(run_id, str(e), latency_ms)
            print(f"Pipeline failed: {e}")
            raise


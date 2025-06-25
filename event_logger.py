import logging
import os
import sys
import json
import functools
import inspect
import datetime
import asyncio
import time
import uuid
from contextlib import contextmanager

# === 1. CORE LOGGING SETUP (EXISTING) ===
# This section remains the same. It sets up the basic logging infrastructure.

def setup_logging(console_level=logging.INFO, file_level=logging.DEBUG, log_file="logs/evaluation.log"):
    """
    Configures the root logger for console and file output.
    The file output is structured JSON for easy parsing.
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # The file handler will now use a JSON formatter for structured data.
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    # This formatter just passes the message through, as we will be formatting it as JSON ourselves.
    file_format = logging.Formatter('%(message)s')
    file_handler.setFormatter(file_format)

    # The console handler can use a more human-readable format.
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(console_level)
    stream_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(stream_format)

    root_logger.setLevel(min(console_level, file_level))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    
    # Use a dedicated logger for the application's structured events
    logging.getLogger("FinRobot").info("Unified logging initialized for evaluation.")


# === 2. STRUCTURED EVENT LOGGER (ENHANCED) ===
# We will create a dedicated logger for our structured events to avoid
# interference with other potential logging in the system.
event_logger = logging.getLogger("FinRobotEvents")

def _log_event(event_type: str, data: dict):
    """
    Internal function to log a structured event as a JSON line.
    """
    log_payload = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "event_type": event_type,
        "data": data
    }
    event_logger.info(json.dumps(log_payload, ensure_ascii=False))

# === 3. EVALUATION-SPECIFIC LOGGING FUNCTIONS ===
# These functions are the core of the new evaluation framework. They provide
# a clear and explicit API for logging events tied to your defined metrics.

def log_pipeline_start(query: str, run_id: str, custom_data: dict = None):
    """
    Logs the beginning of an end-to-end pipeline run.
    - Metric: End-to-End Latency (start time)
    - Metric: Total Cost (initialization)
    """
    _log_event("pipeline_start", {
        "run_id": run_id,
        "query": query,
        "custom_data": custom_data or {}
    })

def log_pipeline_end(run_id: str, final_output: any, latency_ms: float):
    """
    Logs the successful completion of an end-to-end pipeline run.
    - Metric: End-to-End Latency (end time)
    - Metric: Answer Relevance (captures final answer for later scoring)
    - Metric: Faithfulness (captures final answer for later scoring)
    """
    _log_event("pipeline_end", {
        "run_id": run_id,
        "final_output": final_output,
        "end_to_end_latency_ms": latency_ms
    })
    
def log_pipeline_error(run_id: str, error: str, latency_ms: float):
    """
    Logs the failure of an end-to-end pipeline run.
    - Metric: Toxicity / Refusal Rate (can be inferred from error)
    """
    _log_event("pipeline_error", {
        "run_id": run_id,
        "error": error,
        "end_to_end_latency_ms": latency_ms
    })

def log_agent_start(run_id: str, agent_id, agent_name: str, inputs: dict):
    """
    Logs the beginning of an individual agent's execution.
    - Metric: Agent-Level Latency (start time)
    """
    _log_event("agent_start", {
        "run_id": run_id,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "inputs": inputs
    })

def log_agent_end(run_id: str, agent_id, agent_name: str, output: any, latency_ms: float):
    """
    Logs the successful completion of an agent's execution.
    - Metric: Agent-Level Latency (end time)
    """
    _log_event("agent_end", {
        "run_id": run_id,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "output": output,
        "agent_latency_ms": latency_ms
    })
    
def log_agent_error(run_id: str, agent_id, agent_name: str, error: str, latency_ms: float):
    """
    Logs the failure of an agent's execution.
    """
    _log_event("agent_error", {
        "run_id": run_id,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "error": error,
        "agent_latency_ms": latency_ms
    })

def log_agent_setup(run_id, agent_name, config):
    logging.getLogger("FinRobot").info(json.dumps({
        "event_type": "agent_setup",
        "run_id": run_id,
        "agent_name": agent_name,
        "config": config
    }))

def log_tool_call(run_id: str, agent_name: str, tool_name: str, tool_input: dict):
    """
    Logs a tool call made by an agent BEFORE execution.
    - Metric: Tool Selection Accuracy (captures which tool was chosen)
    """
    _log_event("tool_call", {
        "run_id": run_id,
        "agent_name": agent_name,
        "tool_name": tool_name,
        "tool_input": tool_input
    })

def log_tool_result(run_id: str, agent_name: str, tool_name: str, tool_output: any, success: bool, latency_ms: float):
    """
    Logs the result of a tool call AFTER execution.
    - Metric: Tool Call Success Rate
    - Metric: Context Relevance / Recall (captures retrieved data for scoring)
    """
    _log_event("tool_result", {
        "run_id": run_id,
        "agent_name": agent_name,
        "tool_name": tool_name,
        "tool_output": tool_output,
        "success": success,
        "tool_latency_ms": latency_ms
    })

def log_llm_metrics(run_id: str, agent_name: str, model_name: str, tokens: int, cost: float, latency_ms: float):
    """
    Logs metrics related to a specific LLM call.
    - Metric: Total Cost / Tokens
    """
    _log_event("llm_metrics", {
        "run_id": run_id,
        "agent_name": agent_name,
        "model_name": model_name,
        "tokens": tokens,
        "cost": cost,
        "llm_latency_ms": latency_ms
    })

def log_evaluation_metric(run_id: str, metric_name: str, score: float, reasoning: str, details: dict = None):
    """
    Logs the output of an evaluation (e.g., from an LLM-as-a-judge).
    """
    _log_event("evaluation_metric", {
        "run_id": run_id,
        "metric_name": metric_name,
        "score": score,
        "reasoning": reasoning,
        "details": details or {}
    })


# === 4. CONTEXT MANAGERS FOR EASY INTEGRATION ===
# These context managers make it easy to wrap your pipeline and agent
# calls to automatically handle timing and start/end logging.

@contextmanager
def pipeline_run(query: str, custom_data: dict = None):
    """Context manager for a full pipeline execution."""
    run_id = str(uuid.uuid4())
    start_time = time.perf_counter()
    log_pipeline_start(query, run_id, custom_data)

    def log_end_pipeline(output: dict):
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        log_pipeline_end(run_id, output, latency_ms)

    def log_error_pipeline(error: str):
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        log_pipeline_error(run_id, error, latency_ms)

    try:
        yield run_id, log_end_pipeline, log_error_pipeline
    except Exception as e:
        log_error_pipeline(str(e))
        raise

@contextmanager
def agent_run(run_id: str, agent_id, agent_name: str, inputs: dict):
    start_time = time.perf_counter()
    agent_id = str(uuid.uuid4())

    # Start log
    log_agent_start(run_id, agent_id, agent_name, inputs)

    def log_end(output: dict):
        latency_ms = (time.perf_counter() - start_time) * 1000
        log_agent_end(run_id, agent_id, agent_name, output, latency_ms)

    def log_error(error: str):
        latency_ms = (time.perf_counter() - start_time) * 1000
        log_agent_error(run_id, agent_id, agent_name, error, latency_ms)

    try:
        yield log_end, log_error
    except Exception as e:
        log_error(str(e))
        raise

# === EXAMPLE USAGE ===
# This demonstrates how you would use the new logging functions in your code.

def example_usage():
    """A mock run of the FinRobot pipeline to demonstrate logging."""
    setup_logging()
    
    query = "What was the revenue for Apple in the last fiscal year?"
    
    # Using the context manager for the pipeline
    with pipeline_run(query) as run_id:
        try:
            # 1. CompanyIdentifier Agent
            agent_1_inputs = {"company_name": "Apple"}
            with agent_run(run_id, "CompanyIdentifier", agent_1_inputs):
                time.sleep(0.1) # Simulate work
                agent_1_output = {"ticker": "AAPL", "region": "US"}
                # Manually log agent end with its output
                log_agent_end(run_id, "CompanyIdentifier", agent_1_output, 105.3)

            # 2. DataExtractor Agent
            agent_2_inputs = {"ticker": "AAPL"}
            with agent_run(run_id, "DataExtractor", agent_2_inputs):
                # This agent calls a tool
                tool_name = "get_financial_statements"
                tool_input = {"ticker": "AAPL", "statement": "income_statement"}
                log_tool_call(run_id, "DataExtractor", tool_name, tool_input)
                time.sleep(0.3) # Simulate tool execution
                tool_output = {"revenue": 90_000_000_000}
                log_tool_result(run_id, "DataExtractor", tool_name, tool_output, success=True, latency_ms=301.2)
                
                agent_2_output = tool_output
                log_agent_end(run_id, "DataExtractor", agent_2_output, 350.5)

            # 3. FinancialAnalyzer Agent
            agent_3_inputs = {"data": {"revenue": 90_000_000_000}}
            with agent_run(run_id, "FinancialAnalyzer", agent_3_inputs):
                # This agent calls an LLM
                time.sleep(0.5) # Simulate LLM call
                log_llm_metrics(run_id, "FinancialAnalyzer", "gpt-4o", 1200, 0.015, 502.1)
                agent_3_output = "Apple's revenue was $90B."
                log_agent_end(run_id, "FinancialAnalyzer", agent_3_output, 550.8)

            # Pipeline finished, manually log the end event
            final_report = agent_3_output
            
            # Here, you would call your LLM-as-a-judge to get scores
            log_evaluation_metric(run_id, "Answer Relevance", 4.8, "The answer directly addresses the user's query.")
            log_evaluation_metric(run_id, "Faithfulness", 5.0, "The answer is fully supported by the retrieved data.")

            # IMPORTANT: Manually log the pipeline end event with the final output
            # We get the latency from the context manager's print statement for this example
            log_pipeline_end(run_id, final_report, 1000.0) # Placeholder latency
            
            print("\n✅ Example usage finished. Check 'logs/evaluation.log' for structured output.")

        except Exception as e:
            print(f"\n❌ Pipeline failed: {e}")

if __name__ == "__main__":
    example_usage()

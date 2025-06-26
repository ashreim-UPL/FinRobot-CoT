import os
import openai 

from openai import OpenAI



client = OpenAI(api_key="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") 


response = client.chat.completions.create(
    model="gpt-4-1106-preview",  # "gpt-4.1-mini-2025-04-14",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the summary of the income statement?"}
    ],
)


def match_file_to_concept(section_name: str, file_list: list[str]) -> str:
    """
    Ask the LLM to choose the best file from a list for a given concept.
    """
    prompt = f"""
    You are given a section of a financial report titled: '{section_name}'.
    From the following available files, pick the most appropriate one for that section:

    {file_list}

    Return only the exact filename best suited.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a financial data assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=50
        )
        filename = response.choices[0].message.content.strip()
        return filename if filename in file_list else None
    except Exception as e:
        return None

def llm_judge_explanation(hallucinations, context=""):
    """
    Uses GPT-4 to generate a reasoned explanation of detected hallucinations.
    """
    if not hallucinations:
        return "No hallucinations detected."

    prompt = f"""
You are a critical reasoning assistant.
You have been given the following list of possible LLM hallucinations or tool errors during a financial analysis pipeline:

Hallucinations:
{hallucinations}

Context:
{context}

Your task is to explain what likely caused these hallucinations, whether they are critical, and what steps should be taken to resolve them. Be concise but insightful.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful financial QA assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"[LLM explanation failed: {e}]"

def classify_hallucination_type(filename, tool_name, failure_type):
    """
    A basic classifier to tag hallucination types in a standardized way.
    """
    if "missing" in failure_type.lower():
        return "missing_output"
    elif "timeout" in failure_type.lower():
        return "api_timeout"
    elif "short" in failure_type.lower():
        return "undergenerated"
    elif "tool_crash" in failure_type:
        return "tool_exception"
    else:
        return "unknown"

def llm_should_retry(tool_name, failure_reason):
    if any(term in failure_reason.lower() for term in ["timeout", "rate limit", "empty"]):
        return "retry"
    if "irrelevant" in failure_reason.lower():
        return "switch"
    return "no_action"

def generate_placeholder_summary(filename, company):
    return f"[AUTO] Placeholder summary for {company} - Source: {filename}. This was auto-generated due to missing data or tool failure."

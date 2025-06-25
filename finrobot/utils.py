# /finrobot/utils.py
import json
import re
import os
from datetime import date, timedelta, datetime
from typing import Optional, Dict, Annotated
import socket
from functools import wraps
import pandas as pd

# --- Import the central logging setup ---
from .logging_config import setup_logger

# --- Create a logger for this module ---
utils_logger = setup_logger("finrobot.utils")

# --- Utility Functions ---
# --- Networking Utilities ---
_original_getaddrinfo = socket.getaddrinfo
def force_ipv4(*args, **kwargs):
    """Forces IPv4 resolution for network requests."""
    return [info for info in _original_getaddrinfo(*args, **kwargs) if info[0] == socket.AF_INET]
socket.getaddrinfo = force_ipv4

def load_prompt_from_file(filename: str, default_prompt: str = "Default system prompt.") -> str:
    """Loads a prompt from a file. The filename should be an absolute path or relative to the CWD."""
    prompt_file_path = filename
    try:
        with open(prompt_file_path, 'r', encoding='utf-8') as f:
            utils_logger.info("Loading prompt from %s", prompt_file_path)
            return f.read()
    except FileNotFoundError:
        utils_logger.error("Prompt file not found: %s. Using default prompt.", prompt_file_path)
        return default_prompt
    except Exception as e:
        utils_logger.error("Error loading prompt from %s: %s. Using default.", prompt_file_path, e)
        return default_prompt

def save_json_to_file(data: dict, filename: str, directory: str = ".") -> None:
    """Saves a dictionary to a JSON file."""
    try:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
    except OSError as e:
        utils_logger.error("Error creating directory '%s': %s.", directory, e)
        return
    filepath = os.path.join(directory, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        utils_logger.info("JSON saved to %s", filepath)
    except IOError as e:
        utils_logger.error("Error saving JSON to %s: %s", filepath, e)
    except TypeError as e:
        utils_logger.error("Data for '%s' is not JSON serializable: %s", filepath, e)

def load_json_from_file(filename: str, directory: str = ".") -> Optional[dict]:
    """Loads a dictionary from a JSON file."""
    filepath = os.path.join(directory, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            utils_logger.info("Loaded JSON from %s", filepath)
            return data
    except FileNotFoundError:
        utils_logger.warning("File not found at %s", filepath)
        return None
    except json.JSONDecodeError:
        utils_logger.error("Could not decode JSON from %s.", filepath)
        return None
    except IOError as e:
        utils_logger.error("Error loading JSON from %s: %s", filepath, e)
        return None

def clean_text(text: str) -> str:
    """Cleans text by replacing multiple whitespaces with single spaces and stripping."""
    if not isinstance(text, str):
        return ""
    return re.sub(r'\s+', ' ', text).strip()

SavePathType = Annotated[str, "File path to save data. If None, data is not saved."]

def save_output(data: pd.DataFrame, tag: str, save_path: SavePathType = None) -> None:
    """Saves DataFrame to CSV if save_path is provided."""
    if save_path:
        data.to_csv(save_path)
        utils_logger.info(f"{tag} saved to {save_path}")
        print(f"{tag} saved to {save_path}")

def get_next_weekday(input_date):
    """
    Returns the next weekday if the input_date is a weekend.
    Handles datetime objects or YYYY-MM-DD strings.
    """
    if not isinstance(input_date, datetime):
        input_date = datetime.strptime(input_date, "%Y-%m-%d")
    if input_date.weekday() >= 5:  # Monday is 0, Sunday is 6
        days_to_add = 7 - input_date.weekday()
        next_weekday = input_date + timedelta(days=days_to_add)
        return next_weekday
    else:
        return input_date

def register_keys_from_json(json_file_path: str):
    """
    Registers API keys from a JSON file by setting them as environment variables.
    It expects a JSON file where keys are API names (e.g., "OPENAI_API_KEY")
    and values are the corresponding API keys.
    """
    if not os.path.isfile(json_file_path):
        msg = f"API keys file not found at {json_file_path}. Please create it if needed."
        utils_logger.warning(msg)
        print(msg)
        return

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            api_keys = json.load(f)

        registered_keys = []

        for key, value in api_keys.items():
            if value:
                os.environ[key] = value
                utils_logger.info(f"Registered API key for {key}")
                registered_keys.append(key)

        msg = (
            f"Registered API keys for: {', '.join(registered_keys)}"
            if registered_keys else
            "No API keys registered."
        )
        print(msg)

    except json.JSONDecodeError:
        msg = f"Failed to parse JSON in {json_file_path}. Please check the file format."
        utils_logger.error(msg)
        print(msg)

    except Exception as e:
        msg = f"Unexpected error while loading API keys: {e}"
        utils_logger.error(msg, exc_info=True)
        print(msg)

def decorate_all_methods(decorator):
    """Class decorator to apply a given decorator to all methods of a class."""
    def class_decorator(cls):
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value):
                setattr(cls, attr_name, decorator(attr_value))
        return cls
    return class_decorator

def save_to_file(data: str, file_path: str) -> str:
    """
    Save the provided string data to a file at the specified file path using UTF-8 encoding.

    Args:
        data (str): The text data to be saved.
        file_path (str): The path (including filename) where the data should be saved.

    Returns:
        str: A message indicating successful save and the file path.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(data)
    return f"Data successfully saved to {file_path}"
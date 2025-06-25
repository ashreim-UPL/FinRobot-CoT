import functools
import inspect
import datetime
import asyncio
import yaml
import logging
import os
import time
import json

# --- STATIC DEBUG CONFIGURATION ---
DEBUG_CONFIG = {
    "enabled": True,
    "wait_for_confirmation": False,
    "log_to_file": True,
    "log_file_path": "logs/debug.log",
    "use_logging_module": True,
    "refresh_on_call": False,
    "verbose_startup": True
}

# --- CONFIG LOADING ---
def load_full_config(config_path=DEBUG_CONFIG["CONFIG_PATH"]):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

full_config = load_full_config()
debug_config = full_config.get("debug", {})
paths_config = full_config.get("paths", {})
log_file_path = debug_config.get("log_file_path", "logs/debug.log")
cfg_refresh = debug_config.get("refresh_on_call", False)

# --- LOGGING SETUP ---
def setup_logger(log_file):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logging.basicConfig(
        filename=log_file,
        filemode='a',
        format='[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.DEBUG
    )

if debug_config.get("use_logging_module") and debug_config.get("log_to_file"):
    setup_logger(log_file_path)

# --- SAFE PRINTING ---
def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        safe_msg = msg.encode("ascii", "replace").decode()
        print(safe_msg)

# --- UNIFIED DEBUG OUTPUT ---
def log_debug(msg):
    cfg = load_full_config().get("debug", {}) if cfg_refresh else debug_config
    if cfg.get("use_logging_module") and cfg.get("log_to_file"):
        logging.debug(msg)
    else:
        safe_print(msg)

# --- DECORATOR FOR DEBUG LOGGING ---
def debug_log(cfg_refresh=False, max_output_len=500):
    def decorator(func):
        is_coroutine = asyncio.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            caller = inspect.stack()[1].function
            func_name = func.__name__

            log_debug(f"\n[DEBUG {timestamp}] --> async '{func_name}' called from '{caller}'\n  |-- Args: {args}\n  |-- Kwargs: {kwargs}")

            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
            except Exception as e:
                log_debug(f"[DEBUG {timestamp}] async '{func_name}' raised: {e}")
                raise
            end_time = time.perf_counter()

            # --- CHANGE HERE for milliseconds ---
            duration_ms = (end_time - start_time) * 1000
            # Ensure proper formatting, e.g., 2 decimal places for milliseconds
            # If duration is very small, we might still see 0.00ms.
            # You can adjust formatting (e.g., :.3f or :.0f) based on desired precision.
            formatted_duration = f"{duration_ms:.2f}ms" 
            # --- END CHANGE ---

            result_str = str(result)
            if len(result_str) > max_output_len:
                result_str = result_str[:max_output_len] + " ... [truncated]"

            log_debug(f"[DEBUG {timestamp}] <-- async '{func_name}' returned: {result_str}\n  Duration: {formatted_duration}")
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            caller = inspect.stack()[1].function
            func_name = func.__name__

            effective_args = args
            try:
                inspect.signature(func).bind_partial(*effective_args, **kwargs)
            except TypeError:
                if len(effective_args) > 0:
                    effective_args = effective_args[1:]

            log_debug(f"\n[DEBUG {timestamp}] --> '{func_name}' called from '{caller}'\n  |-- Args: {args}\n  |-- Kwargs: {kwargs}")

            start_time = time.perf_counter()
            try:
                result = func(*effective_args, **kwargs)
            except Exception as e:
                log_debug(f"[DEBUG {timestamp}] '{func_name}' raised: {e}")
                raise
            end_time = time.perf_counter()

            # --- CHANGE HERE for milliseconds ---
            duration_ms = (end_time - start_time) * 1000
            formatted_duration = f"{duration_ms:.2f}ms"
            # --- END CHANGE ---

            result_str = str(result)
            if len(result_str) > max_output_len:
                result_str = result_str[:max_output_len] + " ... [truncated]"

            log_debug(f"[DEBUG {timestamp}] <-- '{func_name}' returned: {result_str}\n  Duration: {formatted_duration}")
            return result

        return async_wrapper if is_coroutine else sync_wrapper

    return decorator

# --- CLASS AUTO-WRAPPING ---
def auto_debug_class(cls):
    for attr_name in dir(cls):
        if attr_name.startswith("__"):
            continue
        attr = getattr(cls, attr_name)
        if callable(attr) and not isinstance(attr, (staticmethod, classmethod)):
            setattr(cls, attr_name, debug_log()(attr))
    return cls

# --- OPTIONAL DEV MODE STARTUP PRINTS ---
if __name__ == "__main__" or debug_config.get("verbose_startup"):
    safe_print(f"Loading config from: {DEBUG_CONFIG["full_path"]}")
    safe_print("Full config:\n" + json.dumps(full_config, indent=2))
    safe_print("Debug config:\n" + json.dumps(debug_config, indent=2))
    safe_print(f"Logging to file: {log_file_path}")
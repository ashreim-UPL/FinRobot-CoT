from autogen import register_function, ConversableAgent
from .data_source import *
from .functional.coding import CodingUtils

from typing import List, Callable, Any, Union
from functools import wraps
from pandas import DataFrame
import inspect

def stringify_output(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, DataFrame):
            return result.to_string()
        else:
            return str(result)

    return wrapper

def safe_bound_wrapper(func):
    """Wrap bound methods to ignore 'self' if it's incorrectly passed."""
    def wrapper(**kwargs):
        if 'self' in kwargs:
            del kwargs['self']
        return func(**kwargs)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def register_toolkits(
    config: List[dict | Callable | type],
    caller: ConversableAgent,
    executor: ConversableAgent,
    **kwargs
):
    """Register tools from a configuration list."""
    for entry in config:

        # Case 1: If it's a class → instantiate and register all bound methods
        if isinstance(entry, type):
            print(f"[INFO] Instantiating toolkit class: {entry.__name__}")
            instance = entry()
            register_tookits_from_cls(caller, executor, entry, instance=instance, **kwargs)
            continue

        # Case 2: If it's an instance → register bound methods
        if hasattr(entry, "__class__") and not callable(entry):
            register_tookits_from_cls(caller, executor, entry.__class__, instance=entry, **kwargs)
            continue

        # Case 3: If it's a function or dictionary definition
        tool_dict = {"function": entry} if callable(entry) else entry
        if "function" not in tool_dict or not callable(tool_dict["function"]):
            raise ValueError("Function not found in tool configuration or not callable.")

        tool_function = tool_dict["function"]

        # Wrap if method (to remove 'self')
        if inspect.ismethod(tool_function):
            tool_function = safe_bound_wrapper(tool_function)

        name = tool_dict.get("name", getattr(tool_function, "__name__", "unnamed_tool"))
        description = tool_dict.get("description", getattr(tool_function, "__doc__", ""))

        print(f"\nRegistering tool: {name}")
        print(f"Function: {tool_function}")
        print(f"Signature: {inspect.signature(tool_function)}")
        print(f"Annotations: {getattr(tool_function, '__annotations__', {})}\n")

        register_function(
            stringify_output(tool_function),
            caller=caller,
            executor=executor,
            name=name,
            description=description,
        )



def register_code_writing(caller: ConversableAgent, executor: ConversableAgent):
    """Register code writing tools."""

    register_toolkits(
        [
            {
                "function": CodingUtils.list_dir,
                "name": "list_files",
                "description": "List files in a directory.",
            },
            {
                "function": CodingUtils.see_file,
                "name": "see_file",
                "description": "Check the contents of a chosen file.",
            },
            {
                "function": CodingUtils.modify_code,
                "name": "modify_code",
                "description": "Replace old piece of code with new one.",
            },
            {
                "function": CodingUtils.create_file_with_code,
                "name": "create_file_with_code",
                "description": "Create a new file with provided code.",
            },
        ],
        caller,
        executor,
    )


def register_tookits_from_cls(caller, executor, cls, instance=None, **kwargs):
    if instance is None:
        instance = cls()

    for attr_name in dir(instance):
        if attr_name.startswith("_"):
            continue

        attr = getattr(instance, attr_name)
        if not callable(attr):
            continue

        name = getattr(attr, "__name__", attr_name)
        description = getattr(attr, "__doc__", "")

        print(f"[INFO] Registering bound method: {name} from {cls.__name__}")

        register_function(
            stringify_output(attr),
            caller=caller,
            executor=executor,
            name=name,
            description=description,
        )

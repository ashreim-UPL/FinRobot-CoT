
from pathlib import Path
import os
from typing import List, Annotated

class TextUtils:
    """
    A collection of static utility functions for text and file manipulation.
    """
    @staticmethod
    def list_available_files(directory: str, ext: str = ".txt"):
        from pathlib import Path
        path = Path(directory)
        if not path.is_dir():
            return []
        return [f.name for f in path.iterdir() if f.is_file() and f.suffix.lower() == ext.lower()]
            
    @staticmethod
    def check_text_length(
        text: Annotated[str, "The text content whose word count is to be checked."],
        min_length: Annotated[int, "The minimum required number of words. Default is 0."] = 0,
        max_length: Annotated[int, "The maximum allowed number of words. Default is 100000."] = 100000,
    ) -> str:
        """
        Checks if the word count of a given text is within a specified min/max range.
        """
        # Split by whitespace to count words
        length = len(text.split())
        if length > max_length:
            return f"Error: Text length of {length} words exceeds the maximum of {max_length}."
        elif length < min_length:
            return f"Error: Text length of {length} words is less than the minimum of {min_length}."
        else:
            return f"Success: Text length of {length} words is within the expected range."

    @staticmethod
    def read_file_content(
        file_path: Annotated[str, "The full, absolute, or relative path to the text file to be read."]
    ) -> str:
        """
        Reads and returns the entire content of a specified text file.
        Returns an error message if the file is not found or cannot be read.
        """
        if not os.path.exists(file_path):
            return f"Error: File not found at the specified path: {file_path}"
        # Allow ONLY .txt files
        _, ext = os.path.splitext(file_path)
        if ext.lower() != '.txt':
            return f"Error: Only .txt files are permitted. Attempted: {file_path}"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            # Capturing the root cause of the error is crucial for debugging
            return f"Error: Could not read file at {file_path}. Root cause: {e}"

    @staticmethod
    def save_to_file(
        data: Annotated[str, "The string content that needs to be written to the file."],
        file_path: Annotated[str, "The full destination path, including the filename and extension (e.g., 'C:/reports/summary.txt')."]
    ) -> str:
        """
        Saves the provided string data to a file at the specified file path.
        This function will create parent directories if they do not exist.
        """
        try:
            # Ensure the directory for the file exists.
            # os.path.dirname() gets the directory part of the path.
            parent_directory = os.path.dirname(file_path)
            if parent_directory: # Check if there is a directory part
                 os.makedirs(parent_directory, exist_ok=True)
            
            # Write the data to the file with UTF-8 encoding
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(data)
                
            return f"Success: Data was successfully saved to {file_path}"
        except Exception as e:
            return f"Error: Could not save file to {file_path}. Root cause: {e}"

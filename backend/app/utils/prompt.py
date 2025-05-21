def read_file_as_text(file_path):
    """
    Read the content of a file as text.

    Args:
        file_path (str): Path to the file to be read

    Returns:
        str: Content of the file as text, or None if file cannot be read
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

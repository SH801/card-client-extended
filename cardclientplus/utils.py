from typing import Any, Iterable

from yaml import safe_load


def load_yaml_file(file_path: str):
    with open(file_path, "r") as file_content:
        return safe_load(file_content)


def chunks(list: Iterable[Any], chunk_size: int):
    for i in range(0, len(list), chunk_size):
        yield list[i : i + chunk_size]

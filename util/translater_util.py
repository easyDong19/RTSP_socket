import os
from datetime import datetime


def ensure_directory_exists(directory_url: str) -> None:
    if not os.path.exists(directory_url):
        os.makedirs(directory_url)
        print(f"directory_url '{directory_url}' created.")
    else:
        print(f"directory_url '{directory_url}' already exists.")


def get_server_date() -> str:
    now = datetime.now()
    current_time = now.strftime("%Y_%m_%d")
    return current_time

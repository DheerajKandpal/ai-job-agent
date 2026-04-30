import requests


def parse_jobs(input_data):
    if isinstance(input_data, str):
        if input_data.startswith("http"):
            try:
                r = requests.get(input_data, timeout=5)
                text = r.text
                clean = text.replace("<", " ").replace(">", " ")
                return [clean[:2000]]
            except Exception:
                return [input_data]

        return [input_data]

    if isinstance(input_data, list):
        return input_data

    return []

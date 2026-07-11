import json
from pathlib import Path

from knowledge_base import normalize_jobs


class DataLoadError(Exception):
    """Raised when a required local configuration file cannot be loaded."""


BASE_DIR = Path(__file__).resolve().parent


def load_json(filename):
    path = BASE_DIR / filename
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as exc:
        raise DataLoadError(f"没有找到配置文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise DataLoadError(f"配置文件 JSON 格式有误：{path}\n{exc}") from exc


def load_optional_json(filename, default):
    path = BASE_DIR / filename
    if not path.exists():
        return default
    return load_json(filename)


def load_all_data():
    majors = load_optional_json("majors.json", [])
    conditional_questions = load_optional_json("conditional_questions.json", {"question_groups": {}})
    major_normalization = load_optional_json("major_normalization.json", {"canonical_majors": []})
    options = load_json("options_config.json")
    options["majors"] = majors
    options["conditional_questions"] = conditional_questions
    options["major_normalization"] = major_normalization
    return {
        "jobs": normalize_jobs(load_json("job_data.json")),
        "options": options,
        "rules": load_json("rules_config.json"),
        "majors": majors,
        "conditional_questions": conditional_questions,
        "major_normalization": major_normalization,
    }

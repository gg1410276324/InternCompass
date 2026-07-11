import csv
import json
import uuid
from datetime import datetime
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "data"
USER_RUNS_PATH = DATA_DIR / "user_runs.jsonl"
FEEDBACK_PATH = DATA_DIR / "feedback_dataset.csv"

RUN_FIELDS = [
    "run_id",
    "timestamp",
    "education_level",
    "current_stage",
    "grade",
    "major",
    "normalized_major",
    "major_group",
    "major_intention",
    "base_answers",
    "conditional_answers",
    "interests",
    "skills",
    "avoid_tags",
    "priority_jobs",
    "explore_jobs",
    "not_recommend_jobs",
    "job_scores",
    "clicked_jobs",
    "feedback_accuracy",
    "feedback_interested_jobs",
    "feedback_unsuitable_jobs",
    "feedback_missing_jobs",
    "feedback_comment",
]


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _job_names(recommendations, level):
    return [item["job"]["job_name"] for item in recommendations.get(level, [])]


def _job_scores(recommendations):
    return {
        item["job"].get("job_id") or item["job"]["job_name"]: item["score"]
        for item in recommendations.get("all", [])
    }


def build_run_record(profile, recommendations, clicked_jobs=None, feedback=None):
    feedback = feedback or {}
    return {
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "education_level": profile.get("education_level", ""),
        "current_stage": profile.get("current_stage", ""),
        "grade": profile.get("grade", ""),
        "major": profile.get("major", ""),
        "normalized_major": profile.get("normalized_major", {}),
        "major_group": profile.get("major_group", ""),
        "major_intention": profile.get("major_preference", ""),
        "base_answers": {
            "frontline_acceptance": profile.get("frontline_acceptance", ""),
        },
        "conditional_answers": profile.get("conditional_answers", {}),
        "interests": profile.get("interests", []),
        "skills": profile.get("skills", []),
        "avoid_tags": profile.get("avoid_tasks", []),
        "priority_jobs": _job_names(recommendations, "优先推荐"),
        "explore_jobs": _job_names(recommendations, "可探索"),
        "not_recommend_jobs": _job_names(recommendations, "暂不推荐"),
        "job_scores": _job_scores(recommendations),
        "clicked_jobs": clicked_jobs or [],
        "feedback_accuracy": feedback.get("accuracy", ""),
        "feedback_interested_jobs": feedback.get("interested_jobs", []),
        "feedback_unsuitable_jobs": feedback.get("unsuitable_jobs", []),
        "feedback_missing_jobs": feedback.get("missing_jobs", []),
        "feedback_comment": feedback.get("comment", ""),
    }


def save_user_run(profile, recommendations, clicked_jobs=None, feedback=None):
    _ensure_data_dir()
    record = build_run_record(profile, recommendations, clicked_jobs, feedback)
    with USER_RUNS_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def append_feedback(run_id, feedback):
    _ensure_data_dir()
    fieldnames = [
        "run_id",
        "timestamp",
        "feedback_accuracy",
        "feedback_interested_jobs",
        "feedback_unsuitable_jobs",
        "feedback_missing_jobs",
        "feedback_comment",
    ]
    exists = FEEDBACK_PATH.exists()
    with FEEDBACK_PATH.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "feedback_accuracy": feedback.get("accuracy", ""),
                "feedback_interested_jobs": "、".join(feedback.get("interested_jobs", [])),
                "feedback_unsuitable_jobs": "、".join(feedback.get("unsuitable_jobs", [])),
                "feedback_missing_jobs": "、".join(feedback.get("missing_jobs", [])),
                "feedback_comment": feedback.get("comment", ""),
            }
        )

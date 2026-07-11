from datetime import datetime
from pathlib import Path


def _join(values):
    return "、".join(values) if values else "无"


def generate_markdown_report(profile, recommendations):
    lines = [
        "# Intern Compass 实习岗位方向推荐报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 用户画像",
        "",
        f"- 学历层次：{profile.get('education_level', '')}",
        f"- 当前阶段：{profile.get('current_stage') or profile.get('grade', '')}",
        f"- 专业：{profile.get('major', '')}",
        f"- 专业类别：{profile.get('major_group', '')}",
        f"- 专业对口意愿：{profile.get('major_preference', '')}",
        f"- 一线场景接受度：{profile.get('frontline_acceptance', '')}",
        f"- 专业补充问题：{_format_conditional_answers(profile.get('conditional_answers', {}))}",
        f"- 喜欢的工作内容：{_join(profile.get('interests', []))}",
        f"- 当前能力：{_join(profile.get('skills', []))}",
        f"- 不想做的工作：{_join(profile.get('avoid_tasks', []))}",
        "",
    ]

    for level in ["优先推荐", "可探索", "暂不推荐"]:
        lines.extend([f"## {level}", ""])
        items = recommendations.get(level, [])
        if not items:
            lines.extend(["暂无结果。", ""])
            continue
        for item in items:
            job = item["job"]
            title = job.get("display_name") or job["job_name"]
            alias_note = f"- 真实招聘常见名称：{_join(job.get('posting_aliases', []))}" if job.get("posting_aliases") else ""
            lines.extend(
                [
                    f"### {title}（{item['score']} 分）",
                    "",
                    f"- 原始岗位方向：{job['job_name']}",
                    f"- 岗位类别：{job.get('category_lv1') or job.get('category', '')}",
                    f"- 推荐理由：{' '.join(item['reasons'])}",
                    alias_note,
                    f"- 学历适配提示：{_education_note(item)}",
                    f"- 岗位所需技能：{_join(job.get('required_skills', []))}",
                    f"- 用户已匹配能力：{_join(item.get('matched_skills', []))}",
                    f"- 用户需要补充的能力：{_join(item.get('missing_skills', []))}",
                    f"- 准备建议：{job.get('preparation_advice', '')}",
                    f"- 简历关键词：{_join(job.get('resume_keywords', []))}",
                    "",
                ]
            )
    return "\n".join(lines)


def _education_note(item):
    for reason in item.get("reasons", []):
        if "学历" in reason:
            return reason
    return "无"


def _format_conditional_answers(answers):
    if not answers:
        return "无"
    return "；".join(f"{key}={value}" for key, value in answers.items())


def export_report(profile, recommendations, output_path=None):
    output = Path(output_path or Path(__file__).resolve().parent / "report.md")
    output.write_text(generate_markdown_report(profile, recommendations), encoding="utf-8")
    return output

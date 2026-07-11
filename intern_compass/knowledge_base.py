import re


ARRAY_FIELDS = [
    "aliases",
    "industry_tags",
    "suitable_major_groups",
    "suitable_majors",
    "required_skills",
    "plus_skills",
    "soft_skills",
    "interest_tags",
    "scene_tags",
    "avoid_tags",
    "daily_tasks",
    "resume_keywords",
    "not_suitable_for",
    "search_keywords",
    "required_major_groups",
    "excluded_major_groups",
    "parent_track",
    "posting_aliases",
]


def normalize_text(value):
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_job(job):
    normalized = dict(job)
    normalized.setdefault("job_id", "")
    normalized.setdefault("job_name", "")
    normalized.setdefault("category", normalized.get("category_lv1", "其他"))
    normalized.setdefault("category_lv1", normalized.get("category", "其他"))
    normalized.setdefault("category_lv2", normalized.get("category", "其他"))
    normalized.setdefault("major_relevance", "低专业限制")
    normalized.setdefault("open_to_non_related_major", normalized["major_relevance"] in ("低专业限制", "跨专业可选"))
    normalized.setdefault("difficulty", "中")
    normalized.setdefault("growth_value", "中")
    normalized.setdefault("entry_level", "适合入门探索")
    normalized.setdefault("description", "")
    normalized.setdefault("preparation_advice", "")
    normalized.setdefault("strict_major_required", False)
    normalized.setdefault("professional_access_note", "")
    education_requirement = normalized.get("education_requirement") or {}
    normalized["education_requirement"] = {
        "min_education": education_requirement.get("min_education", "专科"),
        "preferred_education": as_list(education_requirement.get("preferred_education")),
        "strict": bool(education_requirement.get("strict", False)),
    }
    for field in ARRAY_FIELDS:
        normalized[field] = as_list(normalized.get(field))
    if not normalized.get("interest_tags"):
        normalized["interest_tags"] = as_list(normalized.get("interests"))
    normalized["interests"] = as_list(normalized.get("interests") or normalized.get("interest_tags"))
    normalized["search_keywords"] = list(
        dict.fromkeys(
            [
                *normalized["search_keywords"],
                normalized["job_name"],
                normalized.get("display_name", ""),
                normalized["category"],
                normalized["category_lv1"],
                normalized["category_lv2"],
                *normalized["aliases"],
                *normalized["suitable_majors"],
                *normalized["suitable_major_groups"],
                *normalized["required_skills"],
                *normalized["resume_keywords"],
                *normalized["parent_track"],
                *normalized["posting_aliases"],
            ]
        )
    )
    return normalized


def normalize_jobs(jobs):
    return [normalize_job(job) for job in jobs]


def _major_terms(major):
    terms = [
        major.get("major_name", ""),
        major.get("major_group", ""),
        *as_list(major.get("aliases")),
        *as_list(major.get("keywords")),
        *as_list(major.get("search_keywords")),
    ]
    return [term for term in terms if str(term).strip()]


def _major_match_score(needle, major):
    name = normalize_text(major.get("major_name", ""))
    aliases = [normalize_text(term) for term in as_list(major.get("aliases"))]
    keywords = [normalize_text(term) for term in as_list(major.get("keywords"))]
    search_keywords = [normalize_text(term) for term in as_list(major.get("search_keywords"))]
    major_group = normalize_text(major.get("major_group", ""))

    if needle == name:
        return 600
    if name.startswith(needle):
        return 500
    if needle in name:
        return 400

    alias_terms = aliases + keywords + search_keywords
    if any(needle == term for term in alias_terms):
        return 320
    if any(term.startswith(needle) for term in alias_terms):
        return 280
    if any(needle in term or term in needle for term in alias_terms):
        return 240
    if needle and needle in major_group:
        return 180
    return 0


def find_major(major_name, majors):
    target = normalize_text(major_name)
    if not target:
        return None
    for major in majors:
        if target == normalize_text(major.get("major_name", "")):
            return major
        if any(target == normalize_text(term) for term in _major_terms(major)):
            return major
    return None


def _normalization_entries(options_config):
    return options_config.get("major_normalization", {}).get("canonical_majors", [])


def normalize_major(input_major, options_config, majors=None):
    input_text = str(input_major or "").strip()
    target = normalize_text(input_text)
    for entry in _normalization_entries(options_config):
        terms = [
            entry.get("canonical_major_name", ""),
            entry.get("major_group", ""),
            *as_list(entry.get("related_groups")),
            *as_list(entry.get("aliases")),
        ]
        if any(target == normalize_text(term) for term in terms):
            return {
                "input_major": input_text,
                "canonical_major_id": entry.get("canonical_major_id", ""),
                "canonical_major_name": entry.get("canonical_major_name", input_text),
                "major_group": entry.get("major_group", "通用类"),
                "related_groups": as_list(entry.get("related_groups")) or [entry.get("major_group", "通用类")],
                "barrier_level": entry.get("barrier_level", ""),
                "aliases": as_list(entry.get("aliases")),
                "industry_keywords": as_list(entry.get("industry_keywords")),
            }

    majors = majors or options_config.get("majors", [])
    matched = find_major(input_text, majors)
    if matched:
        group = matched.get("major_group", "通用类")
        return {
            "input_major": input_text,
            "canonical_major_id": matched.get("major_id", ""),
            "canonical_major_name": matched.get("major_name", input_text),
            "major_group": group,
            "related_groups": [group],
            "barrier_level": matched.get("barrier_level", ""),
            "aliases": as_list(matched.get("aliases")),
            "industry_keywords": as_list(matched.get("search_keywords")),
        }

    group = _fallback_major_group(input_text, options_config)
    return {
        "input_major": input_text,
        "canonical_major_id": "",
        "canonical_major_name": input_text,
        "major_group": group,
        "related_groups": [group],
        "barrier_level": "",
        "aliases": [],
        "industry_keywords": [],
    }


def search_majors(query, majors, limit=8):
    needle = normalize_text(query)
    if not needle:
        return []
    scored = []
    for index, major in enumerate(majors):
        score = _major_match_score(needle, major)
        if score:
            scored.append((score, major, index))
    scored.sort(
        key=lambda item: (
            -item[0],
            -int(item[1].get("popularity_score", 0) or 0),
            int(item[1].get("display_order", 9999) or 9999),
            item[2],
            item[1].get("major_name", ""),
        )
    )
    return [major for _score, major, _index in scored[:limit]]


def major_group_for_major(major_name, options_config, majors=None):
    return normalize_major(major_name, options_config, majors).get("major_group", "通用类")


def _fallback_major_group(major_name, options_config):
    normalized = str(major_name or "").strip()
    mapping = options_config.get("major_category_mapping", {})
    for group, names in mapping.items():
        if normalized in names:
            return group
    if any(token in normalized for token in ("计算机", "软件", "人工智能", "数据", "网络", "信息安全")):
        return "计算机类"
    if any(token in normalized for token in ("口腔", "齿科")):
        return "口腔医学类"
    if any(token in normalized for token in ("医学", "护理", "药学", "临床", "康复")):
        return "医药健康类"
    if any(token in normalized for token in ("动物", "兽医", "畜牧", "水产")):
        return "动物医学与动保类"
    if any(token in normalized for token in ("市场", "工商", "电商", "会计", "财务", "审计", "贸易")):
        return "商科管理类"
    if any(token in normalized for token in ("新闻", "传播", "广告", "新媒体", "英语")):
        return "文学传播类"
    if "法" in normalized:
        return "法学公共管理类"
    return "通用类"


def conditional_group_for_major(major_name, options_config, majors=None):
    majors = majors or options_config.get("majors", [])
    normalized = normalize_major(major_name, options_config, majors)
    matched = find_major(normalized.get("canonical_major_name", major_name), majors) or find_major(major_name, majors)
    if matched:
        return matched.get("conditional_question_group", "")
    candidate_groups = [normalized.get("major_group"), *as_list(normalized.get("related_groups"))]
    questions = options_config.get("conditional_questions", {}).get("question_groups", {})
    for group_id, config in questions.items():
        if any(group in config.get("major_groups", []) for group in candidate_groups):
            return group_id
    return ""

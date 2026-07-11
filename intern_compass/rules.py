from collections import defaultdict

from knowledge_base import as_list, major_group_for_major, normalize_major


def _as_set(values):
    return {str(item).strip() for item in values if str(item).strip()}


def _major_group(major, options_config):
    return major_group_for_major(major, options_config)


def _overlap_score(selected, target):
    selected_set = _as_set(selected)
    target_set = _as_set(target)
    if not target_set:
        return 0
    return min(len(selected_set & target_set) / max(len(target_set), 1), 1)


STRONG_BARRIER_GROUPS = {
    "临床医学类",
    "口腔医学类",
    "动物医学类",
    "动物医学与动保类",
    "药学类",
    "护理学类",
    "医学技术类",
    "法学类",
    "法学公共管理类",
    "财会类",
    "计算机类",
    "工程制造类",
}


def _profile_groups(profile):
    normalized = profile.get("normalized_major") or {}
    major_group = normalized.get("major_group", "")
    return _as_set(as_list(normalized.get("related_groups")) + [major_group])


def _is_strong_barrier_profile(profile):
    return bool(_profile_groups(profile) & STRONG_BARRIER_GROUPS)


def _major_score(profile, job, options_config, rules_config):
    major = profile.get("major", "")
    preference = profile.get("major_preference", "")
    normalized = profile.get("normalized_major") or normalize_major(major, options_config)
    major_group = normalized.get("major_group", _major_group(major, options_config))
    related_groups = _as_set(as_list(normalized.get("related_groups")) + [major_group])
    aliases = _as_set(as_list(normalized.get("aliases")) + [major, normalized.get("canonical_major_name", "")])
    industry_keywords = _as_set(as_list(normalized.get("industry_keywords")))
    suitable = _as_set(job.get("suitable_majors", []))
    suitable_groups = _as_set(job.get("suitable_major_groups", []))
    required_groups = _as_set(job.get("required_major_groups", []))
    excluded_groups = _as_set(job.get("excluded_major_groups", []))
    job_terms = _as_set(
        job.get("suitable_majors", [])
        + job.get("suitable_major_groups", [])
        + job.get("industry_tags", [])
        + job.get("search_keywords", [])
        + job.get("resume_keywords", [])
        + [job.get("job_name", ""), job.get("description", ""), job.get("category", ""), job.get("category_lv1", ""), job.get("category_lv2", "")]
    )
    relevance = job.get("major_relevance", "低专业限制")
    scores = rules_config.get("major_relevance_scores", {})

    if excluded_groups & related_groups:
        return 0.18
    if job.get("strict_major_required") and required_groups and not (required_groups & related_groups):
        return 0.18

    exact_match = major in suitable
    canonical_match = normalized.get("canonical_major_name") in suitable or normalized.get("canonical_major_id") in suitable
    group_match = bool((related_groups & suitable_groups) or (related_groups & suitable) or (related_groups & required_groups))
    alias_match = bool(aliases & (suitable | job_terms))
    industry_match = bool(industry_keywords & job_terms)
    base = 0.35
    if exact_match or canonical_match:
        base = 1
    elif group_match:
        base = 0.92 if relevance == "强专业对口" else 0.84
    elif alias_match or industry_match:
        base = 0.82 if relevance != "低专业限制" else 0.72
    elif relevance in ("低专业限制", "跨专业可选"):
        base = 0.62

    preference_factor = scores.get(preference, {}).get(relevance, 0.65)
    return min(base * preference_factor, 1)


def _professional_access(profile, job):
    normalized = profile.get("normalized_major") or {}
    major_group = normalized.get("major_group", "")
    candidate_groups = _as_set(as_list(normalized.get("related_groups")) + [major_group])
    required_groups = _as_set(job.get("required_major_groups", []))
    excluded_groups = _as_set(job.get("excluded_major_groups", []))
    strict = bool(job.get("strict_major_required", False))
    note = job.get("professional_access_note", "")

    if excluded_groups & candidate_groups:
        return {
            "score_cap": 0.18 if strict else 0.45,
            "strict_blocked": strict,
            "downgrade": True,
            "notes": [note or "该岗位通常有明确专业准入限制，当前专业不优先推荐。"],
        }

    if required_groups and not (required_groups & candidate_groups):
        if strict:
            return {
                "score_cap": 0.18,
                "strict_blocked": True,
                "downgrade": True,
                "notes": [note or "该岗位通常有明确专业准入限制，当前专业不优先推荐。"],
            }
        return {
            "score_cap": 0.62,
            "strict_blocked": False,
            "downgrade": True,
            "notes": [note or "该岗位更偏向特定专业背景，当前专业建议作为可探索方向。"],
        }

    return {
        "score_cap": 1,
        "strict_blocked": False,
        "downgrade": False,
        "notes": [],
    }


def _professional_relevance_tier(profile, job):
    normalized = profile.get("normalized_major") or {}
    major = profile.get("major", "")
    candidate_groups = _profile_groups(profile)
    candidate_majors = _as_set([major, normalized.get("canonical_major_name", ""), normalized.get("canonical_major_id", "")])
    suitable = _as_set(job.get("suitable_majors", []))
    groups = _as_set(job.get("suitable_major_groups", [])) | _as_set(job.get("required_major_groups", []))
    relevance = job.get("major_relevance", "低专业限制")
    matched = bool((candidate_groups & groups) or (candidate_groups & suitable) or (candidate_majors & suitable))

    if relevance == "强专业对口" and matched:
        return 4
    if relevance == "弱专业相关" and matched:
        return 3
    if relevance == "低专业限制":
        return 2
    if relevance == "跨专业可选":
        return 1
    return 0


def _professional_relevance_floor(profile, job):
    if profile.get("major_preference") == "跨专业探索":
        return 0, []
    if not _is_strong_barrier_profile(profile):
        return 0, []

    tier = _professional_relevance_tier(profile, job)
    if tier == 4:
        return 85, [f"你的专业属于{profile.get('normalized_major', {}).get('major_group', '相关专业类')}，与该岗位具有较强专业相关性，因此优先推荐。"]
    if tier == 3:
        return 75, [f"你的专业属于{profile.get('normalized_major', {}).get('major_group', '相关专业类')}，该岗位可作为专业弱相关方向优先探索。"]
    return 0, []


def _grade_score(grade, job, rules_config):
    fit = rules_config.get("grade_fit", {}).get(grade, {})
    difficulty = job.get("difficulty", "中")
    return fit.get(difficulty, 0.75)


def _stage_score(stage, job, rules_config):
    fit = rules_config.get("stage_fit", {}).get(stage, {})
    difficulty = job.get("difficulty", "中")
    return fit.get(difficulty, 0.75)


def _education_fit(profile, job, rules_config):
    rank = rules_config.get("education_levels_rank", {})
    level = profile.get("education_level") or "本科"
    requirement = job.get("education_requirement") or {}
    min_education = requirement.get("min_education", "专科")
    preferred = requirement.get("preferred_education", []) or []
    strict = bool(requirement.get("strict", False))

    user_rank = rank.get(level, rank.get("本科", 2))
    min_rank = rank.get(min_education, rank.get("专科", 1))
    notes = []
    downgrade = False

    if user_rank < min_rank:
        if strict:
            score = 0.35
            downgrade = True
            notes.append("该方向对学历和项目经历要求较高，建议作为进阶目标。")
        else:
            score = 0.62
            notes.append("该方向通常更偏本科及以上，当前可以作为可探索方向。")
    elif preferred and level in preferred:
        score = 1.0
        notes.append("你的学历层次与该岗位常见要求较匹配。")
    elif min_education == "专科":
        score = 0.92
        notes.append("该岗位方向通常对学历要求不高，可以作为入门探索。")
    else:
        score = 0.84
        notes.append("当前学历层次基本满足该方向的常见要求。")

    return score, notes, downgrade


def _growth_score(job):
    return {"低": 0.45, "中": 0.75, "高": 1}.get(job.get("growth_value", "中"), 0.75)


def _downgrade_hits(profile, job, rules_config):
    avoid_selected = _as_set(profile.get("avoid_tasks", []))
    job_tags = _as_set(job.get("avoid_tags", []))
    hits = sorted(avoid_selected & job_tags)

    frontline = profile.get("frontline_acceptance", "")
    if frontline == "不接受一线，更想做非技术岗位" and ("临床一线" in job_tags or "养殖场环境" in job_tags):
        hits.append("不接受一线场景")
    if frontline == "只想做专业相关的办公室岗位" and ("临床一线" in job_tags or "体力劳动" in job_tags):
        hits.append("偏好办公室岗位")

    forced = rules_config.get("forced_downgrade_tags", [])
    forced_hits = [tag for tag in forced if tag in avoid_selected and tag in job_tags]
    hits.extend(forced_hits)
    hits.extend(_conditional_avoid_hits(profile, job))
    return sorted(set(hits))


def _conditional_questions(options_config):
    return options_config.get("conditional_questions", {}).get("question_groups", {})


def _iter_conditional_effects(profile, options_config):
    answers = profile.get("conditional_answers", {}) or {}
    for group in _conditional_questions(options_config).values():
        for question in group.get("questions", []):
            answer = answers.get(question.get("id"))
            effects = question.get("effects", {}).get(answer)
            if effects:
                yield question, effects


def _conditional_avoid_hits(profile, job):
    job_tags = _as_set(job.get("avoid_tags", []))
    hits = []
    for question, effects in _iter_conditional_effects(profile, profile.get("_options_config", {})):
        for tag in effects.get("avoid_tags", []):
            if tag in job_tags:
                hits.append(f"{question.get('text', '补充问题')}：{tag}")
    return hits


def _conditional_adjustment(profile, job, options_config, rules_config):
    adjustment = 0
    notes = []
    job_id = job.get("job_id")
    job_tags = _as_set(job.get("avoid_tags", []))
    for question, effects in _iter_conditional_effects(profile, options_config):
        if job_id in effects.get("boost_job_ids", []):
            adjustment += rules_config.get("conditional_boost_score", 5)
            notes.append(f"补充问题加分：{question.get('text', '')}")
        if job_id in effects.get("penalty_job_ids", []):
            adjustment -= rules_config.get("conditional_penalty_score", 10)
            notes.append(f"补充问题降级：{question.get('text', '')}")
        if job_tags & _as_set(effects.get("avoid_tags", [])):
            adjustment -= rules_config.get("conditional_penalty_score", 10)
    return adjustment, notes


def _special_adjustment(profile, job, options_config, rules_config):
    normalized = profile.get("normalized_major") or normalize_major(profile.get("major", ""), options_config)
    candidate_groups = [normalized.get("major_group"), *as_list(normalized.get("related_groups"))]
    candidate_group_set = _as_set(candidate_groups)
    required_groups = _as_set(job.get("required_major_groups", []))
    excluded_groups = _as_set(job.get("excluded_major_groups", []))
    if excluded_groups & candidate_group_set:
        return 0, []
    if job.get("strict_major_required") and required_groups and not (required_groups & candidate_group_set):
        return 0, []
    preference = profile.get("major_preference", "")
    job_name = job.get("job_name", "")
    adjustment = 0
    notes = []

    special_rules = rules_config.get("special_major_rules", {})
    preferred_jobs = []
    strong_related_jobs = []
    weak_related_jobs = []
    cross_related_jobs = []
    for group in candidate_groups:
        preferred_jobs.extend(special_rules.get(group, {}).get(preference, []))
        strong_related_jobs.extend(special_rules.get(group, {}).get("强专业对口", []))
        weak_related_jobs.extend(special_rules.get(group, {}).get("弱专业相关", []))
        cross_related_jobs.extend(special_rules.get(group, {}).get("跨专业探索", []))
    if preference == "不确定，想都看看":
        if job_name in strong_related_jobs and required_groups & candidate_group_set:
            adjustment += rules_config.get("special_boost_score", 6)
            notes.append("不确定时优先保留当前专业强相关方向")
        elif job_name in weak_related_jobs:
            adjustment += 4
            notes.append("不确定时该岗位可作为专业弱相关方向")
        elif job_name in cross_related_jobs:
            adjustment += 1
            notes.append("不确定时该岗位可作为跨专业补充方向")
        preferred_jobs = []
    if job_name in preferred_jobs:
        adjustment += rules_config.get("special_boost_score", 6)
        notes.append("符合该专业和专业对口意愿的优先方向")
        if required_groups & candidate_group_set:
            adjustment += 4
        if preference == "弱专业相关" and job_name in strong_related_jobs and required_groups & candidate_group_set:
            adjustment += 4
            notes.append("虽然你选择弱专业相关，但该岗位仍属于当前专业的核心相关方向")
    elif preference == "弱专业相关":
        if job_name in strong_related_jobs and required_groups & candidate_group_set:
            adjustment += 4
            notes.append("虽然你选择弱专业相关，但该岗位仍属于当前专业的核心相关方向")

    interests = _as_set(profile.get("interests", []))
    is_computer_major = "计算机类" in candidate_groups
    if "写代码 / 技术开发" in interests and not is_computer_major:
        entry_jobs = set(special_rules.get("非计算机转技术", {}).get("可探索", []))
        hard_jobs = set(special_rules.get("非计算机转技术", {}).get("高门槛", []))
        if job_name in entry_jobs:
            adjustment += 2
            notes.append("非计算机专业转技术可作为入门探索方向")
        if job_name in hard_jobs:
            adjustment -= 10
            notes.append("非计算机专业直接进入高门槛开发方向需要额外准备")

    return adjustment, notes


INDUSTRY_SCOPE_LABELS = {
    "dental": "口腔/齿科/医疗器械",
    "pet": "宠物医疗",
    "animal_medicine": "动物医学/动保/兽药",
    "pharma": "医药/药学",
    "medical": "医疗健康",
    "general": "通用岗位",
}

INDUSTRY_SCOPE_MAJOR_GROUPS = {
    "dental": {"口腔医学类", "医学技术类"},
    "pet": {"动物医学类", "动物医学与动保类", "动物科学类"},
    "animal_medicine": {"动物医学类", "动物医学与动保类", "动物科学类", "药学类"},
    "pharma": {"药学类", "临床医学类", "医学技术类", "医药健康类"},
    "medical": {"临床医学类", "护理学类", "医学技术类", "医药健康类", "药学类", "口腔医学类"},
}

INDUSTRY_SCOPE_INTEREST_TERMS = {
    "dental": {"口腔健康", "医疗健康", "口腔", "齿科", "牙科"},
    "pet": {"宠物医疗", "宠物", "动物", "动保行业"},
    "animal_medicine": {"宠物医疗", "动保行业", "动物", "兽药", "畜牧"},
    "pharma": {"医药行业", "医疗健康", "药学", "制药"},
    "medical": {"医疗健康", "医药行业", "医学", "医院"},
}

BUSINESS_GENERAL_GROUPS = {"商科管理类", "财会类"}
GENERAL_ROLE_FAMILIES = {"产品", "市场", "运营", "商务", "项目", "数据分析", "内容"}
PROBLEM_INDUSTRY_SCOPES = {"dental", "pet", "animal_medicine", "pharma", "medical"}


def _profile_text(profile):
    normalized = profile.get("normalized_major") or {}
    parts = [
        profile.get("major", ""),
        profile.get("major_group", ""),
        profile.get("major_preference", ""),
        normalized.get("canonical_major_name", ""),
        normalized.get("major_group", ""),
    ]
    parts.extend(as_list(normalized.get("related_groups")))
    parts.extend(as_list(normalized.get("aliases")))
    parts.extend(as_list(normalized.get("industry_keywords")))
    parts.extend(as_list(profile.get("interests", [])))
    return " ".join(str(part) for part in parts if part)


def _is_business_general_profile(profile):
    groups = _profile_groups(profile)
    if groups & BUSINESS_GENERAL_GROUPS:
        return True
    text = _profile_text(profile)
    return any(term in text for term in ("工商管理", "市场营销", "电子商务", "商科", "管理类", "商务", "运营", "市场"))


def _job_scope(job):
    scope = job.get("industry_scope") or "general"
    if scope:
        return scope
    text = " ".join(_job_field_values(job, ["job_name", "description", "search_keywords", "resume_keywords", "industry_tags"])).lower()
    if _contains_any(text, ORAL_DOMAIN_TERMS):
        return "dental"
    if _contains_any(text, VETERINARY_DOMAIN_TERMS):
        return "animal_medicine"
    if _contains_any(text, HUMAN_MEDICAL_DOMAIN_TERMS):
        return "medical"
    return "general"


def _is_industry_specific_job(job):
    scope = _job_scope(job)
    return bool(job.get("is_industry_specific")) or scope in PROBLEM_INDUSTRY_SCOPES


def _industry_major_match(profile, job):
    scope = _job_scope(job)
    candidate_groups = _profile_groups(profile)
    required_groups = _as_set(job.get("required_major_groups", []))
    scope_groups = INDUSTRY_SCOPE_MAJOR_GROUPS.get(scope, set())
    return bool(candidate_groups & (required_groups | scope_groups))


def _industry_interest_match(profile, scope):
    terms = INDUSTRY_SCOPE_INTEREST_TERMS.get(scope, set())
    if not terms:
        return False
    text = " ".join(str(item) for item in as_list(profile.get("interests", [])) + as_list(profile.get("interest_tags", [])))
    return _contains_any(text, terms)


def _industry_adjustment(profile, job):
    scope = _job_scope(job)
    role_family = job.get("role_family", "")
    notes = []
    force_explore = False

    if not _is_industry_specific_job(job):
        if scope == "general" and _is_business_general_profile(profile) and role_family in GENERAL_ROLE_FAMILIES:
            notes.append("你的专业更适合优先从通用产品、市场、运营、商务、项目或数据岗位切入。")
            return 8, notes, False
        return 0, notes, False

    label = INDUSTRY_SCOPE_LABELS.get(scope, "特定行业")
    major_match = _industry_major_match(profile, job)
    interest_match = _industry_interest_match(profile, scope)

    if major_match:
        notes.append(f"该岗位属于{label}方向，当前专业与该行业背景匹配，因此可正常参与推荐。")
        return 0, notes, False

    force_explore = True
    if interest_match:
        adjustment = -10
        notes.append(f"该岗位属于{label}行业限定方向，当前专业与行业本身不是强相关，但你选择了相关兴趣，可作为行业探索。")
    else:
        adjustment = -24
        notes.append(f"该岗位属于{label}行业限定方向，当前专业和兴趣均未明显匹配，默认不优先推荐。")

    if _is_business_general_profile(profile) and scope in PROBLEM_INDUSTRY_SCOPES:
        adjustment -= 8
        notes.append("对商科/管理类专业，系统会优先推荐通用产品、市场、运营、商务、项目和数据岗位。")

    return adjustment, notes, force_explore


def _industry_first_reason(profile, job):
    if not _is_industry_specific_job(job):
        return ""
    scope = _job_scope(job)
    if _industry_major_match(profile, job):
        return ""
    label = INDUSTRY_SCOPE_LABELS.get(scope, "特定行业")
    if _industry_interest_match(profile, scope):
        return f"该岗位属于{label}行业限定方向，当前专业与行业本身不是强相关，但可作为产品/市场/运营方向的行业探索。"
    return f"该岗位属于{label}行业限定方向，当前专业并非强相关，默认不作为优先推荐。"


def score_job(profile, job, options_config, rules_config):
    profile = dict(profile)
    profile["_options_config"] = options_config
    profile["normalized_major"] = profile.get("normalized_major") or normalize_major(profile.get("major", ""), options_config)
    weights = rules_config["weights"]
    interests = profile.get("interests", [])
    skills = profile.get("skills", [])

    major_component = _major_score(profile, job, options_config, rules_config)
    access = _professional_access(profile, job)
    major_component = min(major_component, access["score_cap"])
    interest_component = _overlap_score(interests, job.get("interest_tags", job.get("interests", [])))
    skill_component = _overlap_score(skills, job.get("required_skills", []))
    education_component, education_notes, education_downgrade = _education_fit(profile, job, rules_config)
    stage_component = _stage_score(profile.get("current_stage") or profile.get("grade", ""), job, rules_config)
    growth_component = _growth_score(job)

    raw = (
        major_component * weights["major_relevance"]
        + interest_component * weights["interest_match"]
        + skill_component * weights["skill_match"]
        + education_component * weights["education_fit"]
        + stage_component * weights["stage_fit"]
        + growth_component * weights["growth_value"]
    ) * 100

    hits = _downgrade_hits(profile, job, rules_config)
    penalty = len(hits) * rules_config.get("avoid_tag_penalty", 12)
    adjustment, special_notes = _special_adjustment(profile, job, options_config, rules_config)
    conditional_adjustment, conditional_notes = _conditional_adjustment(profile, job, options_config, rules_config)
    industry_adjustment, industry_notes, industry_force_explore = _industry_adjustment(profile, job)
    adjustment += industry_adjustment
    if access["downgrade"]:
        adjustment -= 18 if access["strict_blocked"] else 8
    special_notes.extend(industry_notes)
    special_notes.extend(access["notes"])
    special_notes.extend(education_notes)
    special_notes.extend(conditional_notes)
    score = max(0, min(100, round(raw - penalty + adjustment + conditional_adjustment)))
    floor_score, floor_notes = _professional_relevance_floor(profile, job)
    if (
        floor_score
        and not hits
        and not education_downgrade
        and not access["strict_blocked"]
        and not access["downgrade"]
    ):
        score = max(score, floor_score)
        special_notes.extend(floor_notes)

    level = level_for_score(score, rules_config)
    if industry_force_explore and level == "优先推荐":
        level = "可探索"
    if hits and level == "优先推荐":
        level = "可探索"
    if education_downgrade and level == "优先推荐":
        level = "可探索"
    elif education_downgrade and level == "可探索":
        level = "暂不推荐"
    if access["strict_blocked"]:
        level = "暂不推荐"
    elif access["downgrade"] and level == "优先推荐":
        level = "可探索"
    if len(hits) >= 2:
        level = "暂不推荐"
    if (
        _is_strong_barrier_profile(profile)
        and profile.get("major_preference") != "跨专业探索"
        and level == "暂不推荐"
        and not hits
        and not education_downgrade
        and not access["strict_blocked"]
        and not access["downgrade"]
    ):
        level = "可探索"

    matched_skills = sorted(_as_set(skills) & _as_set(job.get("required_skills", [])))
    missing_skills = sorted(_as_set(job.get("required_skills", [])) - _as_set(skills))
    matched_interests = sorted(_as_set(interests) & _as_set(job.get("interest_tags", job.get("interests", []))))

    reasons = build_reason(
        profile=profile,
        job=job,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        matched_interests=matched_interests,
        avoid_hits=hits,
        special_notes=special_notes,
        level=level,
    )

    return {
        "job": job,
        "score": score,
        "level": level,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "matched_interests": matched_interests,
        "avoid_hits": hits,
        "reasons": reasons,
    }


def level_for_score(score, rules_config):
    thresholds = rules_config["thresholds"]
    if score >= thresholds["priority"]:
        return "优先推荐"
    if score >= thresholds["explore"]:
        return "可探索"
    return "暂不推荐"


def build_reason(profile, job, matched_skills, missing_skills, matched_interests, avoid_hits, special_notes, level):
    major = profile.get("major", "当前专业")
    suitable = "、".join(job.get("suitable_majors", []))
    normalized = profile.get("normalized_major") or {}
    related_groups = _as_set(as_list(normalized.get("related_groups")) + [normalized.get("major_group", "")])
    job_groups = _as_set(job.get("suitable_major_groups", []))
    required_groups = _as_set(job.get("required_major_groups", []))
    excluded_groups = _as_set(job.get("excluded_major_groups", []))
    relevance = job.get("major_relevance", "低专业限制")
    access_limited = bool(excluded_groups & related_groups) or (
        bool(job.get("strict_major_required")) and bool(required_groups) and not bool(required_groups & related_groups)
    )
    industry_reason = _industry_first_reason(profile, job)
    if industry_reason:
        first_reason = industry_reason
    elif access_limited:
        first_reason = job.get("professional_access_note") or f"{job['job_name']}通常有明确专业准入限制，当前专业不优先推荐。"
    elif related_groups & job_groups and relevance in ("强专业对口", "弱专业相关"):
        first_reason = f"你的专业属于{normalized.get('major_group', '相关专业类')}，与{job['job_name']}具有较强专业相关性。"
    elif normalized.get("canonical_major_name") and normalized.get("canonical_major_name") in job.get("suitable_majors", []):
        first_reason = f"该岗位与你的专业方向高度相关，可作为专业对口方向考虑。"
    else:
        if (
            _is_strong_barrier_profile(profile)
            and profile.get("major_preference") != "跨专业探索"
            and relevance in ("低专业限制", "跨专业可选")
        ):
            first_reason = f"{job['job_name']}属于{relevance}方向，可作为补充探索，但专业相关度低于当前专业强相关岗位。"
        else:
            first_reason = f"{job['job_name']}与{major}的相关度为“{relevance}”，适配范围包括：{suitable}。"
    reasons = [
        first_reason,
    ]
    if matched_interests:
        reasons.append(f"兴趣匹配点：{ '、'.join(matched_interests) }。")
    else:
        reasons.append("兴趣匹配点较少，建议先通过项目或课程了解真实工作内容。")
    if matched_skills:
        reasons.append(f"当前能力可直接用上：{ '、'.join(matched_skills) }。")
    else:
        reasons.append("当前已选能力与岗位要求重合较少，需要先补基础能力。")
    if missing_skills:
        reasons.append(f"需要补充：{ '、'.join(missing_skills[:6]) }。")
    if avoid_hits:
        reasons.append(f"命中排斥项：{ '、'.join(avoid_hits) }，因此推荐层级会被压低。")
    if special_notes:
        reasons.extend(note for note in special_notes if note != first_reason)
    if job.get("display_name") and job.get("posting_aliases"):
        aliases = "、".join(job.get("posting_aliases", [])[:6])
        tracks = "、".join(job.get("parent_track", [])) or "相关"
        reasons.append(f"{job['job_name']}更像是{tracks}岗位中的细分能力方向，真实招聘中可能以{aliases}等名称出现。")
    reasons.append(f"综合专业、兴趣、能力、学历、当前阶段和成长价值后，被归入“{level}”。")
    return reasons


def calculate_recommendations(profile, jobs, options_config, rules_config):
    scored = [score_job(profile, job, options_config, rules_config) for job in jobs]
    if _is_strong_barrier_profile(profile) and profile.get("major_preference") != "跨专业探索":
        scored.sort(
            key=lambda item: (
                0 if item["avoid_hits"] or item["level"] == "暂不推荐" else _professional_relevance_tier(profile, item["job"]),
                item["score"],
            ),
            reverse=True,
        )
    else:
        scored.sort(key=lambda item: item["score"], reverse=True)

    grouped = defaultdict(list)
    for item in scored:
        grouped[item["level"]].append(item)

    return {
        "优先推荐": grouped.get("优先推荐", []),
        "可探索": grouped.get("可探索", []),
        "暂不推荐": grouped.get("暂不推荐", []),
        "all": scored,
    }


ORAL_DOMAIN_TERMS = {
    "口腔",
    "口腔医学",
    "口腔医学技术",
    "牙科",
    "齿科",
    "牙医",
    "口腔医院",
    "口腔门诊",
    "正畸",
    "种植",
    "洁牙",
    "牙周",
    "四手操作",
    "器械消毒",
    "口腔护理",
    "口腔咨询",
}

VETERINARY_DOMAIN_TERMS = {
    "兽医",
    "宠物",
    "动物",
    "畜牧",
    "养殖",
    "宠物医院",
    "动物医院",
    "宠物诊疗",
    "动物护理",
    "宠物护理",
    "动保",
}

HUMAN_MEDICAL_DOMAIN_TERMS = {
    "临床医学",
    "护理",
    "医学检验",
    "医学影像",
    "药学",
    "医院",
    "门诊",
    "诊所",
    "病房",
    "护理部",
    "检验科",
}

BROAD_SEARCH_TERMS = {"医院", "实习", "助理", "见习", "门诊", "诊所"}


def _contains_any(text, terms):
    return any(term and term in text for term in terms)


def _search_profile_text(profile):
    if not profile:
        return ""
    normalized = profile.get("normalized_major") or {}
    parts = [
        profile.get("major", ""),
        profile.get("major_group", ""),
        profile.get("major_preference", ""),
        normalized.get("canonical_major_name", ""),
        normalized.get("major_group", ""),
    ]
    parts.extend(as_list(normalized.get("related_groups")))
    parts.extend(as_list(normalized.get("aliases")))
    parts.extend(as_list(normalized.get("industry_keywords")))
    return " ".join(str(part) for part in parts if part).lower()


def _profile_domain(profile):
    text = _search_profile_text(profile)
    if not text:
        return ""
    if _contains_any(text, ORAL_DOMAIN_TERMS):
        return "oral"
    if _contains_any(text, VETERINARY_DOMAIN_TERMS):
        return "veterinary"
    if _contains_any(text, HUMAN_MEDICAL_DOMAIN_TERMS):
        return "human_medical"
    return ""


def _job_field_values(job, fields):
    values = []
    for field in fields:
        value = job.get(field, "")
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        else:
            values.append(str(value))
    return values


def _job_text(job, fields):
    return " ".join(_job_field_values(job, fields)).lower()


def _query_terms_for_domain(query, domain):
    terms = [query]
    if domain == "oral" and query in BROAD_SEARCH_TERMS:
        terms.extend(ORAL_DOMAIN_TERMS)
    elif domain == "veterinary" and query in BROAD_SEARCH_TERMS:
        terms.extend(VETERINARY_DOMAIN_TERMS)
    return [term.lower() for term in terms if term]


def _domain_match_score(domain, job, text):
    if not domain:
        return 0
    suitable_text = " ".join(
        _job_field_values(job, ["suitable_majors", "suitable_major_groups", "required_major_groups", "industry_tags", "search_keywords"])
    ).lower()
    if domain == "oral":
        score = 0
        if _contains_any(text, ORAL_DOMAIN_TERMS):
            score += 34
        if _contains_any(suitable_text, ORAL_DOMAIN_TERMS):
            score += 34
        return score
    if domain == "veterinary":
        score = 0
        if _contains_any(text, VETERINARY_DOMAIN_TERMS):
            score += 34
        if _contains_any(suitable_text, VETERINARY_DOMAIN_TERMS):
            score += 34
        return score
    if domain == "human_medical":
        return 24 if _contains_any(text, HUMAN_MEDICAL_DOMAIN_TERMS) else 0
    return 0


def _profile_blocked_by_job_major_rules(profile, job):
    normalized = profile.get("normalized_major") or {}
    candidate_groups = _as_set(
        as_list(normalized.get("related_groups"))
        + [profile.get("major_group", ""), normalized.get("major_group", "")]
    )
    required_groups = _as_set(job.get("required_major_groups", []))
    excluded_groups = _as_set(job.get("excluded_major_groups", []))
    if excluded_groups & candidate_groups:
        return True
    if job.get("strict_major_required") and required_groups and not (required_groups & candidate_groups):
        return True
    return False


def _keyword_match_score(query_terms, job):
    score = 0
    weighted_fields = [
        (["job_name", "display_name", "posting_aliases", "aliases"], 30),
        (["search_keywords", "resume_keywords", "industry_tags", "scene_tags"], 18),
        (["required_skills", "plus_skills", "soft_skills"], 12),
        (["description", "daily_tasks", "category", "category_lv1", "category_lv2"], 8),
    ]
    for fields, weight in weighted_fields:
        text = " ".join(_job_field_values(job, fields)).lower()
        if _contains_any(text, query_terms):
            score += weight
    return score


def _search_result_score(query, query_terms, domain, job, fields, profile):
    if profile and _profile_blocked_by_job_major_rules(profile, job):
        return None

    text = _job_text(job, fields)
    keyword_score = _keyword_match_score(query_terms, job)
    domain_score = _domain_match_score(domain, job, text)
    conflict_penalty = 0

    if domain in {"oral", "human_medical"} and _contains_any(text, VETERINARY_DOMAIN_TERMS):
        conflict_penalty = 120
    if domain == "oral" and query in BROAD_SEARCH_TERMS and not _contains_any(text, ORAL_DOMAIN_TERMS):
        return None
    if domain == "human_medical" and query in BROAD_SEARCH_TERMS and conflict_penalty:
        return None
    if keyword_score <= 0 and domain_score <= 0:
        return None

    return keyword_score + domain_score - conflict_penalty


def search_jobs(query, jobs, fields=None, profile=None):
    if not query.strip():
        return jobs
    fields = fields or [
        "job_name",
        "display_name",
        "category",
        "category_lv1",
        "category_lv2",
        "aliases",
        "industry_tags",
        "suitable_major_groups",
        "suitable_majors",
        "required_skills",
        "plus_skills",
        "soft_skills",
        "interest_tags",
        "scene_tags",
        "resume_keywords",
        "description",
        "daily_tasks",
        "search_keywords",
        "parent_track",
        "posting_aliases",
    ]
    query_lower = query.strip().lower()
    domain = _profile_domain(profile)
    query_terms = _query_terms_for_domain(query_lower, domain)
    results = []
    for job in jobs:
        if profile:
            score = _search_result_score(query_lower, query_terms, domain, job, fields, profile)
            if score is not None and score > 0:
                results.append((score, job))
            continue
        if query_lower in _job_text(job, fields):
            results.append((1, job))
    results.sort(key=lambda item: item[0], reverse=True)
    return [job for _score, job in results]


def group_jobs_by_category(jobs):
    grouped = defaultdict(list)
    for job in jobs:
        grouped[job.get("category_lv1") or job.get("category", "其他")].append(job)
    return dict(sorted(grouped.items()))

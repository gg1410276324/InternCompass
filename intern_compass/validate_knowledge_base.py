from collections import Counter

from data_loader import DataLoadError, load_json
from knowledge_base import conditional_group_for_major, normalize_jobs, normalize_major, search_majors
from rules import calculate_recommendations, search_jobs


REQUIRED_JOB_FIELDS = [
    "job_id",
    "job_name",
    "aliases",
    "category_lv1",
    "category_lv2",
    "industry_tags",
    "major_relevance",
    "suitable_major_groups",
    "suitable_majors",
    "open_to_non_related_major",
    "required_skills",
    "plus_skills",
    "soft_skills",
    "interest_tags",
    "scene_tags",
    "avoid_tags",
    "difficulty",
    "growth_value",
    "entry_level",
    "education_requirement",
    "description",
    "daily_tasks",
    "preparation_advice",
    "resume_keywords",
    "not_suitable_for",
    "search_keywords",
]

REQUIRED_MAJOR_FIELDS = [
    "major_id",
    "major_name",
    "aliases",
    "keywords",
    "major_group",
    "barrier_level",
    "strong_related_job_ids",
    "weak_related_job_ids",
    "cross_major_job_ids",
    "conditional_question_group",
    "search_keywords",
]


def _load_or_error(filename, errors):
    try:
        return load_json(filename)
    except DataLoadError as exc:
        errors.append(str(exc))
        return None


def _duplicates(values):
    return [value for value, count in Counter(values).items() if value and count > 1]


def validate():
    errors = []
    warnings = []

    raw_jobs = _load_or_error("job_data.json", errors) or []
    majors = _load_or_error("majors.json", errors) or []
    options = _load_or_error("options_config.json", errors) or {}
    rules = _load_or_error("rules_config.json", errors) or {}
    conditional = _load_or_error("conditional_questions.json", errors) or {"question_groups": {}}
    major_normalization = _load_or_error("major_normalization.json", errors) or {"canonical_majors": []}
    options["majors"] = majors
    options["conditional_questions"] = conditional
    options["major_normalization"] = major_normalization

    jobs = normalize_jobs(raw_jobs)
    job_ids = {job.get("job_id") for job in jobs if job.get("job_id")}
    job_names = {job.get("job_name") for job in jobs if job.get("job_name")}
    all_tags = set()
    for job in jobs:
        all_tags.update(job.get("avoid_tags", []))
        all_tags.update(job.get("interest_tags", []))
        all_tags.update(job.get("scene_tags", []))

    for index, job in enumerate(jobs, start=1):
        missing = [field for field in REQUIRED_JOB_FIELDS if field not in job or job.get(field) in (None, "")]
        if missing:
            errors.append(f"岗位第 {index} 条 {job.get('job_name', '<未命名>')} 缺少字段：{', '.join(missing)}")
        for field in [
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
        ]:
            if not isinstance(job.get(field), list):
                errors.append(f"岗位 {job.get('job_name', '<未命名>')} 的 {field} 不是数组")
        requirement = job.get("education_requirement", {})
        if not isinstance(requirement, dict):
            errors.append(f"岗位 {job.get('job_name', '<未命名>')} 的 education_requirement 不是对象")
        else:
            for key in ["min_education", "preferred_education", "strict"]:
                if key not in requirement:
                    errors.append(f"岗位 {job.get('job_name', '<未命名>')} 的 education_requirement 缺少 {key}")
            if "preferred_education" in requirement and not isinstance(requirement.get("preferred_education"), list):
                errors.append(f"岗位 {job.get('job_name', '<未命名>')} 的 preferred_education 不是数组")

    for duplicated in _duplicates([job.get("job_id") for job in jobs]):
        errors.append(f"job_id 重复：{duplicated}")
    for duplicated in _duplicates([job.get("job_name") for job in jobs]):
        errors.append(f"岗位名称重复：{duplicated}")

    major_ids = {major.get("major_id") for major in majors if major.get("major_id")}
    for index, major in enumerate(majors, start=1):
        missing = [field for field in REQUIRED_MAJOR_FIELDS if field not in major]
        if missing:
            errors.append(f"专业第 {index} 条 {major.get('major_name', '<未命名>')} 缺少字段：{', '.join(missing)}")
        for field in ["strong_related_job_ids", "weak_related_job_ids", "cross_major_job_ids"]:
            for job_id in major.get(field, []):
                if job_id not in job_ids:
                    errors.append(f"专业 {major.get('major_name')} 引用了不存在的 job_id：{job_id}")

    for duplicated in _duplicates([major.get("major_id") for major in majors]):
        errors.append(f"major_id 重复：{duplicated}")

    if not options.get("education_levels"):
        errors.append("options_config.json 缺少 education_levels")
    if not options.get("stage_options"):
        errors.append("options_config.json 缺少 stage_options")
    if "都接受 / 都可以" not in options.get("frontline_acceptance_options", []):
        errors.append("frontline_acceptance_options 缺少“都接受 / 都可以”")
    for level in options.get("education_levels", []):
        if level not in options.get("stage_options", {}):
            errors.append(f"stage_options 缺少学历层次：{level}")

    question_groups = conditional.get("question_groups", {})
    for major in majors:
        group_id = major.get("conditional_question_group")
        if group_id and group_id not in question_groups:
            errors.append(f"专业 {major.get('major_name')} 引用了不存在的动态问题组：{group_id}")

    for group_id, group in question_groups.items():
        for question in group.get("questions", []):
            for answer, effects in question.get("effects", {}).items():
                for job_id in effects.get("boost_job_ids", []) + effects.get("penalty_job_ids", []):
                    if job_id not in job_ids:
                        errors.append(f"动态问题组 {group_id} 的答案 {answer} 引用了不存在的 job_id：{job_id}")

    special_rules = rules.get("special_major_rules", {})
    for group_name, preference_rules in special_rules.items():
        for preference, references in preference_rules.items():
            if not isinstance(references, list):
                continue
            for reference in references:
                if reference not in job_names:
                    warnings.append(f"推荐规则 {group_name}/{preference} 引用了未找到的岗位名称：{reference}")

    for tag in rules.get("forced_downgrade_tags", []):
        if tag not in all_tags and tag not in options.get("avoid_task_options", []):
            warnings.append(f"强降级标签未在岗位或选项中出现：{tag}")

    major_search_samples = {
        "动物": ["动物医学", "动物科学", "畜牧兽医", "水产养殖学"],
        "口腔": ["口腔医学", "口腔医学技术"],
        "计算机": ["计算机科学与技术", "软件工程", "人工智能", "数据科学与大数据技术", "网络工程", "信息安全"],
        "市场": ["市场营销", "工商管理", "电子商务"],
        "新闻": ["新闻学", "传播学", "网络与新媒体", "广告学"],
    }
    for query, expected_names in major_search_samples.items():
        found_list = [major["major_name"] for major in search_majors(query, majors, limit=12)]
        found = set(found_list)
        missing = [name for name in expected_names if name not in found]
        if missing:
            errors.append(f"专业搜索 “{query}” 缺少结果：{', '.join(missing)}")
        ordered_found = [name for name in found_list if name in expected_names]
        if ordered_found[: len(expected_names)] != expected_names:
            errors.append(f"专业搜索 “{query}” 排序不符合预期：{ordered_found[:len(expected_names)]}")

    alias_search_samples = {
        "兽医": ["动物医学", "畜牧兽医"],
        "动医": ["动物医学"],
        "畜牧": ["畜牧兽医"],
    }
    for query, expected_names in alias_search_samples.items():
        found = {major["major_name"] for major in search_majors(query, majors, limit=8)}
        missing = [name for name in expected_names if name not in found]
        if missing:
            errors.append(f"专业别名搜索 “{query}” 缺少结果：{', '.join(missing)}")

    normalized = normalize_major("畜牧兽医", options, majors)
    if normalized.get("canonical_major_id") != "animal_medicine":
        errors.append("畜牧兽医 未归一化到 animal_medicine")
    if "动物医学" not in normalized.get("canonical_major_name", ""):
        errors.append("畜牧兽医 canonical_major_name 不正确")
    if conditional_group_for_major("畜牧兽医", options, majors) != "animal_medical":
        errors.append("畜牧兽医 未触发动物医学类动态问题")

    animal_related_jobs = {
        "兽医助理",
        "宠物医院实习",
        "养殖场技术实习",
        "动物检验检测实习",
        "兽药企业技术支持",
        "宠物营养助理",
        "动保行业市场实习生",
        "宠物品牌内容运营",
        "宠物医疗产品助理",
        "宠物平台用户运营",
    }
    profile = {
        "education_level": "本科",
        "current_stage": "大三",
        "grade": "大三",
        "major": "畜牧兽医",
        "normalized_major": normalized,
        "major_group": normalized.get("major_group"),
        "major_preference": "强专业对口",
        "frontline_acceptance": "接受企业技术支持",
        "conditional_answers": {},
        "interests": ["和人沟通", "临床 / 实操", "写内容 / 做账号"],
        "skills": ["专业知识", "沟通表达", "PPT"],
        "avoid_tasks": [],
    }
    recommendations = calculate_recommendations(profile, jobs, options, rules)
    by_name = {item["job"]["job_name"]: item for item in recommendations.get("all", [])}
    for job_name in animal_related_jobs:
        item = by_name.get(job_name)
        if not item:
            errors.append(f"动物医学类测试缺少岗位：{job_name}")
            continue
        reason_text = " ".join(item.get("reasons", []))
        if "跨专业" in reason_text:
            errors.append(f"畜牧兽医 推荐理由误判跨专业：{job_name}")

    def recommendation_map(major_name):
        normalized_major = normalize_major(major_name, options, majors)
        test_profile = {
            "education_level": "本科",
            "current_stage": "大三",
            "grade": "大三",
            "major": major_name,
            "normalized_major": normalized_major,
            "major_group": normalized_major.get("major_group"),
            "major_preference": "强专业对口",
            "frontline_acceptance": "接受临床 / 一线实操",
            "conditional_answers": {},
            "interests": ["临床 / 实操", "写内容 / 做账号", "和人沟通"],
            "skills": ["专业知识", "沟通表达", "Excel", "写作", "PPT"],
            "avoid_tasks": [],
        }
        result = calculate_recommendations(test_profile, jobs, options, rules)
        return result, {item["job"]["job_name"]: item for item in result.get("all", [])}

    pharmacy_normalized = normalize_major("药学", options, majors)
    if pharmacy_normalized.get("major_group") != "药学类":
        errors.append("药学 未归一化到 药学类")

    pharmacy_result, pharmacy_jobs = recommendation_map("药学")
    hospital_item = pharmacy_jobs.get("医院见习")
    if hospital_item and hospital_item.get("level") == "优先推荐":
        errors.append("药学 不应优先推荐 医院见习")
    if hospital_item and hospital_item.get("level") != "暂不推荐":
        errors.append("药学 的 医院见习 应被降到暂不推荐")
    pharmacy_priority = [item["job"]["job_name"] for item in pharmacy_result.get("优先推荐", [])[:12]]
    pharmacy_targets = {"药品注册助理", "质量管理实习生", "医药市场实习", "医学内容运营", "医疗产品助理", "临床研究助理"}
    if not (set(pharmacy_priority) & pharmacy_targets):
        errors.append("药学 未优先推荐药企/注册/质量/医药市场/医学内容相关方向")

    weak_profile = {
        "education_level": "本科",
        "current_stage": "大三",
        "grade": "大三",
        "major": "药学",
        "normalized_major": pharmacy_normalized,
        "major_group": pharmacy_normalized.get("major_group"),
        "major_preference": "弱专业相关",
        "frontline_acceptance": "都接受 / 都可以",
        "conditional_answers": {},
        "interests": ["和人沟通", "写内容 / 做账号", "市场品牌 / 商务销售", "产品 / 项目"],
        "skills": ["专业知识", "沟通表达", "Excel", "写作", "PPT"],
        "avoid_tasks": [],
    }
    weak_result = calculate_recommendations(weak_profile, jobs, options, rules)
    weak_jobs = {item["job"]["job_name"]: item for item in weak_result.get("all", [])}
    oral_market_score = weak_jobs.get("口腔器械市场助理", {}).get("score", 0)
    for job_name in ["药品注册助理", "质量管理实习生", "品控实习生", "研发助理", "实验室助理", "医药市场实习"]:
        if weak_jobs.get(job_name, {}).get("score", 0) <= oral_market_score:
            errors.append(f"药学+弱专业相关时 {job_name} 分数不应低于口腔器械市场助理")
    if weak_jobs.get("药品注册助理", {}).get("level") != "优先推荐":
        errors.append("药学+弱专业相关时 药品注册助理 应保持较高优先级")

    clinical_result, clinical_jobs = recommendation_map("临床医学")
    if clinical_jobs.get("医院见习", {}).get("level") == "暂不推荐":
        errors.append("临床医学 应允许推荐 医院见习")

    _nursing_result, nursing_jobs = recommendation_map("护理学")
    if nursing_jobs.get("医院见习", {}).get("level") == "优先推荐":
        errors.append("护理学 不应优先推荐医生临床见习")

    _oral_result, oral_jobs = recommendation_map("口腔医学")
    if oral_jobs.get("口腔门诊助理", {}).get("level") == "暂不推荐":
        errors.append("口腔医学 应允许推荐 口腔门诊助理")

    animal_uncertain = normalize_major("动物医学", options, majors)
    uncertain_profile = {
        "education_level": "本科",
        "current_stage": "大三",
        "grade": "大三",
        "major": "动物医学",
        "normalized_major": animal_uncertain,
        "major_group": animal_uncertain.get("major_group"),
        "major_preference": "不确定，想都看看",
        "frontline_acceptance": "都接受 / 都可以",
        "conditional_answers": {},
        "interests": ["和人沟通", "临床 / 实操", "写内容 / 做账号"],
        "skills": ["专业知识", "沟通表达", "PPT", "Excel"],
        "avoid_tasks": [],
    }
    uncertain_result = calculate_recommendations(uncertain_profile, jobs, options, rules)
    uncertain_jobs = {item["job"]["job_name"]: item for item in uncertain_result.get("all", [])}
    if uncertain_jobs.get("兽医助理", {}).get("level") == "暂不推荐":
        errors.append("动物医学+不确定 不应把强专业岗位直接列为暂不推荐")
    if uncertain_jobs.get("用户研究助理", {}).get("level") == "暂不推荐":
        errors.append("不确定时无排斥项的跨专业可选岗位应至少进入可探索")
    if uncertain_jobs.get("动保行业市场实习生", {}).get("score", 0) <= uncertain_jobs.get("市场实习生", {}).get("score", 0):
        errors.append("动物医学+不确定 应让专业弱相关岗位排在通用低限制岗位前")
    user_research_job = uncertain_jobs.get("用户研究助理", {}).get("job", {})
    if user_research_job.get("display_name") != "市场/产品-用户研究助理":
        errors.append("用户研究助理 缺少正确 display_name")
    if "市场实习生" not in user_research_job.get("posting_aliases", []):
        errors.append("用户研究助理 缺少真实招聘名称映射")

    def uncertain_map(major_name, avoid_tasks=None, major_preference="不确定，想都看看"):
        normalized_major = normalize_major(major_name, options, majors)
        test_profile = {
            "education_level": "本科",
            "current_stage": "大三",
            "grade": "大三",
            "major": major_name,
            "normalized_major": normalized_major,
            "major_group": normalized_major.get("major_group"),
            "major_preference": major_preference,
            "frontline_acceptance": "都接受 / 都可以",
            "conditional_answers": {},
            "interests": options.get("interest_options", []),
            "skills": options.get("skill_options", []),
            "avoid_tasks": avoid_tasks or [],
        }
        result = calculate_recommendations(test_profile, jobs, options, rules)
        return {item["job"]["job_name"]: item for item in result.get("all", [])}

    uncertain_cases = [
        ("临床医学", ["医院见习", "临床研究助理", "医学事务助理", "医疗器械临床支持"], ["市场实习生", "用户研究助理"]),
        ("口腔医学", ["口腔门诊助理", "口腔医院实习"], ["用户增长分析实习生", "市场分析助理"]),
        ("动物医学", ["兽医助理", "宠物医院实习", "动物检验检测实习"], ["市场实习生", "用户研究助理"]),
        ("药学", ["药品注册助理", "质量管理实习生", "医药市场实习"], ["口腔器械市场助理", "市场实习生"]),
        ("法学", ["法务实习"], ["市场实习生"]),
        ("会计学", ["财务实习", "会计助理", "审计实习", "税务实习生"], ["市场实习生"]),
        ("计算机科学与技术", ["前端开发实习", "后端开发实习", "数据开发实习", "算法实习"], ["用户运营"]),
        ("机械工程", ["机械工程实习", "设备工程助理", "质量工程助理"], ["市场实习生"]),
    ]
    for major_name, strong_jobs, generic_jobs in uncertain_cases:
        mapped = uncertain_map(major_name)
        for job_name in strong_jobs:
            item = mapped.get(job_name)
            if not item:
                errors.append(f"{major_name}+不确定 缺少强相关测试岗位：{job_name}")
                continue
            if item.get("level") != "优先推荐":
                errors.append(f"{major_name}+不确定 时 {job_name} 应进入优先推荐")
            for generic_name in generic_jobs:
                generic = mapped.get(generic_name)
                if generic and item.get("score", 0) <= generic.get("score", 0):
                    errors.append(f"{major_name}+不确定 时 {job_name} 应排在 {generic_name} 前")

    oral_avoid = uncertain_map("口腔医学", ["临床一线"])
    if oral_avoid.get("口腔门诊助理", {}).get("level") == "优先推荐":
        errors.append("明确排斥临床一线时 口腔门诊助理 不应保持优先推荐")
    clinical_avoid = uncertain_map("临床医学", ["临床一线"])
    if clinical_avoid.get("医院见习", {}).get("level") == "优先推荐":
        errors.append("明确排斥临床一线时 医院见习 不应保持优先推荐")
    weak_animal = uncertain_map("动物医学", major_preference="弱专业相关")
    if weak_animal.get("兽医助理", {}).get("score", 0) <= weak_animal.get("市场实习生", {}).get("score", 0):
        errors.append("能力全选且选择弱专业相关时 动物医学强相关岗位仍应高于通用市场岗位")

    try:
        search_jobs("产品", jobs)
        search_jobs("动物", jobs)
    except Exception as exc:
        errors.append(f"岗位搜索索引构建失败：{exc}")

    return errors, warnings


def main():
    errors, warnings = validate()
    if warnings:
        print("警告：")
        for warning in warnings:
            print(f"- {warning}")
    if errors:
        print("知识库校验未通过：")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("知识库校验通过。")


if __name__ == "__main__":
    main()

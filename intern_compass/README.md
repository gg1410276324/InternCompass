# Intern Compass 大学生实习岗位方向推荐工具

Intern Compass 是一个本地可运行的 Python 桌面程序 Demo，用来帮助大学生根据专业、学历层次、当前阶段、专业对口意愿、兴趣、能力和排斥项，判断更适合优先探索哪些实习岗位方向。

它不是招聘平台，不推荐具体公司，不推荐城市，不做投递系统，不爬取真实岗位，不接入 AI API，也不联网。

## 项目背景

很多大学生在找第一段实习时，不是缺少岗位列表，而是不知道自己应该先探索哪类方向。尤其是动物医学、临床医学、口腔医学、计算机、商科、传媒等专业，专业壁垒、跨专业可能性和个人排斥项会显著影响选择。

这个 Demo 通过本地岗位方向库和规则评分模型，把“我适合什么方向”拆成可解释的推荐结果，适合放入产品经理作品集展示。

## 解决的用户痛点

- 不清楚专业对口、弱相关、跨专业方向之间怎么取舍。
- 不知道岗位需要哪些技能，无法判断自己缺口在哪里。
- 容易被具体公司或城市信息干扰，忽略岗位方向本身。
- 缺少一份能导出的、结构化的实习方向探索报告。

## 核心功能

- 学生画像填写：学历层次、当前阶段、专业、专业对口意愿、一线场景接受度、兴趣、能力、排斥项。
- 岗位方向推荐：输出“优先推荐 / 可探索 / 暂不推荐”三类结果。
- 岗位详情展示：展示岗位内容、日常任务、所需技能、匹配点、缺口、准备建议、简历关键词等。
- 搜索岗位：支持按岗位名称、类别、适合专业、技能、兴趣、简历关键词、描述搜索。
- 岗位地图：按类别查看全部岗位方向。
- 导出报告：生成 `report.md`，包含画像、推荐结果、理由、技能和准备建议。

## 推荐逻辑说明

推荐分由以下因素组成：

- 专业相关度：30%
- 兴趣匹配度：25%
- 能力匹配度：25%
- 学历适配度：10%
- 当前阶段适配度：10%
- 成长价值：10%
- 排斥项扣分

分层规则：

- 80 分及以上：优先推荐
- 60-79 分：可探索
- 60 分以下：暂不推荐

如果命中强排斥项，例如临床一线、养殖场环境、纯代码、纯销售、长期无薪，推荐层级会被压低。

## 文件结构

```text
intern_compass/
  main.py                 主程序入口
  ui_components.py        CustomTkinter UI 组件
  rules.py                推荐评分、搜索和分组逻辑
  knowledge_base.py       岗位 / 专业兼容归一化和搜索工具
  data_manager.py         匿名内测数据追加保存
  report_generator.py     Markdown 推荐报告导出
  data_loader.py          JSON 配置读取
  job_data.json           岗位方向库
  majors.json             专业知识库和搜索关键词
  conditional_questions.json 专业补充问题配置
  options_config.json     问卷选项和专业映射
  rules_config.json       推荐权重、阈值和专业规则
  validate_knowledge_base.py 知识库校验脚本
  ui_config.py            UI 主题、文案和尺寸配置
  README.md               项目说明
```

## 安装方式

建议使用 Python 3.9 或以上版本。

```bash
pip install customtkinter
```

## 运行方式

在 `intern_compass` 目录下运行：

```bash
python main.py
```

如果没有安装 CustomTkinter，程序会弹窗提示安装命令。

## 如何修改 UI

打开 `ui_config.py`，可以集中修改：

- 窗口标题、宽高、最小尺寸
- 主题色、背景色、面板色、文字色
- 字体大小
- 卡片圆角和间距
- 按钮文案
- 推荐等级显示名称和颜色

## 如何修改岗位知识库

打开 `job_data.json`。每个岗位方向是一个 JSON 对象，字段保持统一：

- `job_id`
- `job_name`
- `category`
- `category_lv1`
- `category_lv2`
- `aliases`
- `industry_tags`
- `suitable_major_groups`
- `suitable_majors`
- `major_relevance`
- `open_to_non_related_major`
- `required_skills`
- `plus_skills`
- `soft_skills`
- `interest_tags`
- `scene_tags`
- `interests`
- `avoid_tags`
- `difficulty`
- `growth_value`
- `entry_level`
- `description`
- `daily_tasks`
- `resume_keywords`
- `preparation_advice`
- `not_suitable_for`
- `search_keywords`

修改后重新运行 `python main.py` 即可生效。

新增岗位时建议复制一个相近岗位对象，再修改：

1. `job_id` 使用英文 snake_case，并保持唯一。
2. `job_name` 不要和已有岗位重复。
3. 数组字段即使暂时没有内容，也保留空数组。
4. `search_keywords` 放岗位名称、别名、技能、行业词、常见搜索词。
5. 不要把岗位数据写进 Python 代码。

旧版字段 `category` 和 `interests` 仍然兼容，程序运行时会映射到 `category_lv1/category_lv2` 和 `interest_tags`。

## 如何新增专业

打开 `majors.json`，新增一个专业对象，字段包括：

- `major_id`
- `major_name`
- `aliases`
- `keywords`
- `major_group`
- `barrier_level`
- `strong_related_job_ids`
- `weak_related_job_ids`
- `cross_major_job_ids`
- `conditional_question_group`
- `search_keywords`
- `popularity_score`
- `display_order`

其中 `strong_related_job_ids`、`weak_related_job_ids`、`cross_major_job_ids` 必须引用 `job_data.json` 中真实存在的 `job_id`。新增专业后，也建议把专业名加入 `options_config.json` 的 `common_major_options` 和 `major_category_mapping`。

专业搜索排序会综合匹配类型、`popularity_score` 和 `display_order`：`popularity_score` 越大越靠前，`display_order` 越小越靠前。想手动调整“动物”“计算机”“市场”等关键词的展示顺序，优先改这两个字段。

## 如何添加专业搜索关键词

专业搜索不只看完全匹配，会同时搜索 `major_name`、`aliases`、`keywords`、`search_keywords` 和 `major_group`。

如果用户常用某个简称或别名，例如“口腔”“电商”“新媒体”“CS”，把它加入对应专业的 `aliases` 或 `search_keywords` 即可。

同一专业 / 同类专业的内部归一化规则写在 `major_normalization.json`。例如“畜牧兽医”“兽医”“动医”会归一化到 canonical 专业“动物医学”，用于推荐评分、专业组识别和动态问题触发；界面输入框仍保留用户原始选择。

## 如何修改动态专业问题

打开 `conditional_questions.json`。每个问题组包含：

- `major_groups`：哪些专业类别显示这组问题。
- `questions`：问题列表。
- `effects`：不同答案对岗位的加分、降级或排斥标签影响。

新增问题时，为每个问题设置唯一 `id`。如果要让答案影响推荐结果，可以在答案下配置 `boost_job_ids`、`penalty_job_ids` 或 `avoid_tags`。用户切换专业后，左侧补充问题会自动刷新；补充问题答案会进入推荐、导出报告和匿名内测数据。

## 如何修改问卷选项

打开 `options_config.json`，可修改：

- 学历层次 `education_levels`
- 当前阶段 `stage_options`
- 专业对口意愿选项
- 一线场景接受度选项
- 兴趣选项
- 能力选项
- 排斥项
- 常见专业选项
- 专业类别映射

## 如何修改推荐规则

打开 `rules_config.json`，可修改：

- `weights`：推荐分权重
- `thresholds`：推荐等级阈值
- `avoid_tag_penalty`：排斥项扣分
- `conditional_boost_score`：动态问题命中加分
- `conditional_penalty_score`：动态问题命中降级分
- `forced_downgrade_tags`：强降级标签
- `major_relevance_scores`：专业对口意愿与岗位相关度的适配分
- `education_levels_rank`：学历层次高低排序
- `stage_fit`：当前阶段与岗位难度适配
- `special_major_rules`：动物医学、医药、口腔、计算机等专业特殊规则

## 后期如何修改

1. 新增一个岗位：在 `job_data.json` 的数组末尾新增一个岗位对象，字段按现有岗位复制并修改。
2. 修改岗位所需技能：修改对应岗位的 `required_skills` 数组。
3. 新增一个专业：在 `options_config.json` 的 `common_major_options` 中加入专业名，并在 `major_category_mapping` 中归入合适类别。
4. 修改问卷选项：编辑 `options_config.json` 中对应选项数组。
5. 修改推荐分权重：编辑 `rules_config.json` 的 `weights`，总和建议保持为 1。
6. 修改推荐等级阈值：编辑 `rules_config.json` 的 `thresholds.priority` 和 `thresholds.explore`。
7. 修改 UI 颜色和字体：编辑 `ui_config.py` 的 `theme` 和 `font`。
8. 添加新的排斥项：先在 `options_config.json` 的 `avoid_task_options` 中新增，再在相关岗位的 `avoid_tags` 中加入同名标签。
9. 添加新的岗位类别：在 `job_data.json` 的岗位 `category` 中直接使用新类别，岗位地图会自动分组显示。
10. 扩展搜索字段：在 `rules.py` 的 `search_jobs` 默认 `fields` 中加入新的岗位字段名。

## 如何修改学历门槛

岗位学历要求写在 `job_data.json` 的 `education_requirement`：

```json
{
  "min_education": "本科",
  "preferred_education": ["本科", "硕士"],
  "strict": false
}
```

如果 `strict` 为 `true`，学历低于 `min_education` 时会明显降分并尽量降级；如果为 `false`，只作为可探索方向降分提示。学历和阶段评分规则在 `rules_config.json` 的 `education_levels_rank` 与 `stage_fit` 中维护。

## 如何运行知识库校验

在 `intern_compass` 目录下运行：

```bash
python validate_knowledge_base.py
```

校验内容包括 JSON 可读性、岗位和专业 ID 唯一性、必要字段、专业引用的岗位 ID、动态问题组、推荐规则引用和专业 / 岗位搜索是否能构建。

## 如何查看内测数据合集

每次生成推荐后，程序会把匿名记录追加到：

```text
intern_compass/data/user_runs.jsonl
```

记录包含学历层次、当前阶段、专业、专业类别、基础答案、补充问题答案、兴趣、能力、排斥项、推荐结果和分数，不保存姓名、手机号、学号、学校等个人身份信息。

如果后续接入反馈入口，可调用 `data_manager.append_feedback`，反馈会追加到：

```text
intern_compass/data/feedback_dataset.csv
```

## 作品集展示说明

这个项目展示的是产品经理对“岗位方向推荐”问题的拆解能力，以及用本地规则模型实现可解释推荐的能力。重点不是岗位数量，而是：

- 用户画像信息结构化
- 专业壁垒与跨专业探索的规则表达
- 推荐原因可解释
- 数据、规则、UI 分离，方便后期扩展
- 本地运行，不依赖网络和外部服务

## Windows 无黑窗口启动

正式给用户双击运行时，建议使用项目根目录的：

```text
启动 Intern Compass.vbs
```

这个入口会调用 `intern_compass/main.pyw`，不会显示后面的 cmd 黑色命令行窗口。

开发调试时仍然可以在 `intern_compass` 目录中运行：

```bash
python main.py
```

如果需要查看启动报错，无窗口入口会把异常写入：

```text
intern_compass/logs/app_error.log
```

如果要打包成 Windows exe，可以使用：

```bash
pyinstaller --onefile --windowed main.py
```

或：

```bash
pyinstaller --onefile --noconsole main.py
```

`--windowed` / `--noconsole` 可以避免启动时出现 cmd 黑窗口。打包后运行 `dist` 目录中的 exe 文件即可。图标可以后续再加。

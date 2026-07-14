# Intern Compass

一个给大学生做实习方向筛选的本地桌面小工具。

它不是招聘平台，也不抓取真实岗位。它做的事情更前置：让学生先把自己的专业、阶段、兴趣、已有能力和不想做的工作填清楚，再用一套本地规则把可尝试的实习方向排出来，并说明为什么推荐、缺什么能力、下一步可以怎么准备。

项目目前内置 128 个实习方向和 70 个专业条目。

## 主要功能

- 填写学生画像：学历、年级/阶段、专业、专业对口意愿、一线场景接受度、兴趣、技能和排斥项。
- 专业搜索与归一化：支持专业别名、关键词和专业大类识别，比如把相近叫法归到同一类专业上。
- 动态补充问题：不同专业会出现不同追问，用来细化推荐结果。
- 实习方向推荐：输出“优先推荐 / 可以探索 / 暂不推荐”三档结果。
- 岗位详情说明：展示工作内容、所需技能、匹配点、能力缺口、准备建议和简历关键词。
- 岗位搜索与岗位地图：可以按关键词查方向，也可以按类别浏览全部方向。
- 导出报告：生成 Markdown 和 docx 格式的推荐报告。
- 本地记录：生成推荐后，会追加一条匿名运行记录，方便后续复盘规则效果。

## 它不做什么

- 不联网，不调用 AI API。
- 不推荐具体公司、城市或投递链接。
- 不保存姓名、手机号、学号、学校等身份信息。
- 不承诺“最适合”的唯一答案，只提供一个可解释的探索顺序。

## 运行方式

环境建议：

- Python 3.9+
- Windows 桌面环境

安装依赖：

```bash
pip install customtkinter
```

开发调试：

```bash
cd intern_compass
python main.py
```

Windows 双击运行可以使用项目根目录里的：

```text
启动 Intern Compass.vbs
```

如果缺少依赖或配置文件读取失败，程序会弹窗提示。无窗口启动时的异常会写到：

```text
intern_compass/logs/app_error.log
```

## 项目结构

```text
intern_compass/
  main.py                  程序入口
  main.pyw                 无命令行窗口入口
  ui_components.py         桌面界面组件
  ui_config.py             界面文案、颜色、尺寸配置
  rules.py                 推荐评分、分层、搜索和分组逻辑
  rules_config.json        推荐权重、阈值和特殊规则
  knowledge_base.py        专业归一化、专业搜索、岗位数据整理
  job_data.json            实习方向库
  majors.json              专业知识库
  major_normalization.json 专业别名和归一化规则
  conditional_questions.json 动态补充问题
  options_config.json      问卷选项和专业映射
  report_generator.py      报告导出
  data_manager.py          匿名运行记录和反馈记录
  validate_knowledge_base.py 知识库校验脚本
```

## 推荐逻辑

推荐不是黑盒模型，主要看这些因素：

- 专业相关度
- 兴趣匹配度
- 能力匹配度
- 学历和当前阶段是否适合
- 岗位成长价值
- 用户明确排斥的工作内容
- 专业补充问题带来的加分、降分或排除标签

结果会被分成三档：

- 80 分及以上：优先推荐
- 60-79 分：可以探索
- 60 分以下：暂不推荐

遇到强排斥项，比如不接受临床一线、养殖场环境、纯销售、长期无薪等，相关方向会被降级。

## 修改数据

新增或调整实习方向，改：

```text
intern_compass/job_data.json
```

新增或调整专业，改：

```text
intern_compass/majors.json
intern_compass/major_normalization.json
intern_compass/options_config.json
```

调整推荐权重和阈值，改：

```text
intern_compass/rules_config.json
```

调整界面文案、颜色和控件尺寸，改：

```text
intern_compass/ui_config.py
```

## 校验知识库

改完岗位或专业数据后，建议跑一次：

```bash
cd intern_compass
python validate_knowledge_base.py
```

校验会检查 JSON 格式、ID 是否重复、必填字段、专业引用的岗位 ID、动态问题配置和搜索索引是否能正常构建。

## 导出和本地数据

推荐报告默认导出到：

```text
intern_compass/exports/
```

匿名运行记录默认写入：

```text
intern_compass/data/user_runs.jsonl
```

这些记录用于改进规则，不包含姓名、手机号、学号、学校等身份信息。

## 项目定位

这个项目更像一个“实习方向判断器”，不是求职自动化工具。它展示的重点是：怎样把模糊的求职问题拆成用户画像、岗位知识库、规则评分、解释理由和可导出的报告。



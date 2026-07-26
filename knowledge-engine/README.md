# Atlas · 知识与科学发现工作台

Atlas 是一个零第三方运行依赖、本地优先的知识探索系统。它将概念、方向明确的关系、来源证据和论文组织在同一个 SQLite 知识网络中，并以保守、可解释的方式分析结构化命题。

## 快速开始

需要 Python 3.9 或更高版本：

```bash
cd knowledge-engine
python3 server.py
```

打开 <http://127.0.0.1:8000>。首次运行会创建 `data/knowledge.db` 并载入种子知识；后续版本会通过幂等迁移保留并升级已有数据。

内置的第一组深度策展主题是“人工智能、意识与科学发现”。它把短词条扩展为包含重要性、机制、边界、争议和开放问题的知识档案，并关联图灵测试、基础模型、RLHF、意识理论、AlphaFold、AlphaTensor 等概念及其原始论文来源。策展安装是幂等的，不会覆盖用户已经编辑的概念。

可以通过参数修改监听地址：

```bash
python3 server.py --host 127.0.0.1 --port 8080
```

## 工作视图

- **研究简报**：从一个自然语言问题出发，聚合当前判断、策展命题、概念连接、来源论文和开放问题；覆盖不足时明确拒绝拼凑答案
- **知识网络**：组合搜索与领域筛选、结构化知识档案、局部/全局图谱、关系和来源证据编辑
- **争议议题**：把研究问题拆成竞争命题，逐条标记支持、反对、限制和来源，并给出条件化当前判断
- **假设验证**：将自然语言命题解析为“主体 + 关系 + 客体”，区分直接证据、传递推断、反证和证据不足
- **论文证据**：BibTeX 与 arXiv 导入、论文元数据检索、保留原文的本地全文分块检索
- **研究路径**：围绕命题核查、反证边界、邻接概念和相关阅读生成可选择的后续路径

## 结论语义

Atlas 的结论只表示当前本地知识库与命题的匹配情况，不代表科学共识：

- `supports`：存在方向一致的直接关系，或明确标注的传递推断
- `contradicts`：存在冲突关系、方向相反的分类/组成关系，或已知关系否定了命题
- `inconclusive`：命题不完整、没有对应关系，或支持和反对信号无法区分
- `unknown`：没有识别到知识库中的概念

论文和概念相关性只作为阅读上下文，不自动参与结论计分；论文年份也不代表证据强度。返回字段 `confidence` 为“证据匹配度”，不是统计概率。

策展议题中的命题也只作为研究上下文，不直接改变假设验证结论。专题的作用是展示争议结构和证据边界，而不是用编辑判断替代图谱证据。

推荐的命题形式：

```text
深度学习是机器学习的一种
机器学习依赖概率论
量子力学与相对论矛盾
```

## 项目结构

```text
knowledge-engine/
├── server.py          # HTTP 服务、输入验证和 REST API
├── database.py        # SQLite schema、连接和版本迁移
├── knowledge.py       # 概念、关系、证据和假设数据层
├── evidence.py        # 命题解析与方向一致的证据分析
├── reasoning.py       # 保守结论和证据匹配度
├── issues.py          # 研究议题、竞争命题与命题证据
├── briefs.py          # 问题到证据简报的数据聚合
├── search.py          # 概念 TF-IDF 检索
├── papers.py          # 论文、BibTeX、DOI 和引用网络
├── fulltext.py        # 原文分块与全文 TF-IDF 检索
├── paths.py           # 研究路径生成与选择
├── graph.py           # 本地 SVG 知识图谱
├── arxiv.py           # arXiv 查询与元数据解析
├── seed.py            # 跨学科种子数据
├── curated_content.py # 深度主题、知识档案与代表论文
├── tests/             # 标准库 unittest 回归测试
└── static/            # 原生 HTML、CSS 和 JavaScript 工作台
```

## API 摘要

```text
GET  /api/stats
GET  /api/concepts?q=&category=&limit=&offset=
GET  /api/concepts/{id}
POST /api/concepts
PUT  /api/concepts/{id}

GET  /api/relations?concept_id=
GET  /api/relations/types
POST /api/relations
GET  /api/evidence?concept_id=
POST /api/evidence

POST /api/hypothesis
POST /api/hypothesis/analyze
GET  /api/hypotheses
POST /api/brief
GET  /api/issues
GET  /api/issues/{id}
POST /api/hypothesis/paths
POST /api/paths/select

GET  /api/graph?concept_id=
GET  /api/papers?q=&limit=&offset=
GET  /api/papers/fulltext?q=
POST /api/papers
POST /api/papers/import-bibtex
POST /api/papers/import-doi
GET  /api/arxiv/search?q=
POST /api/arxiv/import
```

列表接口返回统一的 `items`、`total`、`limit` 和 `offset`（适用时）。写接口区分参数错误、数据冲突和服务器错误；URL 字段只接受 `http` 或 `https`。

## 开发与验证

运行完整回归测试：

```bash
python3 -m unittest discover -s tests -v
```

检查 Python 语法：

```bash
python3 -m py_compile database.py knowledge.py search.py graph.py evidence.py reasoning.py papers.py fulltext.py paths.py arxiv.py seed.py server.py
```

测试使用独立临时数据库，不会修改 `data/knowledge.db`。覆盖关系约束、种子方向、组合筛选、全文原文保真、论文规范化、命题正反例、否定命题、传递推断和研究路径幂等性。

## 数据与迁移

- 数据库位于 `data/knowledge.db`，该目录不提交到 Git
- `schema_meta` 保存当前 schema 版本
- 启动时自动执行未运行的迁移，不需要删除已有数据库
- 关系写入禁止自关联，确信度必须位于 `0` 到 `1`
- DOI 会规范化为小写标识，全文片段保留原始标点和语序

重要数据仍建议定期备份 SQLite 文件。Atlas 当前是单用户本地工具，不包含身份认证、实时协作或远程同步。

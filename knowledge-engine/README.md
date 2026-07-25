# Atlas · 人类知识与科学发现引擎

Atlas 是一个零外部依赖的本地知识探索 MVP。它把概念、关系和证据组织成可浏览的知识网络，并提供一个简单的假设验证实验台。

## 快速开始

需要 Python 3.9 或更高版本，不需要 Node.js、npm、数据库服务或 API Key：

```bash
cd "/Users/wanganchang/Desktop/new idea/knowledge-engine"
python3 server.py
```

然后打开 <http://127.0.0.1:8000>。按 `Ctrl+C` 停止服务。

首次启动会自动创建 `data/knowledge.db`，并填充一组跨人工智能、计算机、生物、物理、天文、数学和哲学的种子知识。

## 能做什么

- **探索概念**：关键词搜索、按领域过滤、查看定义和标签
- **关系图谱**：查看当前概念与其他概念的关系网络，也可以打开全局图谱
- **证据浏览**：查看概念关联的可追溯来源和关系说明
- **验证假设**：输入自然语言判断，基于当前知识网络返回支持、反对或证据不足
- **添加知识**：从界面创建概念；API 也支持添加关系和证据
- **本地优先**：所有数据保存在本地 SQLite 文件中，方便备份、检查和进一步接入 Git

## 项目结构

```text
knowledge-engine/
├── server.py          # http.server 服务和 REST API
├── database.py        # SQLite 初始化、连接和通用工具
├── knowledge.py       # 概念、关系、证据、假设数据层
├── search.py          # 标准库实现的 TF-IDF 检索
├── graph.py           # SVG 知识图谱渲染
├── reasoning.py       # 假设验证规则引擎
├── seed.py            # 跨学科种子数据
├── static/
│   ├── index.html     # 单页界面
│   ├── app.js         # 浏览器交互和 API 调用
│   └── style.css      # 视觉样式
└── data/knowledge.db  # 首次启动自动生成，不提交到代码仓库
```

## API 摘要

```text
GET  /api/stats
GET  /api/concepts?q=机器学习&category=人工智能
GET  /api/concepts/{id}
POST /api/concepts
GET  /api/graph?concept_id={id}
GET  /api/graph
GET  /api/relations?concept_id={id}
POST /api/relations
GET  /api/evidence?concept_id={id}
POST /api/evidence
POST /api/hypothesis
GET  /api/hypotheses
```

例如添加一个概念：

```bash
curl -X POST http://127.0.0.1:8000/api/concepts \
  -H 'Content-Type: application/json' \
  -d '{"name":"合成生物学","description":"通过工程化方式设计和构建生物系统。","category":"生物学","tags":["工程","生命"]}'
```

## 开发与验证

运行基础语法检查和数据层 smoke test：

```bash
python3 -m py_compile database.py knowledge.py search.py graph.py reasoning.py seed.py server.py
python3 seed.py
python3 - <<'PY'
import database, knowledge, search, graph, reasoning

database.init_db()
print(knowledge.get_stats())
print(search.search("机器学习"))
first = knowledge.list_concepts(q="机器学习")[0]
svg, data = graph.render_svg(first["id"])
print("graph nodes:", len(data["nodes"]), "svg:", len(svg))
print(reasoning.verify("深度学习依赖机器学习"))
PY
```

## 设计边界与下一步

当前检索和推理是**可解释的本地规则 MVP**，不是外部论文搜索引擎，也不会把启发式结果包装成科学结论。下一阶段可以在保持本地数据模型的基础上增加：

1. BibTeX / DOI / PDF 元数据导入与引用管理
2. 论文全文分块、向量检索和来源级引用
3. 用户在环的多方案研究路径选择
4. 协作编辑、冲突合并和知识变更审计
5. 接入真实科学数据库与可复现实验记录
6. 对假设输出更严格的证据等级、反例和待验证实验建议

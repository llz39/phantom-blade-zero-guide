# 影之刃零 · 影境攻略

《影之刃零》单游戏攻略智能客服。**不登录、打开即问**，答案带来源，查不到就说“暂未收录”。

> 非官方作品集 Demo。内容为公开来源的摘要与短引用，不含攻略原文、不含游戏美术素材。

---

## 1. 它是什么

- 领域：只做《影之刃零》，其他游戏与现实话题直接拒答；
- 交互：浏览器匿名会话（`anon:<uuid>`），不做注册/登录/用户表；
- 检索：**Milvus** 向量召回（HNSW + COSINE）+ 标量过滤（`game_id / doc_type / entity_id / version`）；
- 存储：**MySQL** 存攻略登记、会话、反馈、成本；
- 生成：检索结果 → LLM 按固定规则作答，强制带来源、强制拒答未知；
- 已在代码层移除 Neo4j / GraphRAG / Cypher。

```
浏览器（匿名 session）
      │  POST /api/chat
      ▼
FastAPI（限流 / CORS / 输入长度）
      ▼
Agent + LangGraph：understand → policy → action → guard → response
      ├── FlowPolicy：Boss 打法 / 材料位置 / 任务流程
      └── EnterpriseSearchPolicy：知识问答
                ▼
        MilvusRetriever（embedding API + Milvus 过滤检索）
                ▼
        Milvus（chunk 向量）      MySQL（guide_doc / trackers / feedback / cost_log）
```

---

## 2. 目录

```text
game_guide_customer_service/
├── customer_service_system/          # 通用对话框架（保留，未重写核心）
│   ├── agent/  core/  policies/  retrieval/  api/
│   └── api/templates/chat.html       # 武侠水墨风匿名聊天页
├── game_guide_demo/                  # 本领域工程
│   ├── config.yml  endpoints.yml
│   ├── app.py                        # uvicorn 入口
│   ├── domain/domain_game.yml
│   ├── data/flows/                   # flow_boss / flow_item / flow_quest
│   ├── actions/game_action.py        # action_guide_lookup
│   ├── addons/milvus_retrieval.py    # MilvusRetriever
│   ├── knowledge/phantom_blade_zero/ # 72 篇攻略 + sources.jsonl
│   ├── scripts/                      # 建库 / 入库 / 验收 / 评测
│   ├── eval/questions.jsonl          # 120 题评测集
│   ├── docs/gates/                   # M1-M8 门禁签收
│   └── README.md
├── requirements.txt
└── setup.py
```

---

## 3. 快速开始（本地）

### 3.1 依赖

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### 3.2 起 MySQL 与 Milvus

**MySQL（必需）**

```bash
mysql -uroot -p < scripts/init_mysql.sql     # 建库建表，可重复执行
```

**Milvus 用 Zilliz Cloud**

建 Serverless 免费集群 → 把 URI / Token 填进 `.env`。不需要 Docker，Windows 上最省事。

Zilliz 的变量名是 `ZILLIZ_CLOUD_URI / ZILLIZ_CLOUD_TOKEN`，
项目内部用 `MILVUS_URI / MILVUS_TOKEN`，两套都认（`env_bootstrap.py` 自动映射），填一套即可。
若你之前用 `setx` 配了系统变量，终端读不到时执行：

```bash
python scripts/sync_env.py            # 从系统环境变量同步进 .env（不打印明文）
python test.py                        # 单独验证 endpoint + token 能否连上
```

### 3.3 配置

```bash
cp .env.example .env
# 填 QWEN_API_KEY；MILVUS_URI / MYSQL_* 按实际改
```

### 3.4 建库（灌知识）

```bash
python scripts/ingest.py --dry-run     # 先看分块，不花钱
python scripts/ingest.py               # 正式入库（写 MySQL + Milvus）
```

产出 `ingest_report.json`：成功/失败/跳过数量、每篇的 chunk 数与 token 数、失败原因。

### 3.5 启动

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
# 或：llz_agent run --model .
```

打开 <http://localhost:8000/>。`/health` 应返回 `{"status":"ok",...}`。

> ⚠️ **必须用 FastAPI 提供的地址打开页面**。直接双击 `chat.html`、或用 IDE 预览/静态服务器打开，
> 页面没有 `/api/chat` 可调，点“问剑”一定失败。页面会在输入框上方用红条提示“后端未连接”，
> 这**不是**网络问题，是后端没起或地址不对。

### 3.6 自检（排障第一步）

```bash
python scripts/preflight.py            # 依赖 / .env / MySQL / Milvus / Embedding / LLM 全量检查
python scripts/preflight.py --offline  # 不联网，只查工程装配
```

任何一个 `[FAIL]` 都要先处理，否则后面的现象都会被误判成模型问题。

> 本机开着 HTTP 代理（Clash 之类）时，务必在 `.env` 里设 `NO_PROXY=localhost,127.0.0.1,::1`；
> 命令行测本机接口用 `curl --noproxy '*'`，Python 用 `httpx.Client(trust_env=False)`，
> 否则请求会被代理劫持成 `POST http%3A//127.0.0.1...` 并返回 404。

---

## 4. 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 匿名聊天页 |
| GET | `/api/chat/session` | 创建/读取匿名会话（HttpOnly Cookie） |
| POST | `/api/chat` | `{message, session_id?}` → `{text, sources[], unknown, elapsed_ms}` |
| POST | `/api/feedback` | `{session_id, rating, comment}` → 写 `feedback` 表 |
| GET | `/health` | 健康检查（含 `retriever_ready`），给平台探活用，很轻 |
| GET | `/ready` | 就绪检查：真的 ping MySQL + Milvus，任一不通返回 503 |

**默认关闭**：`/inspect`、`/docs`、`/api/domain`、`/api/flows`、`/api/tracker/*`。需要时设 `ENABLE_DEBUG_ROUTES=true`。

限流：10 次/分钟/IP、100 次/天/IP、每日总请求预算 300（`DAILY_REQUEST_LIMIT`）。单条输入 ≤ 300 字。

---

## 5. 知识库

- 目录：`knowledge/phantom_blade_zero/{weapons,bosses,story,items,faq}`
- 规模：72 篇 = 武器 19 / Boss 14 / 剧情 8 / 材料 10 / FAQ 21
- front matter 必填：`game_id / doc_type / entity_id / title / version / source_level / source_urls / updated_at / confidence`
- 来源清单：`knowledge/phantom_blade_zero/sources.jsonl`（16 条，含 S1–S4 分级与访问日期）
- 重新生成文档：`python scripts/build_knowledge.py`（数据与来源集中维护，避免手写 front matter 出错）

来源分级：S1 官方 / S2 访谈 / S3 攻略媒体 / S4 社区线索。数值类信息若只有单一来源，文中会明确写“单一来源，未交叉验证”，不当作确定值。

### 分块

- 上限 700 tokens，下限目标 300，块间 15% overlap；
- 标题优先切分，表格/材料清单/阶段不切断；
- 实测：73 块，最大 671 tokens，中位数 227；
  
  **偏差说明**：实体卡片式知识库（Boss/材料/FAQ）单条信息量常在 200–290 tokens，强行撑到 300 只能靠套话填充，与“不许为看起来完整而补内容”冲突，因此保留单块短卡片，仅保证不超上限、不碎片化。详见 `docs/gates/M3.md`。

---

## 6. 评测

```bash
python scripts/run_eval.py --retrieval-only   # Recall@5（只要 Milvus + embedding）
python scripts/run_eval.py --full --sample 24 # 抽样冒烟（省钱）
python scripts/run_eval.py --full             # 全量 120 题
```

120 题：武器 40 / Boss 40 / 剧情 20 / 对抗 20。报告写 `eval/eval_report.json`。
答案准确率需人工复核，脚本会导出每题回答供打分。

**最新实测（2026-11-08，Zilliz Cloud）**

| 指标 | 结果 | 目标 |
|---|---|---|
| 入库 | 72 篇 → **81 chunks**，Milvus 81 行 / MySQL `guide_doc` 72 行 | — |
| 知识库完整度 | 正文「暂未收录」**260 → 50 处**（-81%） | 越少越好 |
| 抽测 30 题（20 常规 + 10 对抗） | Recall@5 **100%** · 引用覆盖 **100%** · 未知识别 **100%** | ≥95% / ≥90% / ≥95% |
| 常规题拒答数 | **0 / 20** | 越少越好 |
| 检索时延 | 冷启动 1.76s，热态均值 299ms，p95 1.15s | <1.5s |
| 端到端时延 | 8–13s（两次 LLM 调用） | <8s（未达标） |

> 上一版全量 120 题为 98% / 98% / 95%。本轮不跑全量，改为定向抽测 20 常规 + 10 对抗题，
> 结果全绿。提升主要来自三处：知识库补全 8 个实体、修掉生成层 `max_tokens` 被思考过程耗尽的问题、
> 以及 Flow 卡住时不再吞掉后续消息。全量 120 题需重跑确认，命令：`run_eval.py --full`。

---

## 7. 运行方式

本项目**只在本机运行，不做公网部署**。

### 依赖两个外部服务

- **Milvus**：Zilliz Cloud（`MILVUS_URI` + `MILVUS_TOKEN` 填 `.env`）
- **MySQL**：本机实例，先执行一次 `scripts/init_mysql.sql` 建库建表

### 启动

> 📁 在 `game_guide_demo` 目录执行

```powershell
..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

浏览器打开 <http://127.0.0.1:8000/>。`/health` 返回 `agent_ready`、`retriever_ready` 都是 `true` 才算正常。

### 运维

```powershell
# 清理 7 天前的会话（可挂 Windows 任务计划）
..\.venv\Scripts\python.exe scripts\cleanup_sessions.py --days 7 --feedback
```

```sql
-- 成本日报
SELECT day, SUM(input_tokens), SUM(output_tokens), ROUND(SUM(cost_cny),4)
FROM cost_log GROUP BY day ORDER BY day DESC;
```

---

## 8. 预算与护栏

| 项 | 上限 |
|---|---:|
| LLM API | 80 元 |
| Embedding API | 20 元 |
| Milvus | 0–30 元 |
| MySQL | 0–30 元 |
| 托管 | 30–50 元 |
| 域名 | 0–20 元 |
| 预留 | 20 元 |
| 合计 | ≤ 200 元 |

代码侧护栏：单次输出 ≤ 800 tokens、检索 top_k ≤ 6、上下文 ≤ 7000 字符、最多 1 次重试、不做多模型投票、不做微调、不实时爬取。逐日成本记 `docs/成本记录.csv`。

---

## 9. 已知限制

- 知识库是**摘要型**，不是图鉴全量；未收录字段在每篇文档的 `## 暂未收录` 中逐条列出；
- 章节中译名、部分材料名仅有 S4 线索，文中已标注“待核验”；
- 武器数量存在 51/55/56 三种媒体口径，项目并列展示、不做取舍；
- 会话过期清理（7 天）由定时任务执行，SQL 见 `scripts/init_mysql.sql` 末尾；
- 限流为单进程内存实现，多实例部署需换 Redis。

---

## 10. 验收

- **日常验收手册**：`docs/验收操作手册.md` —— 环境变量清单、每次验收的 8 步、报错对照表
- 八个门禁的签收记录：`docs/gates/M1.md` … `M8.md`，未达标项与证据一并写在里面
- 未完成项：`docs/未完成项.md`
- 自检脚本：`scripts/preflight.py`（环境）、`scripts/verify_local.py`（工程 36 项）、`scripts/verify_retrieval.py`（检索）

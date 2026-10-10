# Industrial AI Agent Platform 开发计划

> 版本：v1.0
> 目标：在现有基础设施之上，连续交付一条可审计、可回滚、可进入工厂试点的数据到模型闭环。

## 1. 计划边界

当前仓库已经具备本地 Docker 基础设施、平台网关、Agent Runtime、Tool Gateway、前端控制台和 Helm 基线。现有任务执行仍是本地 `BackgroundTasks` 适配器，Agent 计划和工具返回值仍是演示实现；因此后续开发必须优先替换这些占位逻辑，再叠加数据、模型和知识能力。

本计划采用两级目标：

1. **30 个工作日工程版一期**：完成数据集、探查、标注、特征、AutoML、模型注册、Agent 编排和一次工厂试点闭环。
2. **后续 15～30 个工作日生产加固**：完成高可用、灾备、安全、边缘断网、压测、混沌和正式上线门禁。

计划按 4～6 人并行团队估算；单人执行需要按 2～3 倍时间重新排期。这里的“工程版”必须使用真实服务、真实数据和真实制品，不用静态页面或硬编码返回值替代功能。

## 2. 第一性原理约束

所有开发任务都必须满足以下约束：

- 租户和项目范围由服务端身份上下文决定，不能由请求体单独决定；每一次查询和写入都带租户过滤。
- 数据集、标签、特征、实验、模型、Agent、Tool、Prompt、知识和发布物使用不可变版本；版本通过新记录创建，不能原地覆盖。
- 业务写入、审计事件和待发布事件在同一个数据库事务内提交，使用 transactional outbox，不能在事务外直接发送事件。
- 所有命令带幂等键；幂等键必须有数据库唯一约束，并能识别“同键同请求”和“同键不同请求”。
- Agent 只能调用已注册且通过策略检查的工具；副作用操作需要审批；Agent 不直连 PLC、生产数据库或未经授权的文件系统。
- Temporal 负责持久化工作流；外部 I/O、网络、随机数和当前时间只能在 Activity 中执行，Activity 必须有超时、重试和幂等设计。
- 审计日志只追加、不更新、不删除，记录 actor、tenant、trace、resource、action、reason 和结果，禁止写入 Token、密码和大段敏感数据。
- 每个训练或发布结果都必须关联数据集版本、特征版本、代码提交、环境摘要和制品 digest。
- HTTP、事件和模型输入输出都必须有运行时 Schema 校验；错误响应不能泄露跨租户资源是否存在。

## 3. 目标闭环

```text
工厂数据/文件/数据库
  → 数据接入与目录
  → 数据质量、探查、热力图
  → 标注与数据集版本
  → 特征工程与特征版本
  → AutoML / 训练 / 评测
  → 模型注册、审批、发布
  → 中心或边缘推理
  → 监控、反馈、漂移检测
  → 再标注、再训练、再发布
```

```text
用户/前端 → API → Temporal Workflow → Supervisor Agent
  → 专业 Agent → Tool Gateway → 数据/训练/模型/知识/边缘工具
```

## 4. 服务和配套组件

| 层 | 本期实现 | 后续生产增强 |
|---|---|---|
| 控制面 | FastAPI、PostgreSQL、SQLAlchemy、Alembic、OpenAPI | OIDC、OPA、Vault、PITR、只读副本 |
| 工作流 | Temporal Python SDK、Worker、Activity、审批 Signal | Worker Versioning、任务队列隔离、背压和多集群 |
| 数据面 | S3/SeaweedFS、Parquet、ClickHouse、Polars、DuckDB | Iceberg、Flink/Spark、OpenMetadata、OpenLineage |
| 数据质量 | Schema、空值、重复、分布、时间连续性和标签泄漏检查 | Great Expectations 规则中心和质量门禁 |
| 标注 | Label Studio 项目、预标注、回调、标签版本 | 多人一致性、主动学习和审计导出 |
| 特征 | Feature Definition、Point-in-time Join、离线回填 | Feast Online/Offline Store、特征服务高可用 |
| AutoML | Optuna、LightGBM、XGBoost、CatBoost、SHAP | GPU 训练队列、分布式搜索和资源配额 |
| 模型 | MLflow Tracking/Registry、模型卡、制品 digest | KServe/Triton、影子、灰度、自动回滚 |
| 知识 | 文档版本、pgvector、混合检索、引用 | OpenSearch、Neo4j、知识图谱和跨工厂权限 |
| 观测 | OpenTelemetry、Prometheus、Grafana | Tempo/Loki、SLO、告警路由和成本分析 |
| 边缘 | ONNX Runtime、Edge Agent、本地缓存 | K3s/KubeEdge、MQTT、OPC-UA、断网同步 |
| 交付 | Docker、Helm、GitHub Actions、契约测试 | Argo CD、SBOM、Trivy、Cosign、混沌工程 |

## 5. 30 个工作日排期

### 第 1～5 天：控制面、契约、版本和审计

- 设计并落地 Tenant、Project、Dataset、DatasetVersion、Artifact、AuditEvent、OutboxEvent、Agent、Tool、WorkflowRun 等领域表。
- 添加 PostgreSQL Migration、索引、唯一约束和租户范围约束。
- 完成 OpenAPI、JSON Schema、CloudEvents 事件契约和错误码。
- 完成身份上下文适配：OIDC 接口、开发环境 Header Adapter、角色和项目授权。
- 将任务创建改为“数据库记录 + 审计事件 + Outbox 事件”同事务提交。
- 建立 Temporal Workflow/Activity 目录，移除关键流程对 `BackgroundTasks` 的依赖。

验收：可登录、可创建项目和数据集、可创建版本、同一幂等键重复请求结果一致、跨租户不能读取、审计和 Outbox 同事务存在。

### 第 6～10 天：数据接入、数据目录、探查和标注

- 接入 CSV、Parquet、PostgreSQL、REST；定义后续 Kafka、MQTT、OPC-UA Connector 接口。
- 原始数据写入对象存储，生成内容指纹、Schema 指纹和 DatasetVersion。
- 实现数据预览、统计摘要、缺失率、唯一值、异常值、时间间隔、类别不平衡和泄漏初筛。
- 实现特征相关性、目标变量、工位、设备、时间段和缺陷分布热力图。
- 接入 Label Studio：项目创建、样本导入、预标注、审核、导出和标签版本。

验收：一个真实样例数据集可以生成可复现探查报告、热力图和标签版本；质量不合格的数据不能进入训练。

### 第 11～15 天：特征工程和 AutoML

- 建立 Feature、FeatureView、Transformation、Backfill 领域模型。
- 实现缺失处理、窗口统计、聚合、变化率、编码和时间切分。
- 实现 Point-in-time Join，阻止未来信息泄漏。
- 建立分类、回归、异常检测和预测任务定义。
- 使用 Optuna 搜索 LightGBM、XGBoost、CatBoost 和基线模型。
- 将数据版本、特征版本、代码提交、环境摘要、指标、解释结果和模型制品写入 MLflow。

验收：从 DatasetVersion 能自动生成 FeatureView、训练 Run、Best Run 和 Model Candidate，并能够复现。

### 第 16～19 天：模型注册、发布和回滚

- 实现 `DRAFT → CANDIDATE → STAGING → PRODUCTION → RETIRED` 状态机。
- 增加准确率、鲁棒性、延迟、资源、解释性和数据质量发布门禁。
- 使用 ONNX Runtime 实现 CPU 推理 API。
- 接入 KServe 或 Triton，支持影子、灰度、流量切换和回滚。
- 模型、镜像和配置使用 digest，发布时记录审批人和证据。

验收：模型可以从注册中心部署到中心或边缘，完成在线预测、灰度、回滚和发布审计。

### 第 20～22 天：Agent Registry、Tool Gateway 和编排

- 实现 Agent Manifest、Prompt、模型、工具、策略、版本和发布。
- 实现 Data Scout、EDA、Feature Engineer、Labeling、AutoML、Evaluation、Release 和 Monitoring Agent。
- Tool Gateway 支持 JSON Schema、风险等级、权限 scope、超时、重试、幂等和审批。
- Temporal 负责长流程；Agent Runtime 负责单次计划和上下文。
- 统一 task_id、step_id、trace_id、artifact_id 和 workflow_id 的传播。

验收：自然语言任务可以形成真实工作流，遇到发布或 OT 副作用时暂停等待审批，所有工具调用可以追溯。

### 第 23～24 天：知识工程和 Copilot

- 导入 SOP、维修手册、质量标准、报警说明、历史问题单和模型卡。
- 实现文档解析、分块、嵌入、pgvector、关键词混合检索、引用和权限过滤。
- 知识文档也必须版本化，回答必须带来源；无证据时禁止编造。

### 第 25～27 天：反馈、漂移和工厂边缘

- 记录人工接受、拒绝、误报、漏报和现场修正。
- 实现数据漂移、特征漂移、标签漂移、模型性能、推理延迟和 Agent 成本监控。
- 实现 ONNX 模型边缘缓存、签名校验、断网运行、重新联网补传、远程升级和回滚。
- 接入 MQTT/OPC-UA 适配器；Agent 和大模型不能直连 PLC。

### 第 28～30 天：生产验证和试点

- GitHub Actions、单元测试、契约测试、集成测试、镜像扫描、SBOM、Secret Scan 和 Helm 检查。
- 演练 Worker 重启、消息重复、网络分区、数据库异常、对象存储异常、边缘断网和模型回滚。
- 选择一条产线、一个缺陷类型、一个数据源和一个预测模型完成现场试点。

## 6. 第一周代码任务拆解

第一周按以下顺序实施：

1. `services/platform-gateway/app/db.py`：控制面领域模型、唯一约束、审计表和 Outbox 表。
2. `services/platform-gateway/app/main.py`：项目、数据集、数据集版本、审计查询 API。
3. `schemas/`：控制面资源 Schema 和错误响应 Schema。
4. `infra/migrations/`：初始 Migration 和升级校验。
5. `tests/`：租户隔离、幂等竞态、版本不可变、审计不可变、Outbox 同事务测试。
6. `workflows/`：Temporal Workflow/Activity 最小真实骨架。
7. `docs/`：接口、状态机、威胁模型、运行手册和回滚说明。

## 7. 对抗式审查清单

每次提交合并前必须验证：

- 两个租户使用相同资源 ID，不能互相读取、更新或从错误信息中枚举存在性。
- 并发提交相同幂等键时只产生一条业务记录；同键不同请求必须拒绝。
- 陈旧版本更新、非法状态跃迁、终态回退和重复发布必须拒绝。
- 数据库提交后进程崩溃时，Outbox 仍可补发；重复事件消费不会重复副作用。
- Worker 崩溃、Activity 超时、Workflow 重放和 Signal 重复不会造成重复发布。
- Token、密码、完整数据行和大段 Prompt 不得进入日志、审计或 Temporal Payload。
- 大请求、深 JSON、分页、SQL 注入、Prompt 注入、恶意文档和 Poison Event 不会拖垮服务。
- Migration 在空库、上一版本库和中断恢复场景都可以执行。

## 8. 每个功能的完成定义

一个功能只有同时具备以下内容才算完成：

- API 和运行时 Schema；
- 数据库 Migration；
- 权限和审计；
- 事件或 Outbox；
- 前端页面或可验证 CLI；
- 单元、契约和集成测试；
- 指标、日志和 trace；
- Docker/Helm 配置；
- 回滚和运维文档。

## 9. 建议的 GitHub Epic

```text
EPIC-01 控制面与租户权限
EPIC-02 数据源与数据目录
EPIC-03 数据质量与探查
EPIC-04 标注闭环
EPIC-05 特征工程
EPIC-06 AutoML 与实验管理
EPIC-07 模型注册与发布
EPIC-08 Agent Registry 与 Tool Gateway
EPIC-09 Temporal 工作流
EPIC-10 知识工程与 RAG
EPIC-11 反馈与漂移监控
EPIC-12 工厂边缘部署
EPIC-13 安全、测试与生产验收
```


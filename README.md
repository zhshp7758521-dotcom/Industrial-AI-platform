# Industrial AI Agent Platform

面向汽车整车工厂的生产级工业智能体平台工程基线。

## 目标

平台按控制面、运行面、数据面、治理面和边缘面设计，支持：

- 工业数据接入、数据契约、数据目录和质量治理
- 数据探查、热力图分析、特征工程、标注和 AutoML
- 模型注册、评测、签名、灰度发布、回滚和漂移监控
- Supervisor + 专业 Agent + Tool Gateway + 工作流编排
- 工艺知识库、知识图谱、RAG 和工程师 Copilot
- 中心 Kubernetes + 工厂边缘 K3s/KubeEdge

## 工程原则

1. 控制面和数据面分离。
2. Agent 只能调用注册工具，不能直接访问生产数据库或 PLC。
3. 数据、特征、标签、实验、模型、Prompt、知识和 Agent 均使用不可变版本。
4. 生产工作流使用持久化状态机和补偿机制，不把关键流程放在 Prompt 中。
5. 所有结果关联 `trace_id`、`artifact_id` 和版本信息。
6. 先保证接口、契约和治理稳定，再按负载拆分服务。

## 目录

```text
services/       控制面和数据面服务
agents/         专业 Agent 实现
schemas/        OpenAPI、JSON Schema、AsyncAPI 契约
infra/          Docker、Kubernetes、Helm、Terraform
docs/           架构、ADR、运维和安全文档
scripts/        本地开发、迁移、测试、发布脚本
tests/          单元、契约、集成、Agent、安全和混沌测试
```

## 本地开发

本地开发环境只用于验证，不代表生产拓扑。生产目标是 Kubernetes 集群、PostgreSQL、Kafka、对象存储、Redis、Temporal、模型服务和边缘集群。

```powershell
./scripts/bootstrap.ps1
Copy-Item .env.example .env
# 编辑 .env，至少设置 POSTGRES_PASSWORD、TEMPORAL_POSTGRES_PASSWORD 和 S3_SECRET_ACCESS_KEY
docker compose --env-file .env -f infra/docker/compose.dev.yml up -d
./scripts/run-local.ps1
pnpm --dir apps/web-console install --frozen-lockfile
./scripts/run-console.ps1
```

`.env` 只保存在本地，不应提交到 Git。生产环境请使用 Vault、云密钥管理或 Kubernetes Secret 注入同名变量。

## 生产部署目标

- 中心：Kubernetes + GPU 节点 + GitOps
- 工厂：K3s/KubeEdge + 边缘网关 + 实时推理
- 数据：Kafka/Redpanda、对象存储、Iceberg、ClickHouse、Feature Store
- 运行：Temporal、Agent Runtime、Tool Gateway、模型服务
- 治理：OIDC、RBAC/ABAC、OPA、Vault、OpenTelemetry、SBOM、镜像签名


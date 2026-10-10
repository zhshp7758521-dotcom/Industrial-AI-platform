# 开发约定

## 版本与契约

- API 以 OpenAPI 为先，事件以 AsyncAPI/CloudEvents 为先。
- Agent、Tool、Workflow、Model 使用语义化版本和 immutable digest。
- 生产环境引用具体 revision，不允许使用 floating latest。
- 跨服务只传资源 ID、版本和 artifact 引用。

## 错误分类

```text
POLICY_DENIED
SCHEMA_INVALID
TIMEOUT
DEPENDENCY_UNAVAILABLE
QUOTA_EXCEEDED
MODEL_ERROR
DATA_QUALITY
EXTERNAL_SIDE_EFFECT
```

## 测试门禁

- 单元测试、API 契约测试、事件契约测试。
- 数据 Schema、质量、时间顺序和标签泄漏检查。
- 模型准确率、延迟、鲁棒性、资源和可解释性检查。
- Agent 工具白名单、越权、Prompt 注入、SQL 注入和敏感信息测试。
- Worker 重启、消息重复、网络分区、边缘断网和回滚演练。


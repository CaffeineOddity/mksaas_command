# Notification 环境分组需求

## 1. 目标

本分组定义 `Notification` 相关环境变量的采集、确认、回写与最终落地规则。

## 2. 参考说明

参考官方文档：

1. [MkSaaS 环境配置](https://mksaas.com/zh/docs/env)

需要遵循的基础原则：

1. 环境变量以项目根目录的 `.env` 体系为最终落点
2. 采集时应参考 `env.example` 或 `.env.example`
3. `.env`、`.env.test`、`.env.prod` 与整个 `.mksaas/` 目录都不能提交到版本控制
4. 最终完成配置后，应支持通过 `pnpm run dev` 验证环境是否正确

## 3. 独立命令

```bash
mksaas env notification [--profile test|prod]
```

要求：

1. 该命令可单独执行
2. 启动时先读取 `.mksaas/setup-state.json`
3. 若 JSON 中已有值，必须先展示并让用户确认是否修改
4. 修改完成后立即回写 JSON

## 4. 变量范围

1. `DISCORD_WEBHOOK_URL`
2. `FEISHU_WEBHOOK_URL`

## 5. 采集流程说明

建议按以下顺序执行：

1. 读取 `.mksaas/setup-state.json` 中当前分组和当前 profile 的已有配置
2. 按“已存在值 / 未配置值 / 自动生成值”三类展示当前状态
3. 先让用户选择一种通知渠道，例如 Discord 或飞书
4. 根据所选渠道，只展示并采集对应的 webhook 字段，而不是把所有渠道字段一起逐项询问
5. 告知用户该渠道字段的用途，并提示先到对应平台创建 webhook
6. 对输入值做基础校验，例如 URL 或 webhook 是否为空
7. 将结果回写到 `.mksaas/setup-state.json`，并清理未选中渠道的旧字段，标记当前分组已采集但尚未 apply
8. 在最后一步 `mksaas apply` 中，将本分组内容合并进 `.env.*`
9. apply 完成后，支持通过 `pnpm run dev` 做环境验证

## 6. 流程图

```mermaid
flowchart TD
    A[执行 mksaas env notification] --> B[读取 setup-state.json]
    B --> C{是否已有 Notification 配置}
    C -->|是| D[展示当前已选渠道与已有值]
    C -->|否| E[进入 Notification 采集流程]
    D --> F{是否修改}
    F -->|否| G[沿用已有配置]
    F -->|是| E
    E --> H[先选择通知渠道]
    H --> I[仅采集该渠道对应字段]
    I --> J[清理未选中渠道的旧字段]
    G --> K[更新 JSON 对应分组]
    J --> K
    K --> L[标记已采集未应用]
    L --> M[等待 apply 统一生成 env]
```

## 7. 时序图

```mermaid
sequenceDiagram
    participant U as 用户
    participant C as CLI
    participant J as setup-state.json
    participant D as 官方文档/第三方平台

    U->>C: mksaas env notification
    C->>J: 读取 notification 分组配置
    J-->>C: 返回已有值或空结果
    C->>U: 展示当前已选渠道、已有值与缺失项
    U->>C: 选择沿用或修改
    alt 需要补充配置
        C->>U: 先选择一种通知渠道
        C->>U: 提示前往对应平台创建 webhook
        U->>D: 获取所需参数
        U->>C: 仅回填所选渠道的字段值
    end
    C->>C: 校验字段格式与必填项
    C->>J: 回写 notification 分组配置
    C-->>U: 提示需在 apply 阶段统一落地并可用 pnpm run dev 验证
```

## 8. 采集要求

1. 进入本分组后必须先选择一种通知渠道
2. 仅采集当前所选渠道对应字段，不应把所有渠道字段一起展示
3. 若已有值，仅展示当前已选择的渠道与摘要
4. 提示用户先在通知平台创建 webhook

## 9. 生成要求

1. webhook URL 写入 `.env.*`
2. 未选中的渠道字段应按 schema 默认值或空值输出，不保留旧渠道残留值
3. 当前仅应保留所选渠道的有效配置

## 10. 安全要求

1. 不得在终端打印完整 webhook 地址
2. 采集时对 webhook URL 使用隐藏输入

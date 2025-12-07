# AnyRouter 自动签到

多平台多账号自动签到，支持 NewAPI/OneAPI 平台。

## 使用方法

### 1. Fork 本仓库

### 2. 获取账号信息

#### Cookies
1. 访问 https://anyrouter.top/ 并登录
2. F12 打开开发者工具 → Application → Cookies
3. 复制 `session` 的值

#### API User
1. F12 → Network → 过滤 Fetch/XHR
2. 找到带 `New-Api-User` 请求头的请求，复制该值（正常是 5 位数）

### 3. 配置 GitHub Secrets

1. Settings → Environments → New environment → 创建 `production`
2. Add environment secret：
   - Name: `ANYROUTER_ACCOUNTS`
   - Value: 账号配置 JSON

### 4. 账号配置格式

```json
[
  {
    "name": "主账号",
    "cookies": {"session": "xxx"},
    "api_user": "12345"
  },
  {
    "name": "备用账号",
    "provider": "agentrouter",
    "cookies": {"session": "yyy"},
    "api_user": "67890"
  }
]
```

- `cookies`、`api_user`：必填
- `provider`：可选，默认 `anyrouter`，可选 `agentrouter`
- `name`：可选，用于日志显示

### 5. 运行

- 自动：每 6 小时执行一次
- 手动：Actions → AnyRouter 自动签到 → Run workflow

## 注意事项

- Session 有效期约 1 个月，401 错误需重新获取
- 支持部分账号失败，有成功则任务不失败

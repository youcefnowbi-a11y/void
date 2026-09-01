@echo off
REM VOIDFORGE MSVC env — vcvars64 + manual Windows SDK registration
REM (the SDK is installed but NOT registered with this BuildTools instance,
REM  so vcvars64 alone leaves INCLUDE without ucrt/um/shared — we append).
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1

set "SDK_INC=C:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0"
set "SDK_LIB=C:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0"

set "INCLUDE=%INCLUDE%;%SDK_INC%\ucrt;%SDK_INC%\um;%SDK_INC%\shared;%SDK_INC%\winrt;%SDK_INC%\cppwinrt"
set "LIB=%LIB%;%SDK_LIB%\ucrt\x64;%SDK_LIB%\um\x64"
set "PATH=%PATH%;C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64"

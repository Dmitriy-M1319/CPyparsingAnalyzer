@echo off

%~d0
cd "%~dp0"


del /f /q .\runtime.netmodule .\runtime.msil
rem stoped without cmd /c
cmd /c ..\bin\csc /target:module /out:.\runtime.netmodule .\runtime.cs
..\bin\ildasm /text /out:.\runtime.msil .\runtime.netmodule

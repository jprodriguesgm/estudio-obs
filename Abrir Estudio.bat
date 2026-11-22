@echo off
rem Abre o Estudio (Windows). Dois cliques. Deixe esta janela aberta enquanto estiver gravando.
chcp 65001 >nul
cd /d "%~dp0"
where py 1>NUL 2>NUL
if %errorlevel%==0 (
  py -3 -m estudio abrir
) else (
  python -m estudio abrir
)
if errorlevel 1 (
  echo.
  echo Nao consegui abrir o Estudio. O Python esta instalado? Veja o INSTALAR.md.
  pause
)

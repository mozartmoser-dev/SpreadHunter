@echo off
REM ==========================================================
REM   SPREADHUNTER — Instalacao automatica
REM   Execute uma unica vez ao receber o projeto
REM ==========================================================

echo.
echo === SPREADHUNTER :: INSTALADOR ===
echo.

REM 1. Verifica Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale o Python 3.13.14 de https://www.python.org/downloads/release/python-31314/
    echo IMPORTANTE: marque "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYV=%%v
echo [OK] Python %PYV% encontrado.

REM 2. Cria .env a partir do .env.example (se nao existir)
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [OK] .env criado a partir do exemplo.
        echo [AVISO] Edite o arquivo .env com seu CPF e senha do opcoes.net.br
    ) else (
        echo [AVISO] .env.example nao encontrado. Crie um .env manualmente.
    )
) else (
    echo [OK] .env ja existe.
)

REM 3. Instala dependencias
echo.
echo Instalando pacotes do requirements.txt...
echo (isso pode levar 1-2 minutos na primeira vez)
echo.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar pacotes. Veja o log acima.
    pause
    exit /b 1
)

echo.
echo === INSTALACAO CONCLUIDA ===
echo.
echo Proximo passo: clique duas vezes em run.bat para abrir o app.
echo Se der erro, copie a mensagem em vermelho e envie pro suporte.
echo.
pause

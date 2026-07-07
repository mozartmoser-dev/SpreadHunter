@echo off
REM ==========================================================
REM   SPREADHUNTER — Instalacao + Execucao automatica
REM   Clique duas vezes aqui para rodar tudo
REM ==========================================================

echo.
echo === SPREADHUNTER ===
echo.

REM 1. Verifica Python 3.12+ instalado
set NEEDS_PYTHON=0
where python >nul 2>&1
if errorlevel 1 (
    set NEEDS_PYTHON=1
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYV=%%v
    REM Compara major.minor com 3.12
    for /f "tokens=1,2 delims=." %%a in ("%PYV%") do (
        set MAJOR=%%a
        set MINOR=%%b
    )
    if %MAJOR% LSS 3 (
        set NEEDS_PYTHON=1
    )
    if %MAJOR% EQU 3 if %MINOR% LSS 12 (
        set NEEDS_PYTHON=1
    )
)

if "%NEEDS_PYTHON%"=="1" (
    if not defined PYV set PYV=nao encontrado
    echo.
    echo ############################################################
    echo #  Voce tem Python "%PYV%". Spreadhunter precisa de 3.12+.  #
    echo #  Vamos abrir a pagina de download da versao 3.13.14.    #
    echo ############################################################
    echo.
    echo IMPORTANTE ao instalar:
    echo   - Na primeira tela, MARQUE a opcao
    echo     "Add python.exe to PATH" (obrigatorio!)
    echo   - Depois clique em "Install Now"
    echo.
    echo Apos instalar, clique duas vezes NESTE arquivo de novo.
    echo.
    pause
    start "" https://www.python.org/downloads/release/python-31314/
    exit /b 1
)

echo [OK] Python %PYV% encontrado.

REM 2. Instala pacotes (1 vez)
if not exist ".installed" (
    echo.
    echo Primeira execucao: instalando as bibliotecas do app...
    echo (isso pode levar 1-2 minutos na primeira vez)
    echo.
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERRO] Falha ao instalar bibliotecas.
        echo Tente manualmente: abra o CMD nesta pasta e rode
        echo   python -m pip install -r requirements.txt
        pause
        exit /b 1
    )
    type nul > .installed
    echo [OK] Bibliotecas instaladas.
) else (
    echo [OK] Bibliotecas ja instaladas.
)

REM 3. Garante .env
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [OK] .env criado. Edite com seu CPF e senha do opcoes.net.br antes de usar.
    )
) else (
    echo [OK] .env ja existe.
)

REM 4. Cria pasta logs
if not exist "logs" mkdir logs

echo.
echo === ABRINDO SPREADHUNTER ===
echo (logs aparecerao nesta janela — se der erro em VERMELHO,
echo  copie tudo e mande pro suporte)
echo.

REM 5. Roda
python main.py
if errorlevel 1 (
    echo.
    echo [ERRO] Spreadhunter fechou com erro.
    echo Copie as mensagens em VERMELHO acima e envie pro suporte.
    pause
)

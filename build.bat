@echo off
:: build.bat - Revit2Etabs Executable Builder
:: Este script automatiza la compilación de Revit2Etabs.exe usando PyInstaller.

echo ======================================================
echo           Revit2Etabs - Compilador Ejecutable
echo ======================================================
echo.

:: 1. Verificar existencia de entorno virtual
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] No se encontró el entorno virtual venv en la carpeta raíz.
    echo Asegúrate de ejecutar este script en la raíz del proyecto Revit2Etabs.
    pause
    exit /b 1
)

:: 2. Activar entorno virtual
echo [INFO] Activando entorno virtual .venv...
call venv\Scripts\activate.bat

:: 3. Verificar/Instalar PyInstaller
echo [INFO] Verificando instalación de PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller no está instalado. Instalando pyinstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar PyInstaller. Verifica tu conexión a internet.
        pause
        exit /b 1
    )
) else (
    echo [INFO] PyInstaller ya está instalado.
)

:: 4. Limpiar compilaciones previas
echo [INFO] Limpiando compilaciones anteriores (build/, dist/)...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"

:: 5. Ejecutar PyInstaller con el archivo .spec
echo [INFO] Compilando la aplicación (esto puede tomar un momento)...
pyinstaller --clean Revit2Etabs.spec

:: 6. Validar resultado de compilación
if exist "dist\Revit2Etabs.exe" (
    echo.
    echo ======================================================
    echo [SUCCESS] Compilación completada con éxito!
    echo El archivo ejecutable se encuentra en: dist\Revit2Etabs.exe
    echo ======================================================
) else (
    echo.
    echo ======================================================
    echo [ERROR] Falló la compilación de la aplicación.
    echo Revisa los mensajes de error arriba para más detalles.
    echo ======================================================
)

echo.
pause

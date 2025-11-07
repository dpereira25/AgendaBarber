@echo off
echo Activando entorno virtual...
call venv\Scripts\activate.bat
echo.
echo Entorno virtual activado. Para ejecutar el proyecto:
echo cd dev\capstone
echo python manage.py runserver
echo.
cmd /k
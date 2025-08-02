@echo off
chcp 936 > nul
echo 正在设置视频制作系统数据库...
echo.

rem 获取MySQL路径
set /p MYSQL_PATH=请输入MySQL可执行文件路径 (例如: C:\Program Files\MySQL\MySQL Server 8.0\bin 或留空使用环境变量): 

set /p MYSQL_USER=请输入MySQL用户名 (默认: root): 
if "%MYSQL_USER%"=="" set MYSQL_USER=root

set /p MYSQL_PASSWORD=请输入MySQL密码 (默认: root): 
if "%MYSQL_PASSWORD%"=="" set MYSQL_PASSWORD=root

echo.
echo 正在连接到MySQL并创建数据库...

rem 如果用户提供了MySQL路径，则使用它
if not "%MYSQL_PATH%"=="" (
    "%MYSQL_PATH%\mysql" -u%MYSQL_USER% -p%MYSQL_PASSWORD% < create_database.sql
) else (
    mysql -u%MYSQL_USER% -p%MYSQL_PASSWORD% < create_database.sql
)

if %ERRORLEVEL% EQU 0 (
    echo.
    echo 数据库创建成功!
    
    echo.
    echo 正在更新配置文件...
    
    echo import pymysql > ..\app\utils\mysql_config_helper_temp.py
    echo import os >> ..\app\utils\mysql_config_helper_temp.py
    echo. >> ..\app\utils\mysql_config_helper_temp.py
    echo conn_params = { >> ..\app\utils\mysql_config_helper_temp.py
    echo     "host": "localhost", >> ..\app\utils\mysql_config_helper_temp.py
    echo     "port": 3306, >> ..\app\utils\mysql_config_helper_temp.py
    echo     "user": "%MYSQL_USER%", >> ..\app\utils\mysql_config_helper_temp.py
    echo     "password": "%MYSQL_PASSWORD%",  # 已根据输入更新 >> ..\app\utils\mysql_config_helper_temp.py
    echo     "database": "videomaker", >> ..\app\utils\mysql_config_helper_temp.py
    echo     "charset": "utf8mb4" >> ..\app\utils\mysql_config_helper_temp.py
    echo } >> ..\app\utils\mysql_config_helper_temp.py
    
    type ..\app\utils\mysql_config_helper.py | findstr /v "host" | findstr /v "user" | findstr /v "password" | findstr /v "conn_params" | findstr /v "import" >> ..\app\utils\mysql_config_helper_temp.py
    
    move /y ..\app\utils\mysql_config_helper_temp.py ..\app\utils\mysql_config_helper.py > nul
    
    echo 配置文件已更新!
) else (
    echo.
    echo MySQL命令执行失败。请确保:
    echo 1. MySQL已经安装
    echo 2. MySQL bin目录已添加到PATH环境变量
    echo 3. 或者提供MySQL bin目录的完整路径
)

echo.
echo 按任意键退出...
pause > nul 
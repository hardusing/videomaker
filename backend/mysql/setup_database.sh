#!/bin/bash

echo "正在设置视频制作系统数据库..."
echo

# 获取用户输入
read -p "请输入MySQL用户名 (默认: root): " MYSQL_USER
MYSQL_USER=${MYSQL_USER:-root}

read -s -p "请输入MySQL密码 (默认: root): " MYSQL_PASSWORD
MYSQL_PASSWORD=${MYSQL_PASSWORD:-root}
echo

echo
echo "正在连接到MySQL并创建数据库..."

# 执行SQL脚本
mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" < create_database.sql

if [ $? -eq 0 ]; then
    echo
    echo "数据库创建成功!"
    
    echo
    echo "正在更新配置文件..."
    
    # 创建临时配置文件
    cat > ../app/utils/mysql_config_helper_temp.py << EOF
import pymysql
import os

conn_params = {
    "host": "localhost",
    "port": 3306,
    "user": "$MYSQL_USER",
    "password": "$MYSQL_PASSWORD",  # 已根据输入更新
    "database": "videomaker",
    "charset": "utf8mb4"
}
EOF
    
    # 添加原有文件中的函数部分
    grep -v "import" ../app/utils/mysql_config_helper.py | grep -v "host" | grep -v "user" | grep -v "password" | grep -v "conn_params" >> ../app/utils/mysql_config_helper_temp.py
    
    # 替换原有文件
    mv -f ../app/utils/mysql_config_helper_temp.py ../app/utils/mysql_config_helper.py
    
    echo "配置文件已更新!"
else
    echo
    echo "数据库创建失败，请检查错误信息并重试"
fi

echo
echo "按Enter键退出..."
read 
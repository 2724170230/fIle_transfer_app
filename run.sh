#!/bin/bash

# 颜色配置
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

echo -e "${BLUE}SendNow 文件传输工具启动脚本${NC}"
echo "================================="
echo 

# 检查Docker是否安装
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    DOCKER_AVAILABLE=true
    echo -e "${GREEN}检测到Docker和Docker Compose已安装${NC}"
else
    DOCKER_AVAILABLE=false
    echo -e "${YELLOW}未检测到Docker或Docker Compose${NC}"
fi

# 检查Python环境
if command -v python3 &> /dev/null; then
    PYTHON_AVAILABLE=true
    echo -e "${GREEN}检测到Python3已安装${NC}"
else
    PYTHON_AVAILABLE=false
    echo -e "${YELLOW}未检测到Python3${NC}"
fi

echo
echo "请选择启动方式:"
echo "1. 直接运行Python应用"
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "2. 使用Docker运行应用(推荐)"
fi
echo "0. 退出"

read -p "请输入选择 [0-2]: " choice

case $choice in
    1)
        echo -e "${BLUE}正在启动Python应用...${NC}"
        if [ "$PYTHON_AVAILABLE" = true ]; then
            # 检查虚拟环境
            if [ -d ".venv" ] || [ -d "venv" ]; then
                if [ -d ".venv" ]; then
                    source .venv/bin/activate
                else
                    source venv/bin/activate
                fi
                echo -e "${GREEN}已激活虚拟环境${NC}"
            else
                echo -e "${YELLOW}未检测到虚拟环境,将使用系统Python${NC}"
            fi
            
            # 检查依赖
            if [ ! -f "requirements.txt" ]; then
                echo -e "${YELLOW}警告: 未找到requirements.txt文件${NC}"
            else
                echo -e "${BLUE}正在检查依赖...${NC}"
                pip install -r requirements.txt
            fi
            
            # 启动应用
            python3 localsend_app.py
        else
            echo -e "${YELLOW}错误: 未安装Python3,无法直接运行应用${NC}"
            exit 1
        fi
        ;;
    2)
        if [ "$DOCKER_AVAILABLE" = true ]; then
            echo -e "${BLUE}正在使用Docker启动应用...${NC}"
            
            # 检测操作系统类型
            OS="$(uname -s)"
            case "${OS}" in
                Linux*)     
                    echo -e "${BLUE}检测到Linux系统${NC}"
                    echo -e "${BLUE}设置X11权限...${NC}"
                    xhost +local:docker
                    docker-compose up -d
                    ;;
                Darwin*)    
                    echo -e "${BLUE}检测到macOS系统${NC}"
                    echo -e "${YELLOW}注意: 在macOS上使用Docker运行GUI应用需要额外配置${NC}"
                    echo "请确保已安装并启动XQuartz,并在XQuartz偏好设置中允许网络客户端连接"
                    echo "详细说明请参考README.md"
                    read -p "是否继续? (y/n): " confirm
                    if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
                        IP=$(ifconfig en0 | grep inet | awk '$1=="inet" {print $2}')
                        echo -e "${BLUE}使用IP: $IP${NC}"
                        DISPLAY=$IP:0
                        xhost + $IP
                        docker-compose up -d
                    else
                        echo "已取消"
                        exit 0
                    fi
                    ;;
                MINGW*|CYGWIN*|MSYS*)
                    echo -e "${BLUE}检测到Windows系统${NC}"
                    echo -e "${YELLOW}注意: 在Windows上使用Docker运行GUI应用需要额外配置${NC}"
                    echo "请确保已安装并启动X服务器(如VcXsrv),并设置'Disable access control'"
                    echo "详细说明请参考README.md"
                    read -p "是否继续? (y/n): " confirm
                    if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
                        docker-compose up -d
                    else
                        echo "已取消"
                        exit 0
                    fi
                    ;;
                *)          
                    echo -e "${YELLOW}未知操作系统: ${OS}${NC}"
                    echo "将尝试直接启动Docker容器"
                    docker-compose up -d
                    ;;
            esac
        else
            echo -e "${YELLOW}错误: 未安装Docker或Docker Compose${NC}"
            exit 1
        fi
        ;;
    0)
        echo "退出"
        exit 0
        ;;
    *)
        echo -e "${YELLOW}无效选择${NC}"
        exit 1
        ;;
esac 
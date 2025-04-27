FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    x11-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
COPY *.py .
COPY icons/ icons/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 为GUI应用设置环境变量
ENV QT_X11_NO_MITSHM=1
ENV QT_GRAPHICSSYSTEM="native"
ENV DISPLAY=:0

# 暴露应用使用的端口
EXPOSE 45678/udp
EXPOSE 45679/tcp

# 启动应用
CMD ["python", "localsend_app.py"] 
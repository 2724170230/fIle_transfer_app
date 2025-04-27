# SendNow 文件传输工具

基于Python-Qt的局域网文件传输工具，风格参考LocalSend.org。

## 功能特点

- 简洁现代的深色UI界面
- 局域网内自动发现设备
- 支持接收和发送文件
- 拖放文件上传功能
- 文件传输进度显示
- 可自定义保存路径

## 安装与运行

### 方式一：直接安装运行

#### 环境要求

- Python 3.6+
- PyQt5
- netifaces

#### 安装依赖

```bash
pip install -r requirements.txt
```

#### 运行应用

```bash
python localsend_app.py
```

### 方式二：使用Docker运行（推荐）

使用Docker可以在任何支持Docker的操作系统上运行SendNow，无需安装Python或其他依赖。

#### 前提条件

- 安装 [Docker](https://docs.docker.com/get-docker/)
- 安装 [Docker Compose](https://docs.docker.com/compose/install/)（可选，但推荐）
- Linux系统需要开启X11转发

#### 使用Docker部署

1. **克隆或下载项目代码**

2. **构建并启动Docker容器**

   使用docker-compose（推荐）:
   ```bash
   docker-compose up -d
   ```

   或者使用Docker命令:
   ```bash
   # 构建Docker镜像
   docker build -t localsend-app .
   
   # 运行容器
   docker run -d --name localsend-app \
     --network host \
     -v /tmp/.X11-unix:/tmp/.X11-unix \
     -v $HOME/Downloads:/root/Downloads \
     -e DISPLAY=$DISPLAY \
     -e QT_X11_NO_MITSHM=1 \
     --cap-add NET_ADMIN \
     --cap-add NET_BROADCAST \
     localsend-app
   ```

#### 针对不同操作系统的Docker配置

##### Linux系统

1. 允许Docker访问X11显示服务器：
   ```bash
   xhost +local:docker
   ```

2. 正常启动容器：
   ```bash
   docker-compose up -d
   ```

##### macOS系统

1. 安装XQuartz：
   ```bash
   brew install --cask xquartz
   ```

2. 启动XQuartz并在偏好设置中允许网络连接

3. 获取IP地址：
   ```bash
   IP=$(ifconfig en0 | grep inet | awk '$1=="inet" {print $2}')
   ```

4. 设置DISPLAY环境变量：
   ```bash
   DISPLAY=$IP:0
   ```

5. 允许本地连接：
   ```bash
   xhost + $IP
   ```

6. 修改docker-compose.yml：
   ```yaml
   environment:
     - DISPLAY=$IP:0
   ```

##### Windows系统

1. 安装X服务器，如[VcXsrv](https://sourceforge.net/projects/vcxsrv/)

2. 启动VcXsrv（设置"Disable access control"）

3. 获取IP地址：
   ```powershell
   $IP = (Get-NetIPAddress | Where-Object {$_.AddressFamily -eq "IPv4" -and $_.IPAddress -notlike "127.*"}).IPAddress
   ```

4. 修改docker-compose.yml：
   ```yaml
   environment:
     - DISPLAY=$IP:0.0
   ```

## 使用说明

1. **接收文件**：
   - 选择"接收"选项卡
   - 确保切换按钮设置为"开"
   - 您的设备将在局域网内可被其他SendNow用户发现
   - 当有人向您发送文件时，会自动接收并显示进度

2. **发送文件**：
   - 选择"发送"选项卡
   - 通过拖放或选择文件按钮添加文件
   - 等待应用自动发现局域网内的其他设备
   - 选择目标设备
   - 点击"发送文件"按钮开始传输

3. **设置**：
   - 选择"设置"选项卡
   - 可以配置默认的文件保存路径

## 网络要求

- 发送和接收设备必须位于同一局域网内
- 端口 45678 (设备发现) 和 45679 (文件传输) 必须未被占用
- 局域网必须允许UDP广播（用于设备发现）

## 项目结构

```
├── localsend_app.py       # 应用主入口
├── localsend_ui_design.py # UI设计实现
├── network_discovery.py   # 网络设备发现模块
├── file_transfer.py       # 文件传输模块
├── icons/                 # 图标文件夹
│   ├── receive.svg        # 接收图标 
│   ├── send.svg           # 发送图标
│   └── settings.svg       # 设置图标
├── requirements.txt       # 项目依赖
├── Dockerfile             # Docker构建文件
├── docker-compose.yml     # Docker Compose配置
└── README.md              # 项目说明
```

## 技术细节

- **设备发现**：基于UDP广播实现局域网内设备自动发现
- **文件传输**：使用TCP协议确保可靠的文件传输
- **多线程处理**：后台线程处理网络通信，确保UI流畅响应
- **文件验证**：使用MD5哈希检查确保文件传输完整性

## 预览

应用使用现代深色主题，提供简洁的用户界面，实现快速、安全的文件传输功能。 
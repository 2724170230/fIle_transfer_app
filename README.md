# SendNow 文件传输工具

基于Python-Qt的局域网文件传输工具

## 功能特点

- 简洁现代的深色UI界面
- 局域网内自动发现设备
- 支持接收和发送文件
- 拖放文件上传功能
- 文件传输进度显示
- 可自定义保存路径

## 安装与运行指南

### 环境要求

- Python 3.6+
- PyQt5
- netifaces

### Windows安装步骤

1. **安装Python**
   - 从[Python官网](https://www.python.org/downloads/windows/)下载并安装Python 3.6或更高版本
   - 安装时勾选"Add Python to PATH"选项

2. **安装C++开发工具**
   - 某些依赖库需要C++编译环境，请下载安装[Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
   - 安装时选择"Desktop development with C++"工作负载

3. **创建虚拟环境**
   ```cmd
   # 在项目目录中打开命令提示符
   python -m venv .venv
   
   # 激活虚拟环境
   .venv\Scripts\activate
   ```

4. **安装依赖**
   ```cmd
   pip install -r requirements.txt
   ```

5. **运行应用**
   ```cmd
   python sendnow_app.py
   ```

### macOS安装步骤

1. **安装Python**
   - 从[Python官网](https://www.python.org/downloads/mac-osx/)下载并安装Python 3.6或更高版本
   - 或使用Homebrew安装: `brew install python`

2. **创建虚拟环境**
   ```bash
   # 在项目目录中打开终端
   python3 -m venv .venv
   
   # 激活虚拟环境
   source .venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **运行应用**
   ```bash
   python3 sendnow_app.py
   ```

### Linux安装步骤

1. **安装Python和依赖**
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv python3-dev
   ```

2. **创建虚拟环境**
   ```bash
   # 在项目目录中打开终端
   python3 -m venv .venv
   
   # 激活虚拟环境
   source .venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **运行应用**
   ```bash
   python3 sendnow_app.py
   ```

## 常见问题解决

1. **Windows: "Microsoft Visual C++ 14.0 is required"错误**
   - 确保已安装Microsoft C++ Build Tools

2. **macOS: "Could not find a version that satisfies the requirement PyQt5"错误**
   - 尝试使用以下命令：`pip install PyQt5 --config-settings --confirm-license= --verbose`

3. **权限错误**
   - Windows: 以管理员身份运行命令提示符
   - macOS/Linux: 使用`sudo`或检查文件夹权限

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
├── sendnow_app.py         # 应用主入口
├── sendnow_ui_design.py   # UI设计实现
├── network_discovery.py   # 网络设备发现模块
├── file_transfer.py       # 文件传输模块
├── test_modules.py        # 测试模块
├── udp_broadcast_test.py  # UDP广播测试
├── demo.py                # 演示脚本
├── icons/                 # 图标文件夹
│   ├── receive.svg        # 接收图标 
│   ├── send.svg           # 发送图标
│   ├── settings.svg       # 设置图标
│   ├── history.svg        # 历史记录图标
│   ├── trash.svg          # 删除图标
│   └── sendnow_logo.svg   # 应用图标
├── transfer/              # 传输文件夹
├── requirements.txt       # 项目依赖
└── README.md              # 项目说明
```

## 技术细节

- **设备发现**：基于UDP广播实现局域网内设备自动发现
- **文件传输**：使用TCP协议确保可靠的文件传输
- **多线程处理**：后台线程处理网络通信，确保UI流畅响应
- **文件验证**：使用MD5哈希检查确保文件传输完整性

## 预览
应用使用现代深色主题，提供简洁的用户界面，实现快速、安全的文件传输功能。 
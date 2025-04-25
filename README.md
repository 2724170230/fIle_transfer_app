# SendNow 文件传输工具

基于Python-Qt的局域网文件传输工具，界面风格参考LocalSend.org。

## 功能特点

- 简洁现代的深色UI界面
- 支持通过UDP广播的设备自动发现
- 支持接收和发送文件
- 拖放文件上传功能
- 文件传输进度显示
- 传输控制（暂停、恢复、取消）
- 文件完整性校验
- 可自定义保存路径

## 技术架构

- **网络通信模块**：实现设备发现和基础网络通信
- **传输协议**：自定义应用层协议，包含消息类型、头信息和负载
- **文件传输**：支持大文件分块传输
- **多线程架构**：采用生产者-消费者模式实现文件传输队列

## 安装与运行

### 环境要求

- Python 3.6+
- PyQt5

### 安装依赖

```bash
# 创建虚拟环境（可选）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows

# 安装依赖
pip install PyQt5
```

### 运行应用

```bash
python main.py
```

## 使用说明

1. **接收文件**：选择"接收"选项卡，程序会自动搜索局域网内的其他设备。当有传输请求时，会弹出确认对话框。
2. **发送文件**：选择"发送"选项卡，通过拖放或选择文件按钮添加文件，选择接收设备，然后点击发送按钮。
3. **设置**：选择"设置"选项卡，可以配置默认的文件保存路径。

## 项目结构

```
├── main.py                 # 程序入口
├── localsend_ui_design.py  # UI设计
├── ui_extensions.py        # UI功能扩展
├── network.py              # 网络通信模块
├── transfer.py             # 文件传输基础类
├── transfer_impl.py        # 文件传输实现
├── app_controller.py       # 应用控制器
├── icons/                  # 图标文件夹
│   ├── app_icon.svg        # 应用图标
│   ├── receive.svg         # 接收图标
│   ├── send.svg            # 发送图标
│   └── settings.svg        # 设置图标
└── README.md               # 项目说明
```

## 协议设计

SendNow使用自定义应用层协议进行通信，主要包含以下消息类型：

- **DISCOVER**：设备发现广播
- **DISCOVER_RESPONSE**：设备发现响应
- **TRANSFER_REQUEST**：传输请求
- **TRANSFER_ACCEPT**：接受传输
- **TRANSFER_REJECT**：拒绝传输
- **FILE_INFO**：文件信息
- **DATA**：数据包
- **ACK**：确认包
- **COMPLETE**：传输完成
- **ERROR**：错误信息
- **PAUSE**：暂停传输
- **RESUME**：继续传输
- **CANCEL**：取消传输

## 网络架构

- 使用UDP广播进行设备发现（端口：45678）
- 使用TCP连接进行文件传输（端口：45679）
- 支持断点续传和传输控制

## 安全性

- 文件传输需经过用户确认
- 使用MD5哈希校验文件完整性

## 许可证

MIT 
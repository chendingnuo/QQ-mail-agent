# QQ邮箱智能邮件处理系统

AI 驱动的 QQ邮箱全自动邮件处理系统。
读取未读邮件 → AI 生成回复 → 写入草稿箱 → 可视化界面确认发送。

## 项目结构

```
qqmail_reader/
├── config.py                # [配置] 邮箱账号、授权码、AI 参数
├── qqmail_imap.py           # IMAP 读写：收件箱读取 / 草稿箱写入删除
├── qqmail_smtp.py           # SMTP 发送邮件
├── ai_generator.py          # AI 回复生成（DeepSeek/OpenAI + 模板回退）
├── auto_processor.py        # 自动处理流程：读邮件→AI→写草稿
├── api_server.py            # HTTP API 服务器（零依赖）
├── main.py                  # 启动入口
├── static/
│   └── index.html           # 前端管理界面（Vue 3 + Tailwind）
├── templates.json           # 回退模板库
└── requirements.txt
```

## 快速开始

### 1. 获取 QQ邮箱授权码

1. 登录 [mail.qq.com](https://mail.qq.com/)
2. 设置 → 账户 → POP3/IMAP/SMTP服务
3. 开启 IMAP/SMTP，生成 16位授权码

### 2. 配置

编辑 `config.py`：

| 配置项 | 说明 |
|--------|------|
| `EMAIL_ACCOUNT` | QQ邮箱地址 |
| `EMAIL_PASSWORD` | 授权码（非QQ密码） |
| `AI_API_KEY` | DeepSeek / OpenAI API Key（留空则用本地模板） |

### 3. 启动

```bash
cd qqmail_reader
python main.py
```

打开浏览器访问 **http://localhost:8000**

### 4. 前端界面功能

| 区域 | 功能 |
|------|------|
| 左侧面板 | 统计卡片、导航菜单、一键处理按钮、AI配置 |
| 中央面板 | 收件箱/草稿箱列表、搜索过滤、邮件详情、发送/重新生成/删除 |
| 右侧面板 | AI助手聊天、快捷指令 |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/stats` | 邮箱统计（未读数、草稿数） |
| GET | `/api/emails` | 收件箱邮件列表 |
| GET | `/api/drafts` | AI草稿列表 |
| GET | `/api/drafts/{id}` | 单封草稿详情 |
| POST | `/api/send-draft` | 发送草稿（SMTP）→ 删除原草稿 |
| POST | `/api/regenerate` | AI重新生成回复 |
| POST | `/api/process-new` | 一键处理：读未读→AI→写草稿 |
| DELETE | `/api/drafts/{id}` | 删除草稿 |

## 核心避坑机制

- **X-AI-Generated 标记**：在邮件头注入自定义标签，前端只显示 AI 生成的草稿
- **UTF-8 显式编码**：Subject/Body 严格指定 utf-8，防止 QQ邮箱乱码
- **SMTP 发送 + IMAP 清理**：发送成功后自动删除草稿箱中的原草稿
- **AI/模板双保险**：AI 不可用时自动回退到本地关键词模板匹配

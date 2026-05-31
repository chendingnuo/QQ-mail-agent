# QQ邮箱邮件读取 & 草稿写入草稿箱

读取QQ邮箱收件箱邮件，根据内容自动生成回复草稿并写入QQ邮箱草稿箱（Drafts）。

打开 [mail.qq.com](https://mail.qq.com/) 即可在草稿箱中看到回复草稿，点击即可编辑发送。

## 项目结构

```
qqmail_reader/
├── config.py              # 配置文件
├── qqmail.py              # IMAP读取 + 草稿写入
├── reply_generator.py     # 模板匹配 + 回复生成
├── templates.json         # 回复模板库
├── main.py                # 主程序入口
├── README.md
└── drafts/                # 本地备份（写入草稿箱失败时的备用）
```

## 快速开始

### 1. 获取授权码

1. 登录 [QQ邮箱](https://mail.qq.com/)
2. **设置 → 账户 → POP3/IMAP/SMTP服务**
3. 开启 **IMAP/SMTP服务**，生成授权码（16位）

### 2. 配置

编辑 `config.py`：

```python
EMAIL_ACCOUNT = '你的QQ号@qq.com'   # QQ邮箱
EMAIL_PASSWORD = '你的16位授权码'     # 不是QQ密码！
```

### 3. 运行

```bash
python main.py
```

### 4. 查看草稿

打开 [mail.qq.com](https://mail.qq.com/) → 左侧 **草稿箱**，即可看到生成的草稿。点击即可编辑和发送。

## 工作流程

1. 连接QQ邮箱 IMAP
2. 读取收件箱最近N天的邮件
3. 根据邮件内容关键词匹配回复模板
4. 构造MIME回复邮件（含 In-Reply-To 引用关系）
5. 通过 IMAP APPEND 写入草稿箱
6. 写入失败时自动保存到本地备份

## 自定义模板

编辑 `templates.json` 可增删改模板。每个模板包含：

- `keywords` — 触发关键词列表
- `subject` — 回复主题模板
- `body` — 回复正文模板（支持占位符）

可用占位符：`{subject}` `{keyword_context}` `{signature}` `{details}` `{date_option_*}`

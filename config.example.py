# QQ邮箱配置
# 【重要】密码不是QQ密码，而是QQ邮箱的授权码！
# 获取方式：登录QQ邮箱 -> 设置 -> 账户 -> POP3/IMAP/SMTP服务 -> 生成授权码

# IMAP配置
IMAP_SERVER = 'imap.qq.com'
IMAP_PORT = 993
IMAP_SSL = True

# 邮箱账号
EMAIL_ACCOUNT = '你的邮箱号@qq.com'
EMAIL_PASSWORD = '你的授权码'

# 读取设置
INBOX_FOLDER = 'INBOX'
MAX_EMAILS = 10
FETCH_DAYS = 7

# 草稿箱设置
# QQ邮箱草稿箱的IMAP文件夹名称（通常为 Drafts）
DRAFTS_FOLDER = 'Drafts'

# 回复设置
SENDER_NAME = '你的名字'

# 本地草稿目录（当写入草稿箱失败时的备份）
LOCAL_DRAFTS_DIR = './drafts'

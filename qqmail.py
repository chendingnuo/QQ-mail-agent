"""
QQ邮箱邮件读取与草稿写入模块
使用IMAP协议连接QQ邮箱，读取收件箱邮件并写入草稿箱
"""

import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import time

from config import (IMAP_SERVER, IMAP_PORT, IMAP_SSL,
                    EMAIL_ACCOUNT, EMAIL_PASSWORD,
                    INBOX_FOLDER, DRAFTS_FOLDER,
                    MAX_EMAILS, FETCH_DAYS, SENDER_NAME)


def decode_mime_header(header_value):
    """解码MIME编码的邮件头"""
    if header_value is None:
        return ''
    decoded_parts = decode_header(header_value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                charset = charset or 'utf-8'
                result.append(part.decode(charset, errors='replace'))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode('utf-8', errors='replace'))
        else:
            result.append(str(part))
    return ''.join(result)


def decode_email_body(msg):
    """递归解码邮件正文"""
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get('Content-Disposition', ''))
            if 'attachment' in content_disposition:
                continue
            if content_type == 'text/plain':
                charset = part.get_content_charset() or 'utf-8'
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode(charset, errors='replace')
                except Exception:
                    pass
            elif content_type == 'text/html' and not body:
                charset = part.get_content_charset() or 'utf-8'
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode(charset, errors='replace')
                except Exception:
                    pass
    else:
        charset = msg.get_content_charset() or 'utf-8'
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(charset, errors='replace')
        except Exception:
            pass
    return body


def connect_qqmail():
    """连接QQ邮箱IMAP服务器"""
    print(f'[*] 正在连接 {IMAP_SERVER}:{IMAP_PORT} ...')
    try:
        if IMAP_SSL:
            conn = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        else:
            conn = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT)
        conn.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        print(f'[+] 登录成功: {EMAIL_ACCOUNT}')
        return conn
    except imaplib.IMAP4.error as e:
        print(f'[-] 登录失败: {e}')
        print('   提示: 密码应使用QQ邮箱授权码，而非QQ密码')
        return None
    except Exception as e:
        print(f'[-] 连接失败: {e}')
        return None


def list_folders(conn):
    """列出邮箱中的所有文件夹"""
    try:
        status, folders = conn.list()
        if status == 'OK':
            print('\n[*] 邮箱文件夹列表:')
            for f in folders:
                decoded = f.decode('utf-8', errors='replace')
                print(f'  {decoded}')
            print()
            return folders
    except Exception:
        pass
    return []


def fetch_recent_emails(max_emails=MAX_EMAILS, days=FETCH_DAYS):
    """读取最近的邮件"""
    conn = connect_qqmail()
    if not conn:
        return []

    emails = []
    try:
        # 列出文件夹（调试用）
        list_folders(conn)

        # 选择收件箱（只读模式）
        status, _ = conn.select(INBOX_FOLDER, readonly=True)
        if status != 'OK':
            print(f'[-] 无法打开文件夹: {INBOX_FOLDER}')
            conn.logout()
            return []

        since_date = (datetime.now() - timedelta(days=days)).strftime('%d-%b-%Y')
        search_criteria = f'(SINCE {since_date})'
        print(f'[*] 搜索 {days} 天内的邮件 (since: {since_date}) ...')
        status, message_ids = conn.search(None, search_criteria)

        if status != 'OK' or not message_ids[0]:
            print('[-] 未找到符合条件的邮件')
            conn.logout()
            return []

        ids = message_ids[0].split()
        fetch_ids = ids[-max_emails:]
        print(f'[+] 共 {len(ids)} 封匹配，获取最近 {len(fetch_ids)} 封')

        for mid in reversed(fetch_ids):
            status, msg_data = conn.fetch(mid, '(RFC822)')
            if status != 'OK':
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = decode_mime_header(msg['Subject'])
            sender = decode_mime_header(msg['From'])
            date_str = msg.get('Date', '')
            msg_id = msg.get('Message-ID', '')
            body = decode_email_body(msg)

            email_info = {
                'id': mid.decode(),
                'subject': subject or '(无主题)',
                'from': sender,
                'from_email': email.utils.parseaddr(sender)[1],
                'date': date_str,
                'message_id': msg_id.strip() if msg_id else '',
                'body': body[:5000],
                'body_preview': body[:200].replace('\n', ' ').replace('\r', ''),
            }
            emails.append(email_info)

        print(f'[+] 成功读取 {len(emails)} 封邮件\n')

    except Exception as e:
        print(f'[-] 读取邮件出错: {e}')
    finally:
        conn.logout()
        print('[*] IMAP连接已关闭')

    return emails


def build_reply_message(reply_subject, reply_body, original_email):
    """构造回复邮件的MIME消息（用于写入草稿箱）"""
    from email.mime.text import MIMEText
    import email.utils

    from_addr = EMAIL_ACCOUNT
    to_addr = original_email['from_email'] or original_email['from']

    # 如果没有完整的 From 地址，尝试从字符串中提取
    if not to_addr or '@' not in to_addr:
        parsed = email.utils.parseaddr(original_email['from'])
        to_addr = parsed[1] if parsed[1] else original_email['from']

    sender_display = SENDER_NAME if SENDER_NAME else EMAIL_ACCOUNT

    # 构建纯文本邮件
    msg = MIMEText(reply_body, 'plain', 'utf-8')
    msg['From'] = email.utils.formataddr((sender_display, from_addr))
    msg['To'] = to_addr
    msg['Subject'] = reply_subject
    msg['Date'] = email.utils.formatdate(localtime=True)

    # 生成唯一的 Message-ID
    msg_id = email.utils.make_msgid(domain='qq.com')
    msg['Message-ID'] = msg_id

    # 添加引用关系（使回复与原邮件在同一会话中）
    if original_email['message_id']:
        msg['References'] = original_email['message_id']
        msg['In-Reply-To'] = original_email['message_id']

    return msg


def write_draft_to_qqmail(conn, reply_message):
    """将回复草稿写入QQ邮箱草稿箱"""
    try:
        # 将MIME消息序列化为字节
        msg_bytes = reply_message.as_bytes()

        # 附加到草稿箱，标记为 \Draft \Seen
        # 使用 IMAP APPEND 命令
        status, result = conn.append(
            DRAFTS_FOLDER,
            '\\Draft \\Seen',
            imaplib.Time2Internaldate(time.time()),
            msg_bytes
        )

        if status == 'OK':
            return True, ''
        else:
            return False, str(result)

    except Exception as e:
        return False, str(e)

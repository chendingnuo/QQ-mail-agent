"""
QQ邮箱 IMAP 操作模块
连接 imap.qq.com，读取邮件、写入/读取/删除草稿
"""
import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, parseaddr, formataddr
from datetime import datetime, timedelta
import time
import re
from config import (
    IMAP_SERVER, IMAP_PORT, IMAP_SSL,
    EMAIL_ACCOUNT, EMAIL_PASSWORD,
    INBOX_FOLDER, DRAFTS_FOLDER,
    MAX_EMAILS_PER_CYCLE, FETCH_DAYS, SENDER_NAME
)

# ─── 工具函数 ─────────────────────────────────────────


def _decode(header_value):
    """解码MIME编码的邮件头"""
    if not header_value:
        return ''
    parts = decode_header(header_value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or 'utf-8', errors='replace'))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode('utf-8', errors='replace'))
        else:
            result.append(str(part))
    return ''.join(result)


def _decode_body(msg):
    """递归解码邮件正文，优先纯文本"""
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if 'attachment' in str(part.get('Content-Disposition', '')):
                continue
            if ct == 'text/plain':
                charset = part.get_content_charset() or 'utf-8'
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode(charset, errors='replace')
                except Exception:
                    pass
            elif ct == 'text/html' and not body:
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


def _extract_email_addr(raw_from):
    """从 '姓名 <a@b.com>' 中提取纯邮箱地址"""
    name, addr = parseaddr(raw_from)
    return addr if addr else raw_from


def _msg_to_dict(msg, msg_id=None):
    """将 email.message 解析为统一字典"""
    subject = _decode(msg['Subject']) or '(无主题)'
    sender = _decode(msg['From'])
    date_str = msg.get('Date', '')
    msg_id_hdr = (msg.get('Message-ID') or '').strip()
    body = _decode_body(msg)

    # 检查自定义头
    is_ai = msg.get('X-AI-Generated', 'false').lower() == 'true'

    return {
        'id': msg_id or msg_id_hdr,
        'subject': subject,
        'from': sender,
        'from_email': _extract_email_addr(sender),
        'date': date_str,
        'message_id': msg_id_hdr,
        'body': body[:8000],
        'body_preview': body[:200].replace('\n', ' ').replace('\r', ''),
        'is_ai_generated': is_ai,
    }

# ─── 连接管理 ─────────────────────────────────────────


def connect():
    """连接 QQ邮箱 IMAP 服务器，返回连接对象"""
    try:
        if IMAP_SSL:
            conn = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=30)
        else:
            conn = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT)
        conn.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        return conn
    except imaplib.IMAP4.error as e:
        raise ConnectionError(f'IMAP登录失败: {e}') from e
    except Exception as e:
        raise ConnectionError(f'IMAP连接失败: {e}') from e


def list_folders(conn):
    """列出所有文件夹（调试用）"""
    status, folders = conn.list()
    if status == 'OK':
        result = []
        for f in folders:
            decoded = f.decode('utf-8', errors='replace')
            result.append(decoded)
        return result
    return []

# ─── 读取邮件 ─────────────────────────────────────────


def fetch_unseen_emails(max_emails=MAX_EMAILS_PER_CYCLE, days=FETCH_DAYS):
    """读取收件箱中未读邮件，返回邮件字典列表"""
    conn = connect()
    emails = []
    try:
        conn.select(INBOX_FOLDER, readonly=True)
        # 同时按"未读"和"日期范围"搜索
        since = (datetime.now() - timedelta(days=days)).strftime('%d-%b-%Y')
        search_criteria = f'(UNSEEN SINCE {since})'
        status, ids = conn.search(None, search_criteria)

        if status != 'OK' or not ids[0]:
            return []

        all_ids = ids[0].split()
        fetch_ids = all_ids[-max_emails:]  # 只取最新的 N 封

        for mid in reversed(fetch_ids):
            ok, data = conn.fetch(mid, '(RFC822)')
            if ok != 'OK':
                continue
            msg = email.message_from_bytes(data[0][1])
            info = _msg_to_dict(msg, msg_id=mid.decode())
            info['imap_id'] = mid.decode()
            emails.append(info)

    finally:
        try:
            conn.close()
            conn.logout()
        except Exception:
            pass
    return emails


def fetch_all_inbox_emails(max_emails=30, days=FETCH_DAYS):
    """读取收件箱所有邮件（不限制是否已读）"""
    conn = connect()
    emails = []
    try:
        conn.select(INBOX_FOLDER, readonly=True)
        since = (datetime.now() - timedelta(days=days)).strftime('%d-%b-%Y')
        status, ids = conn.search(None, f'(SINCE {since})')
        if status != 'OK' or not ids[0]:
            return []
        all_ids = ids[0].split()
        fetch_ids = all_ids[-max_emails:]

        for mid in reversed(fetch_ids):
            ok, data = conn.fetch(mid, '(RFC822)')
            if ok != 'OK':
                continue
            msg = email.message_from_bytes(data[0][1])
            info = _msg_to_dict(msg, msg_id=mid.decode())
            info['imap_id'] = mid.decode()

            # 判断是否已读
            flags = conn.fetch(mid, '(FLAGS)')
            if flags[0] == 'OK':
                flag_str = flags[1][0].decode('utf-8', errors='replace')
                info['is_read'] = '\\Seen' in flag_str
            else:
                info['is_read'] = False

            emails.append(info)
    finally:
        try:
            conn.close()
            conn.logout()
        except Exception:
            pass
    return emails

# ─── 草稿操作 ─────────────────────────────────────────


def build_reply_message(reply_subject, reply_body, original_email, add_ai_tag=True):
    """构造一封回复邮件（MIME格式），用于写入草稿箱"""
    from_addr = EMAIL_ACCOUNT
    to_addr = original_email.get('from_email') or _extract_email_addr(
        original_email.get('from', ''))

    display_name = SENDER_NAME if SENDER_NAME else EMAIL_ACCOUNT
    msg = MIMEText(reply_body, 'plain', 'utf-8')
    msg['From'] = formataddr((display_name, from_addr))
    msg['To'] = to_addr
    msg['Subject'] = reply_subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='qq.com')

    if original_email.get('message_id'):
        msg['References'] = original_email['message_id']
        msg['In-Reply-To'] = original_email['message_id']

    # 【关键！】添加自定义标记，用于前端识别哪些草稿是AI生成的
    if add_ai_tag:
        msg['X-AI-Generated'] = 'true'
        msg['X-AI-Generated-At'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return msg


def append_draft(conn, reply_message):
    """通过 IMAP APPEND 将回复草稿写入 QQ邮箱草稿箱"""
    msg_bytes = reply_message.as_bytes()
    status, result = conn.append(
        DRAFTS_FOLDER,
        '\\Draft \\Seen',
        imaplib.Time2Internaldate(time.time()),
        msg_bytes
    )
    return status == 'OK'


def list_drafts(conn, filter_ai_only=True):
    """读取草稿箱中的所有草稿，返回邮件字典列表"""
    drafts = []
    try:
        conn.select(DRAFTS_FOLDER, readonly=True)
        status, ids = conn.search(None, 'ALL')
        if status != 'OK' or not ids[0]:
            return drafts

        for mid in ids[0].split():
            ok, data = conn.fetch(mid, '(RFC822)')
            if ok != 'OK':
                continue
            msg = email.message_from_bytes(data[0][1])
            info = _msg_to_dict(msg, msg_id=mid.decode())
            info['imap_id'] = mid.decode()

            # 如果要求只筛选AI生成的
            if filter_ai_only and not info['is_ai_generated']:
                continue

            # 解析 To 地址
            to_val = msg.get('To', '')
            info['to'] = _decode(to_val)
            info['to_email'] = _extract_email_addr(to_val)

            drafts.append(info)

    finally:
        try:
            conn.close()
            conn.logout()
        except Exception:
            pass
    return drafts


def delete_draft(conn, imap_id):
    """删除草稿箱中的某封草稿（发送成功后清理）"""
    try:
        conn.select(DRAFTS_FOLDER)
        conn.store(imap_id, '+FLAGS', '\\Deleted')
        conn.expunge()
        return True
    except Exception:
        return False


def mark_as_read(conn, imap_id):
    """将某封邮件标记为已读"""
    try:
        conn.select(INBOX_FOLDER)
        conn.store(imap_id, '+FLAGS', '\\Seen')
        return True
    except Exception:
        return False

# ─── 统计 ─────────────────────────────────────────────


def get_stats():
    """获取收件箱/草稿箱统计信息"""
    stats = {
        'unseen_count': 0,
        'inbox_total': 0,
        'drafts_count': 0,
        'ai_drafts_count': 0,
        'today_received': 0,
    }
    conn = connect()
    try:
        # 收件箱统计
        conn.select(INBOX_FOLDER, readonly=True)
        today = datetime.now().strftime('%d-%b-%Y')

        status, ids = conn.search(None, 'UNSEEN')
        stats['unseen_count'] = len(ids[0].split()) if status == 'OK' and ids[0] else 0

        status, ids = conn.search(None, 'ALL')
        stats['inbox_total'] = len(ids[0].split()) if status == 'OK' and ids[0] else 0

        status, ids = conn.search(None, f'(SINCE {today})')
        stats['today_received'] = len(ids[0].split()) if status == 'OK' and ids[0] else 0

        # 草稿箱统计
        conn.select(DRAFTS_FOLDER, readonly=True)
        status, ids = conn.search(None, 'ALL')
        stats['drafts_count'] = len(ids[0].split()) if status == 'OK' and ids[0] else 0

        # 统计AI生成的草稿
        ai_count = 0
        if status == 'OK' and ids[0]:
            for mid in ids[0].split():
                ok, data = conn.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (X-AI-GENERATED)])')
                if ok == 'OK':
                    hdr = data[0][1].decode('utf-8', errors='replace')
                    if 'X-AI-Generated: true' in hdr:
                        ai_count += 1
        stats['ai_drafts_count'] = ai_count

    finally:
        try:
            conn.close()
            conn.logout()
        except Exception:
            pass
    return stats

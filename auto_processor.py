"""
自动处理模块
读取未读邮件 → AI生成回复 → 写入草稿箱
"""
from datetime import datetime

from qqmail_imap import (
    connect, fetch_unseen_emails, build_reply_message,
    append_draft, mark_as_read
)
from ai_generator import generate_reply


def process_new_emails():
    """
    一次完整的自动处理流程：
    1. 读取未读邮件
    2. AI 生成回复
    3. 写入草稿箱
    4. 标记原邮件为已读

    返回处理结果字典
    """
    result = {
        'started_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'emails_found': 0,
        'drafts_created': 0,
        'errors': [],
        'details': [],
        'finished_at': None,
    }

    # 1. 读取未读邮件
    print('[Auto] 读取未读邮件...')
    emails = fetch_unseen_emails()

    if not emails:
        print('[Auto] 没有未读邮件需要处理')
        result['finished_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return result

    result['emails_found'] = len(emails)
    print(f'[Auto] 发现 {len(emails)} 封未读邮件')

    # 2. 对每封邮件生成回复并写入草稿箱
    conn = connect()

    for mail in emails:
        try:
            subject = mail['subject']
            body = mail['body']
            sender = mail['from']

            print(f'[Auto] 处理: {subject[:40]}...')

            # AI 生成回复
            reply_subject, reply_body, used_fallback, tmpl = generate_reply(
                subject, body, sender
            )

            # 构造 MIME 消息（带 X-AI-Generated 标记）
            msg = build_reply_message(reply_subject, reply_body, mail, add_ai_tag=True)

            # 写入草稿箱
            ok = append_draft(conn, msg)

            if ok:
                # 标记原邮件为已读
                try:
                    mark_as_read(conn, mail.get('imap_id', mail['id']))
                except Exception:
                    pass

                result['drafts_created'] += 1
                detail = {
                    'subject': subject,
                    'from': sender,
                    'reply_preview': reply_body[:100],
                    'ai_generated': not used_fallback,
                    'template': tmpl,
                    'status': 'ok',
                }
            else:
                detail = {
                    'subject': subject,
                    'from': sender,
                    'status': 'failed',
                    'error': '写入草稿箱失败',
                }
                result['errors'].append(f'写入草稿失败: {subject[:30]}')

            result['details'].append(detail)

        except Exception as e:
            result['errors'].append(f'处理邮件出错: {mail.get("subject", "?")[:30]}: {e}')

    # 关闭连接
    try:
        conn.logout()
    except Exception:
        pass

    result['finished_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[Auto] 完成: 创建 {result["drafts_created"]} 封草稿, {len(result["errors"])} 个错误')
    return result

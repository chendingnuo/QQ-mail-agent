"""
回复草稿生成器
匹配邮件模板，构造回复MIME消息，写入QQ邮箱草稿箱
"""

import json
import os
from datetime import datetime

from config import SENDER_NAME, LOCAL_DRAFTS_DIR


def load_templates(template_file='templates.json'):
    """加载回复模板"""
    template_path = os.path.join(os.path.dirname(__file__), template_file)
    with open(template_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def match_template(email_body, email_subject, templates):
    """根据邮件内容匹配最合适的模板"""
    text = (email_subject + ' ' + email_body).lower()
    matched = []
    for name, tmpl in templates.items():
        if not tmpl['keywords']:
            continue
        score = sum(1 for kw in tmpl['keywords'] if kw in text)
        if score > 0:
            matched.append((score, name, tmpl))
    if matched:
        matched.sort(key=lambda x: x[0], reverse=True)
        return matched[0][1], matched[0][2]
    return 'general', templates['general']


def extract_context(email_body, email_subject, max_chars=50):
    """从邮件中提取关键词上下文"""
    body_clean = email_body.strip().replace('\n', ' ').replace('\r', '')
    context = body_clean[:max_chars].strip()
    if not context:
        context = email_subject
    return context


def generate_reply(email_info, templates):
    """为单封邮件生成回复主题和正文"""
    subject = email_info['subject']
    body = email_info['body']

    template_name, template = match_template(body, subject, templates)
    context = extract_context(body, subject)
    today = datetime.now().strftime('%Y年%m月%d日')
    sender = SENDER_NAME if SENDER_NAME else email_info.get('from_email', '')

    reply_body = template['body'].format(
        subject=subject,
        keyword_context=context,
        signature=f'{sender}\n{today}',
        details='【请在此处填写具体内容】',
        date_option_1='(请填写日期1)',
        date_option_2='(请填写日期2)',
        date_option_3='(请填写日期3)',
    )
    reply_subject = template['subject'].format(subject=subject)

    return reply_subject, reply_body.strip(), template_name


def save_local_backup(reply_subject, reply_body, original_email, template_name):
    """保存草稿到本地文件（备用）"""
    draft_dir = os.path.join(os.path.dirname(__file__), LOCAL_DRAFTS_DIR)
    os.makedirs(draft_dir, exist_ok=True)

    safe_subject = original_email['subject']
    for ch in r'\/:*?"<>|':
        safe_subject = safe_subject.replace(ch, '_')
    safe_subject = safe_subject[:40]

    timestamp = datetime.now().strftime('%H%M%S')
    filename = f'{timestamp}_{safe_subject}.txt'
    filepath = os.path.join(draft_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('=' * 60 + '\n')
        f.write('QQ邮箱回复草稿 (本地备份)\n')
        f.write('=' * 60 + '\n\n')
        f.write(f'【原始邮件】\n')
        f.write(f'发件人: {original_email["from"]}\n')
        f.write(f'主题:   {original_email["subject"]}\n')
        f.write(f'日期:   {original_email["date"]}\n\n')
        f.write('-' * 40 + '\n')
        f.write(f'【回复草稿】(模板: {template_name})\n')
        f.write(f'回复主题: {reply_subject}\n\n')
        f.write(f'{reply_body}\n\n')
        f.write('-' * 40 + '\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')

    return filepath

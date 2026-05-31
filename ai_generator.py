"""
AI 回复生成模块
对接 DeepSeek / OpenAI 兼容 API，根据邮件内容智能生成回复
当 AI 不可用时自动回退到本地模板匹配
"""
import json
import os
import requests
from datetime import datetime
from config import AI_API_KEY, AI_API_BASE_URL, AI_MODEL, AI_SYSTEM_PROMPT

_FALLBACK_TEMPLATES = None


def _load_fallback_templates():
    """加载本地模板（当AI不可用时的回退方案）"""
    global _FALLBACK_TEMPLATES
    if _FALLBACK_TEMPLATES is not None:
        return _FALLBACK_TEMPLATES
    tmpl_path = os.path.join(os.path.dirname(__file__), 'templates.json')
    try:
        with open(tmpl_path, 'r', encoding='utf-8') as f:
            _FALLBACK_TEMPLATES = json.load(f)
    except Exception:
        _FALLBACK_TEMPLATES = {}
    return _FALLBACK_TEMPLATES


def _fallback_reply(subject, body, sender):
    """本地模板规则生成回复（AI不可用时的回退）"""
    templates = _load_fallback_templates()
    text = (subject + ' ' + body).lower()

    best_name = 'general'
    best_score = 0
    best_tmpl = None

    for name, tmpl in templates.items():
        keywords = tmpl.get('keywords', [])
        if not keywords:
            continue
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_name = name
            best_tmpl = tmpl

    if best_tmpl is None:
        best_tmpl = templates.get('general', {})

    context = body.strip().replace('\n', ' ')[:60]
    today = datetime.now().strftime('%Y年%m月%d日')
    sign = f'{sender or "我"}\n{today}'

    tmpl_body = best_tmpl.get('body', '')
    reply = tmpl_body.format(
        subject=subject,
        keyword_context=context,
        signature=sign,
        details='【请在此处填写具体内容】',
        date_option_1='(日期1)',
        date_option_2='(日期2)',
        date_option_3='(日期3)',
    )
    reply_subject = best_tmpl.get('subject', 'Re: {subject}').format(subject=subject)
    return reply_subject, reply.strip(), best_name


def generate_reply(subject, body, sender=''):
    """
    使用 AI 生成回复，AI不可用时回退到本地模板
    返回: (reply_subject: str, reply_body: str, used_fallback: bool, template_name: str)
    """
    # 无 API Key → 直接模板回退
    if not AI_API_KEY:
        subj, body_text, tmpl = _fallback_reply(subject, body, sender)
        return subj, body_text, True, tmpl

    try:
        headers = {
            'Authorization': f'Bearer {AI_API_KEY}',
            'Content-Type': 'application/json'
        }
        user_content = f'''邮件主题：{subject}
发件人：{sender}
邮件正文：
{body}

请生成回复：'''

        payload = {
            'model': AI_MODEL,
            'messages': [
                {'role': 'system', 'content': AI_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_content}
            ],
            'temperature': 0.7,
            'max_tokens': 1024,
        }

        resp = requests.post(
            f'{AI_API_BASE_URL}/v1/chat/completions',
            headers=headers, json=payload, timeout=60
        )

        if resp.status_code != 200:
            raise Exception(f'API {resp.status_code}: {resp.text[:200]}')

        result = resp.json()
        reply_text = result['choices'][0]['message']['content'].strip()
        return f'Re: {subject}', reply_text, False, 'ai_generated'

    except Exception as e:
        print(f'[AI] API调用失败: {e}，回退到本地模板')
        subj, body_text, tmpl = _fallback_reply(subject, body, sender)
        return subj, body_text, True, tmpl

#!/usr/bin/env python3
"""
QQ邮箱邮件读取与回复草稿生成 - 主程序
读取收件箱邮件，自动生成回复草稿并写入QQ邮箱草稿箱
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qqmail import (connect_qqmail, fetch_recent_emails,
                    build_reply_message, write_draft_to_qqmail)
from reply_generator import (load_templates, generate_reply, save_local_backup)
from config import EMAIL_ACCOUNT, EMAIL_PASSWORD


def print_banner():
    print()
    print('  +---------------------------------------+')
    print('  |   QQ邮箱 读取邮件 + 写入草稿箱         |')
    print('  +---------------------------------------+')
    print()


def check_config():
    if EMAIL_ACCOUNT == 'your_email@qq.com' or EMAIL_PASSWORD == 'your_auth_code':
        print('[!] 请先编辑 config.py 填写你的QQ邮箱和授权码！')
        print()
        print('    步骤:')
        print('    1. 登录 QQ邮箱 (mail.qq.com)')
        print('    2. 设置 -> 账户 -> POP3/IMAP/SMTP服务')
        print('    3. 开启服务并生成授权码')
        print('    4. 将授权码填入 config.py 的 EMAIL_PASSWORD')
        print()
        return False
    return True


def main():
    print_banner()

    if not check_config():
        sys.exit(1)

    # 第一步：读取收件箱邮件
    print('=' * 50)
    print('  [步骤1] 读取收件箱邮件')
    print('=' * 50)
    emails = fetch_recent_emails()

    if not emails:
        print('[-] 没有读取到邮件，退出。')
        sys.exit(1)

    # 打印邮件列表
    for i, mail in enumerate(emails, 1):
        print(f'  [{i:2d}] {mail["from"]}')
        print(f'      主题: {mail["subject"]}')
        print(f'      日期: {mail["date"]}')
        print()

    # 第二步：加载模板，生成回复草稿
    print('=' * 50)
    print('  [步骤2] 生成回复草稿并写入QQ邮箱草稿箱')
    print('=' * 50)

    templates = load_templates()
    reply_info_list = []

    for mail in emails:
        reply_subject, reply_body, template_name = generate_reply(mail, templates)
        reply_info_list.append((mail, reply_subject, reply_body, template_name))

    # 第三步：连接IMAP并将草稿写入草稿箱
    conn = connect_qqmail()
    if not conn:
        print('[-] 无法连接IMAP，尝试保存到本地文件...')
        for mail, reply_subject, reply_body, template_name in reply_info_list:
            path = save_local_backup(reply_subject, reply_body, mail, template_name)
            print(f'  [*] 已保存到本地: {path}')
        sys.exit(1)

    success_count = 0
    fail_count = 0

    for mail, reply_subject, reply_body, template_name in reply_info_list:
        print(f'\n  --- {mail["subject"][:40]} ---')
        print(f'  匹配模板: [{template_name}]')
        print(f'  回复: {reply_subject}')
        print(f'  发送至: {mail["from"][:40]}')

        # 构造MIME回复消息
        reply_msg = build_reply_message(reply_subject, reply_body, mail)

        # 写入草稿箱
        ok, err = write_draft_to_qqmail(conn, reply_msg)
        if ok:
            print(f'  [OK] 已写入草稿箱')
            success_count += 1
        else:
            print(f'  [FAIL] 写入失败: {err}')
            # 写入失败时保存到本地备份
            path = save_local_backup(reply_subject, reply_body, mail, template_name)
            print(f'  [*] 已保存到本地备份: {path}')
            fail_count += 1

    conn.logout()
    print('\n' + '=' * 50)
    print(f'  完成！成功写入草稿箱: {success_count} 封')
    if fail_count:
        print(f'  写入失败(已存本地): {fail_count} 封')
    print(f'  请打开 mail.qq.com 查看草稿箱')
    print('=' * 50)


if __name__ == '__main__':
    main()

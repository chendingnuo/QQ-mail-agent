#!/usr/bin/env python3
"""
QQ邮箱智能邮件处理系统 - 启动入口

用法:
    python main.py              # 启动Web服务 (访问 http://localhost:8000)
    python main.py --manual     # 手动模式：读取邮件 → 生成草稿
    python main.py --process    # 仅执行一次自动处理
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    args = sys.argv[1:]

    if '--manual' in args:
        # 手动模式：读取 + AI生成 + 写草稿
        from auto_processor import process_new_emails
        result = process_new_emails()
        print(f'\n处理结果: {result["drafts_created"]} 封草稿创建, {len(result["errors"])} 个错误')

    elif '--process' in args:
        # 单次自动处理
        from auto_processor import process_new_emails
        from datetime import datetime
        print(f'[{datetime.now().strftime("%H:%M:%S")}] 开始自动处理...')
        result = process_new_emails()
        print(f'[{datetime.now().strftime("%H:%M:%S")}] 完成: {result["drafts_created"]} 封草稿')

    else:
        # 启动 Web 服务（默认）
        print('启动 QQ邮箱智能邮件管理系统...')
        from api_server import run_server
        run_server()

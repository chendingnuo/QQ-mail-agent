#!/usr/bin/env python3
"""
轻量级 HTTP API 服务器（零外部依赖）
提供 RESTful 接口供前端调用
"""
import os
import sys
import json
import time
import threading
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

# 将项目目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import API_HOST, API_PORT

# ─── 延迟导入（加快启动速度，失败时给出明确提示） ────

_imap = None
_smtp_sender = None
_ai = None
_processor = None


def _lazy_import():
    global _imap, _smtp_sender, _ai, _processor
    if _imap is not None:
        return
    try:
        import qqmail_imap
        import qqmail_smtp
        import ai_generator
        import auto_processor
        _imap = qqmail_imap
        _smtp_sender = qqmail_smtp
        _ai = ai_generator
        _processor = auto_processor
    except Exception as e:
        print(f'[API] 模块导入失败: {e}')
        traceback.print_exc()


def json_response(handler, data, status=200):
    """发送 JSON 响应"""
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    byte_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
    handler.send_header('Content-Length', str(len(byte_data)))
    handler.end_headers()
    handler.wfile.write(byte_data)


def read_body(handler):
    """读取请求体并解析 JSON"""
    length = int(handler.headers.get('Content-Length', 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def serve_static(handler, filepath):
    """提供静态文件"""
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        ext = os.path.splitext(filepath)[1]
        content_types = {
            '.html': 'text/html; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.json': 'application/json',
            '.png': 'image/png',
            '.ico': 'image/x-icon',
        }
        handler.send_response(200)
        handler.send_header('Content-Type', content_types.get(ext, 'application/octet-stream'))
        handler.send_header('Content-Length', str(len(content)))
        handler.end_headers()
        handler.wfile.write(content)
    except FileNotFoundError:
        json_response(handler, {'error': 'Not Found'}, 404)


# ─── API 路由处理 ────────────────────────────────────


def route_api(handler, method, path, query, body):
    """API路由分发"""
    _lazy_import()

    # ========== 统计 ==========
    if method == 'GET' and path == '/api/stats':
        try:
            stats = _imap.get_stats()
            return json_response(handler, {'ok': True, 'data': stats})
        except ConnectionError as e:
            return json_response(handler, {'ok': False, 'error': str(e)}, 503)
        except Exception as e:
            return json_response(handler, {'ok': False, 'error': str(e)}, 500)

    # ========== 收件箱邮件列表 ==========
    elif method == 'GET' and path == '/api/emails':
        try:
            emails = _imap.fetch_all_inbox_emails()
            return json_response(handler, {'ok': True, 'data': emails})
        except ConnectionError as e:
            return json_response(handler, {'ok': False, 'error': str(e)}, 503)
        except Exception as e:
            return json_response(handler, {'ok': False, 'error': str(e)}, 500)

    # ========== 草稿箱列表 ==========
    elif method == 'GET' and path == '/api/drafts':
        try:
            conn = _imap.connect()
            drafts = _imap.list_drafts(conn, filter_ai_only=True)
            return json_response(handler, {'ok': True, 'data': drafts})
        except ConnectionError as e:
            return json_response(handler, {'ok': False, 'error': str(e)}, 503)
        except Exception as e:
            return json_response(handler, {'ok': False, 'error': str(e)}, 500)

    # ========== 获取单封草稿详情 ==========
    elif method == 'GET' and path.startswith('/api/drafts/'):
        draft_id = path.replace('/api/drafts/', '', 1).split('/')[0]
        try:
            conn = _imap.connect()
            all_drafts = _imap.list_drafts(conn, filter_ai_only=False)
            for d in all_drafts:
                if d.get('id') == draft_id or d.get('imap_id') == draft_id:
                    return json_response(handler, {'ok': True, 'data': d})
            return json_response(handler, {'ok': False, 'error': '未找到该草稿'}, 404)
        except Exception as e:
            return json_response(handler, {'ok': False, 'error': str(e)}, 500)

    # ========== 发送草稿 ==========
    elif method == 'POST' and path == '/api/send-draft':
        try:
            data = body
            to_addr = data.get('to', '')
            subject = data.get('subject', '')
            body_text = data.get('body', '')
            draft_imap_id = data.get('draft_imap_id', '')

            if not to_addr or not subject:
                return json_response(handler, {'ok': False, 'error': '缺少收件人或主题'}, 400)

            # 通过 SMTP 发送
            ok, msg = _smtp_sender.send_email(to_addr, subject, body_text)
            if not ok:
                return json_response(handler, {'ok': False, 'error': msg}, 502)

            # 发送成功，删除原草稿
            if draft_imap_id:
                try:
                    conn = _imap.connect()
                    _imap.delete_draft(conn, draft_imap_id)
                except Exception:
                    pass  # 删除草稿是辅助操作，不影响主流程

            return json_response(handler, {'ok': True, 'message': '发送成功'})

        except Exception as e:
            return json_response(handler, {'ok': False, 'error': str(e)}, 500)

    # ========== 重新生成回复 ==========
    elif method == 'POST' and path == '/api/regenerate':
        try:
            data = body
            subject = data.get('subject', '')
            body_text = data.get('body', '')
            sender = data.get('sender', '')

            reply_subj, reply_body, used_fallback, tmpl = _ai.generate_reply(
                subject, body_text, sender
            )
            return json_response(handler, {
                'ok': True,
                'data': {
                    'reply_subject': reply_subj,
                    'reply_body': reply_body,
                    'used_fallback': used_fallback,
                    'template': tmpl,
                }
            })
        except Exception as e:
            return json_response(handler, {'ok': False, 'error': str(e)}, 500)

    # ========== 触发自动处理 ==========
    elif method == 'POST' and path == '/api/process-new':
        def _run_and_return():
            try:
                _lazy_import()
                result = _processor.process_new_emails()
                return result
            except Exception as e:
                return {'error': str(e)}

        # 在后台线程执行
        thread_results = {}

        def worker():
            thread_results['result'] = _run_and_return()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(timeout=120)

        if 'result' in thread_results:
            return json_response(handler, {'ok': True, 'data': thread_results['result']})
        else:
            return json_response(handler, {'ok': False, 'error': '处理超时'}, 504)

    # ========== 删除草稿 ==========
    elif method == 'DELETE' and path.startswith('/api/drafts/'):
        draft_id = path.replace('/api/drafts/', '', 1).split('/')[0]
        try:
            conn = _imap.connect()
            ok = _imap.delete_draft(conn, draft_id)
            if ok:
                return json_response(handler, {'ok': True, 'message': '已删除'})
            else:
                return json_response(handler, {'ok': False, 'error': '删除失败'}, 500)
        except Exception as e:
            return json_response(handler, {'ok': False, 'error': str(e)}, 500)

    # ========== 健康检查 ==========
    elif method == 'GET' and path == '/api/health':
        return json_response(handler, {'ok': True, 'status': 'running', 'time': time.time()})

    return json_response(handler, {'ok': False, 'error': 'Not Found'}, 404)


# ─── HTTP 请求处理器 ─────────────────────────────────


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理"""

    def log_message(self, fmt, *args):
        """自定义日志格式"""
        print(f'[API] {self.address_string()} - {fmt % args}')

    # -------- 静态文件路径 --------
    @property
    def static_dir(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

    def _is_static_file(self, path):
        """判断是否是静态文件请求"""
        if path == '/' or path == '':
            return True
        # 常见的静态文件扩展名
        static_exts = {'.html', '.js', '.css', '.json', '.png', '.jpg', '.ico', '.svg', '.woff2'}
        ext = os.path.splitext(path)[1].lower()
        return ext in static_exts

    def _handle_request(self, method):
        """统一请求处理入口"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/') or '/'
        query = parse_qs(parsed.query)

        # 读取请求体
        body = read_body(self)

        # API 路由
        if path.startswith('/api/'):
            try:
                route_api(self, method, path, query, body)
            except Exception as e:
                print(f'[API] 未捕获错误: {e}')
                traceback.print_exc()
                json_response(self, {'ok': False, 'error': f'服务器内部错误: {e}'}, 500)
            return

        # 静态文件
        if method == 'GET' and self._is_static_file(path):
            filepath = os.path.join(self.static_dir, path.lstrip('/'))
            if path == '/' or path == '':
                filepath = os.path.join(self.static_dir, 'index.html')
            # 确保文件在 static 目录内（安全）
            real_path = os.path.realpath(filepath)
            real_static = os.path.realpath(self.static_dir)
            if not real_path.startswith(real_static):
                json_response(self, {'error': 'Forbidden'}, 403)
                return
            return serve_static(self, real_path)

        json_response(self, {'ok': False, 'error': 'Not Found'}, 404)

    def do_GET(self):
        self._handle_request('GET')

    def do_POST(self):
        self._handle_request('POST')

    def do_DELETE(self):
        self._handle_request('DELETE')

    def do_OPTIONS(self):
        """CORS 预检请求"""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """多线程 HTTP 服务器"""
    allow_reuse_address = True
    daemon_threads = True


def run_server():
    """启动 API 服务器"""
    server = ThreadedHTTPServer((API_HOST, API_PORT), RequestHandler)
    print(f'[API] 服务器启动于 http://{API_HOST}:{API_PORT}')
    print(f'[API] 前端访问: http://localhost:{API_PORT}')
    print(f'[API] API 接口: http://localhost:{API_PORT}/api/')
    print('[API] 按 Ctrl+C 停止')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[API] 服务器已停止')
        server.server_close()


if __name__ == '__main__':
    run_server()

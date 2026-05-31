"""
QQ邮箱 SMTP 发送模块
通过 smtp.qq.com 发送邮件
"""
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from config import SMTP_SERVER, SMTP_PORT, SMTP_SSL, EMAIL_ACCOUNT, EMAIL_PASSWORD, SENDER_NAME


def send_email(to_addr, subject, body):
    """
    通过 QQ邮箱 SMTP 发送邮件
    参数:
        to_addr: 收件人邮箱地址 (str)
        subject: 邮件主题
        body: 邮件正文
    返回: (success: bool, message: str)
    """
    if not to_addr or '@' not in to_addr:
        return False, f'无效的收件人地址: {to_addr}'

    try:
        # 构造邮件
        display_name = SENDER_NAME if SENDER_NAME else EMAIL_ACCOUNT
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['From'] = formataddr((display_name, EMAIL_ACCOUNT))
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)

        # 连接 SMTP 服务器并发送
        if SMTP_SSL:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
            server.starttls()

        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ACCOUNT, to_addr, text)
        server.quit()

        return True, '发送成功'

    except smtplib.SMTPAuthenticationError:
        return False, 'SMTP登录失败：请检查授权码是否正确'
    except smtplib.SMTPRecipientsRefused:
        return False, '收件人被拒：邮箱地址可能无效'
    except smtplib.SMTPServerDisconnected:
        return False, 'SMTP服务器连接断开，请检查网络'
    except smtplib.SMTPException as e:
        return False, f'SMTP发送失败: {e}'
    except Exception as e:
        return False, f'发送出错: {e}'

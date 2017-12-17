# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 17-12-12 下午8:40
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from web2kindle.libs.log import Log
from web2kindle.libs.utils import load_config, singleton, find_file


class SendEmail:
    def __init__(self):
        self.CONFIG = load_config('./web2kindle/config/config.yml')
        self.log = Log('SendEmail2Kindle')

        try:
            self.username = self.CONFIG['EMAIL_USERNAME']
            self.password = self.CONFIG['PASSWORD']
            self.smtp_addr = self.CONFIG['SMTP_ADDR']
            self.kindle_addr = self.CONFIG['KINDLE_ADDR']
        except KeyError:
            self.log.log_it("无法实例化SendEmail2Kindle，请确保config.yml配置完整", 'ERROR')
            import os
            os._exit(1)

        self.sender = self.username
        self.sended = []
        self.client = smtplib.SMTP()

    def connect(self):
        try:
            self.log.log_it("正在连接邮件服务器", 'INFO')
            self.client.connect(self.smtp_addr)
            self.log.log_it("正在登录服务器", 'INFO')
            self.client.login(self.username, self.password)
            return True
        except smtplib.SMTPAuthenticationError:
            self.log.log_it("邮箱用户名或密码错误", 'WARN')
        return False

    def disconnect(self):
        self.client.quit()

    def __enter__(self):
        if not self.connect():
            raise Exception("SendEmail2Kindle连接服务器错误")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def send_file(self, file_path):
        msg = MIMEMultipart()
        msg['Subject'] = 'Web2kindle'
        msg['From'] = self.sender
        msg['To'] = self.kindle_addr

        file = MIMEApplication(
            open(file_path, 'rb').read())
        file.add_header('Content-Disposition', 'attachment', filename=file_path)
        msg.attach(file)
        try:
            self.client.sendmail(self.sender, self.kindle_addr, msg.as_string())
            self.sended.append(file_path)
        except smtplib.SMTPRecipientsRefused as e:
            self.log.log_it("所有收件人都被拒绝。", 'WARN')
        except smtplib.SMTPSenderRefused as e:
            self.log.log_it("发件人地址被拒绝。", 'WARN')
        except smtplib.SMTPDataError as e:
            self.log.log_it("服务器拒绝接受邮件数据。", 'WARN')
        except smtplib.SMTPException as e:
            self.log.log_it("未知错误。FILE_PATH:{},ERRINFO:{}".format(file_path, str(e)), 'WARN')

    def send_files(self, file_paths):
        for file_path in file_paths:
            self.log.log_it("正在发送：{}".format(file_path), 'INFO')
            self.send_file(file_path)


@singleton
class SendEmail2Kindle(SendEmail):
    def send_all_mobi(self, path):
        mobi_file_paths = find_file(path, '.*mobi')
        self.send_files(mobi_file_paths)

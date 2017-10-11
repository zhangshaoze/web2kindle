# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/10 9:53
import requests
from threading import Thread, Condition
from queue import PriorityQueue, Empty, Queue
import random
import re
import os
import time
from web2kindle.libs.log import Log

from requests.packages.urllib3.exceptions import InsecureRequestWarning

# 禁用安全请求警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

cond = Condition()


class RetryTask(Exception):
    pass


class Downloader(Thread):
    def __init__(self, to_download_q: PriorityQueue,
                 downloader_parser_q: PriorityQueue,
                 result_q: Queue,
                 name, session=requests.session()):
        super().__init__(name=name)
        self.to_download_q = to_download_q
        self.downloader_parser_q = downloader_parser_q
        self.result_q = result_q
        self.session = session

        self._exit = False

        self.log = Log(self.name)

    def exit(self):
        self._exit = True

    def get(self):
        try:
            task = self.to_download_q.get_nowait()
        except Empty:
            self.log.log_it("Scheduler to Downloader队列为空，{}等待中。".format(self.name), 'INFO')
            with cond:
                cond.wait()
                self.log.log_it("Downloader to Parser队列不为空。{}被唤醒。".format(self.name), 'INFO')
            return

        response = None
        self.log.log_it("请求 {}".format(task['url']))
        try:
            if re.match(r'^https?:/{2}\w.+$', task['url']):
                response = self.session.get(task['url'], **task.get('meta', {}))
        except Exception as e:
            self.log.log_it("网络请求错误。错误信息:{} URL:{} Response:{}".format(str(e), task['url'], response), 'INFO')
            if task['meta'].get('retry', None):
                if task['meta'].get('retried', 0) < task['meta'].get('retry'):
                    task['meta'].update({'retried': task['meta'].get('retried', 0)})
                    self.log.log_it("重试任务 {}".format(task), 'INFO')
                    self.to_download_q.put(task)
            return

        if response:
            task.update({'response': response})
        else:
            task.update({'response': None})
        self.downloader_parser_q.put(task)

    def run(self):
        while not self._exit:
            self.get()


class Parser(Thread):
    def __init__(self, to_download_q: PriorityQueue, downloader_parser_q: PriorityQueue, result_q, name):
        super().__init__(name=name)
        self.downloader_parser_q = downloader_parser_q
        self.to_download_q = to_download_q
        self.result_q = result_q

        self._exit = False
        self.log = Log(self.name)

    def exit(self):
        self._exit = True

    def parser(self):
        tasks = []
        data = None

        with cond:
            cond.notify_all()
        task = self.downloader_parser_q.get()

        try:
            data, tasks = task['parser'](task)
        except RetryTask:
            self.log.log_it("RetryTask Exception.Task{}".format(task), 'INFO')
            if task['meta'].get('retry', None):
                if task['meta'].get('retried', 0) < task['meta'].get('retry'):
                    task['meta'].update({'retried': task['meta'].get('retried', 0)})
                    self.log.log_it("重试任务 {}".format(task), 'INFO')
                    self.to_download_q.put(task)
            return
        except Exception as e:
            self.log.log_it("解析错误。错误信息：{}。Task：{}".format(str(e), task), 'WARN')

        if tasks and isinstance(tasks, list):
            self.log.log_it("获取新任务{}个。".format(len(tasks)), 'INFO')
            for new_task in tasks:
                self.to_download_q.put(new_task)
        elif tasks:
            self.log.log_it("获取新任务1个。", 'INFO')
            self.to_download_q.put(tasks)
        return data

    def run(self):
        while not self._exit:
            self.parser()


class Crawler:
    def __init__(self, to_download_q,
                 downloader_parser_q,
                 result_q,
                 parser_worker_count=1,
                 downloader_worker_count=1,
                 session=requests.session()):
        self.parser_worker_count = parser_worker_count
        self.downloader_worker_count = downloader_worker_count
        self.downloader_worker = []
        self.parser_worker = []
        self.log = Log("Crawler")

        self.to_download_q = to_download_q
        self.downloader_parser_q = downloader_parser_q
        self.result_q = result_q

        self.session = session

    def start(self):
        print("启动。输入Q结束。")
        for i in range(self.downloader_worker_count):
            _worker = Downloader(self.to_download_q, self.downloader_parser_q, self.result_q, "Downloader {}".format(i),
                                 self.session)
            self.downloader_worker.append(_worker)
            self.log.log_it("启动 Downloader {}".format(i), 'INFO')
            _worker.start()

        for i in range(self.parser_worker_count):
            _worker = Parser(self.to_download_q, self.downloader_parser_q, self.result_q, "Parser {}".format(i))
            self.parser_worker.append(_worker)
            self.log.log_it("启动 Parser {}".format(i), 'INFO')
            _worker.start()

        try:
            while True:
                q = input("")
                if q == 'Q':
                    # os._exit(0)
                    for worker in self.downloader_worker:
                        worker.exit()
                    for worker in self.parser_worker:
                        worker.exit()
                    return
        except KeyboardInterrupt:
            # os._exit(0)
            return


if __name__ == '__main__':
    iq = PriorityQueue()
    oq = PriorityQueue()
    result_q = Queue()
    crawler = Crawler(iq, oq, result_q)
    crawler.start()

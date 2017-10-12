# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/10 9:53
import re
import os
import traceback
from copy import deepcopy
from queue import PriorityQueue, Empty, Queue

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from threading import Thread, Condition
from furl import furl

from web2kindle.libs.log import Log
from web2kindle.config import config

# 禁用安全请求警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
cond = Condition()


class RetryTask(Exception):
    pass


class Task(dict):
    """
    'task': {
        'tid': str,                         md5(request.url + request.data)
        'priority': int,                    Priority of task
        'retried': int,                     Retried count
        'retry': int,                       Retry time
        'meta':dict                         A dict to some config or something to save
        {
            'retry': int                    The count of retry.Default: 0
            'retry_wait': int               Default: 3
            'catty.config.DUPE_FILTER': bool             Default: False
        },

        'request': dict
        {
            'method':str                    HTTP method
            'url':str                       URL
            'params':dict/bytes             (optional) Dictionary or bytes to be sent in the query string
            'data':dict/list                (optional) Dictionary or list of tuples [(key, value)]
                                            (will be form-encoded), bytes, or file-like object
            ‘json':str                      (optional) json data to send in the body
            'headers':dict                  (optional) Dictionary of HTTP Headers
            'cookies':dict/CookieJar        (optional) Dict or CookieJar object
            'files':dict                    (optional) Dictionary of 'name': file-like-objects (or {'name': file-tuple})
                                            for multipart encoding upload. can be a 2-tuple ('filename', fileobj),
                                            3-tuple ('filename', fileobj, 'content_type') a 4-tuple
                                            ('filename', fileobj, 'content_type', custom_headers), where 'content-type'
                                            is a string the content type of the given file and custom_headers a
                                            dict-like object containing additional headers add for the file.
            'timeout':float/tuple           (optional) a float, or (connect timeout, read timeout) tuple.
            'allow_redirects':bool          (optional) Boolean. Enable/disable GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD
                                            redirection. Defaults to True.
            'proxies':dict                  (optional) Dictionary mapping protocol to the URL of the proxy.
            'verify':bool/str               (optional) Either a boolean, in which case it controls whether we verify
                                            server's TLS certificate, or a string, in which case it must be a path
                                            a CA bundle to use. Defaults to True.
            'stream':bool                   (optional) if False, the response content will be immediately downloaded.
            'cert':str/tuple                (optional) if String, path to ssl client cert file (.pem).
                                            If Tuple, ('cert', 'key') pair.
        }

        'parser': function

        'response': requests.models.Response,
        # for detail:http://docs.python-requests.org/en/master/api/#requests.Response
        {
            'status_code':int               HTTP status code
            'url':str                       url
            'history':list                  A list of Response objects from the history of the Request. Any redirect
                                            responses will end up here. The list is sorted from the oldest to the most
                                            recent request.
            'encoding':str
            'reason':str                    OK
            'elapsed':timedelta             The amount of time elapsed between sending the request and the arrival of
                                            the response
            'text':str/unicode              Content of the response, in unicode.
            json():
                Returns the json-encoded content of a response, if any.
                    Parameters:	**kwargs -- Optional arguments that json.loads takes.
                    Raises:	ValueError -- If the response body does not contain valid json.

        }
    }
    """

    def __eq__(self, other):
        return self['priority'] == other['priority']

    def __lt__(self, other):
        return self['priority'] > other['priority']

    @staticmethod
    def make_task(params):
        if 'parser' not in params:
            raise Exception("Need a parser")

        if 'method' not in params:
            raise Exception("Need a method")

        if 'url' not in params:
            raise Exception("Need a url")

        params.setdefault('meta', {})
        params.setdefault('priority', 0)

        if re.match(r'^https?:/{2}\w.+$', params['url']):
            params['url'] = furl(params['url']).url
        else:
            raise Exception("Not a vaild URL.URL:{}".format(params['url']))
        return Task(**params)


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

    def request(self):
        response = None

        try:
            task = self.to_download_q.get_nowait()
        except Empty:
            self.log.log_it("Scheduler to Downloader队列为空，{}等待中。".format(self.name), 'INFO')
            with cond:
                cond.wait()
                self.log.log_it("Downloader to Parser队列不为空。{}被唤醒。".format(self.name), 'INFO')
            return

        self.log.log_it("请求 {}".format(task['url']))
        try:
            if re.match(r'^https?:/{2}\w.+$', task['url']):
                response = self.session.request(task['method'], task['url'], **task.get('meta', {}))
        except Exception as e:
            traceback.print_exc(file=open(os.path.join(config.LOG_PATH, 'downlaoder_traceback'), 'a'))
            traceback.print_exc()
            self.log.log_it("网络请求错误。错误信息:{} URL:{} Response:{}".format(str(e), task['url'], response), 'INFO')
            if task.get('retry', None):
                if task.get('retried', 0) < task.get('retry'):
                    task.update({'retried': task.get('retried', 0)})
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
            self.request()


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
            if task.get('retry', None):
                if task.get('retried', 0) < task.get('retry'):
                    task.update({'retried': task.get('retried', 0)})
                    self.log.log_it("重试任务 {}".format(task), 'INFO')
                    self.to_download_q.put(task)
            return
        except Exception as e:
            traceback.print_exc(file=open(os.path.join(config.LOG_PATH, 'parser_traceback'), 'a'))
            traceback.print_exc()
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
                    break
        except KeyboardInterrupt:
            # os._exit(0)
            pass

        for worker in self.downloader_worker:
            worker.exit()
        for worker in self.parser_worker:
            worker.exit()
        return

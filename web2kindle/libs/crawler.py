# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/10 9:53
import re
import traceback
import time
from queue import PriorityQueue, Empty, Queue

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from threading import Thread, Condition, Lock

from web2kindle.libs import CRAWLER_CONFIG
from web2kindle.libs.log import Log
from web2kindle.libs.utils import singleton, md5string

# 禁用安全请求警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
COND = Condition()


class RetryDownload(Exception):
    pass


class RetryDownloadEnForce(Exception):
    pass


class RetryParse(Exception):
    pass


class RetryParseEnForce(Exception):
    pass


class RetryResult(Exception):
    pass


class RetryResultEnForce(Exception):
    pass


class Task(dict):
    """
    'task': {
        'tid': str,                         md5(request.url + request.data)
        'method':str                        HTTP method
        'url':str                           URL
        'parser': function
        'priority': int,                    Priority of task
        'retried': int,                     Retried count
        'retry': int,                       Retry time
        'meta':dict                         A dict to some config or something to save
        {
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
        },

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
        parsed_data:                        Structured data from parser
    }
    """

    def __eq__(self, other):
        return self['priority'] == other['priority']

    def __lt__(self, other):
        return self['priority'] > other['priority']

    @staticmethod
    def make_task(params):
        if 'parser' not in params:
            # FIXME:Can't raise Exception in there
            raise Exception("Need a parser")

        if 'method' not in params:
            raise Exception("Need a method")

        if 'url' not in params:
            raise Exception("Need a url")

        tid = md5string(params['url'] + str(params.get('data')) + str(params.get('params')))
        params.setdefault('meta', {})
        params.setdefault('priority', 0)
        params.setdefault('retry', 3)
        params.setdefault('tid', tid)

        if not params['url'].startswith('http'):
            params['url'] = 'http://' + params['url']
        return Task(**params)


@singleton
class TaskManager:
    registered_task = set()
    ALLDONE = False

    def __init__(self, lock):
        self.lock = lock

    def register(self, tid):
        self.lock.acquire()
        self.registered_task.add(tid)
        self.lock.release()

    def unregister(self, tid):
        self.lock.acquire()
        try:
            self.registered_task.remove(tid)
        except KeyError:
            pass
        self.lock.release()

    def is_empty(self):
        self.lock.acquire()
        is_empty = (len(self.registered_task) == 0)
        self.lock.release()
        if is_empty:
            TaskManager.ALLDONE = True
        return is_empty


class Downloader(Thread):
    def __init__(self, to_download_q: PriorityQueue,
                 downloader_parser_q: PriorityQueue,
                 result_q: Queue,
                 name: str,
                 lock,
                 session=requests.session()):
        super().__init__(name=name)
        self.to_download_q = to_download_q
        self.downloader_parser_q = downloader_parser_q
        self.result_q = result_q
        self.session = session

        self._exit = False

        self.log = Log(self.name)
        self.lock = lock
        self.task_manager = TaskManager(self.lock)

    def exit(self):
        self._exit = True

    def request(self):
        response = None

        try:
            task = self.to_download_q.get_nowait()
            self.task_manager.register(task['tid'])
        except Empty:
            self.log.log_it("Scheduler to Downloader队列为空，{}等待中。".format(self.name), 'DEBUG')
            with COND:
                COND.wait()
                self.log.log_it("Downloader to Parser队列不为空。{}被唤醒。".format(self.name), 'DEBUG')
            return

        self.log.log_it("请求 {}".format(task['url']), 'INFO')
        try:
            response = self.session.request(task['method'], task['url'], **task.get('meta', {}))
        except Exception as e:
            # traceback.print_exc(file=open(os.path.join(config.get('LOG_PATH'), 'downlaoder_traceback'), 'a'))
            traceback.print_exc()
            self.log.log_it("网络请求错误。错误信息:{} URL:{} Response:{}".format(str(e), task['url'], response), 'INFO')
            if task.get('retry', None):
                if task.get('retried', 0) < task.get('retry'):
                    task.update({'retried': task.get('retried', 1) + 1})
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
    def __init__(
            self,
            to_download_q: PriorityQueue,
            downloader_parser_q: PriorityQueue,
            result_q: Queue,
            name: str,
            lock):
        super().__init__(name=name)
        self.downloader_parser_q = downloader_parser_q
        self.to_download_q = to_download_q
        self.result_q = result_q

        self._exit = False
        self.log = Log(self.name)
        self.lock = lock
        self.task_manager = TaskManager(self.lock)

    def exit(self):
        self._exit = True

    def parser(self):

        with COND:
            COND.notify_all()
        task = self.downloader_parser_q.get()

        try:
            task_with_parsed_data, tasks = task['parser'](task)
        except RetryDownload:
            self.log.log_it("RetryDownload Exception.Task{}".format(task), 'INFO')
            if task.get('retry', None):
                if task.get('retried', 0) < task.get('retry'):
                    task.update({'retried': task.get('retried', 1) + 1})
                    self.to_download_q.put(task)
            return
        except RetryDownloadEnForce:
            self.log.log_it("RetryDownloadEnForce Exception.Task{}".format(task), 'INFO')
            self.to_download_q.put(task)
            return
        except RetryParse:
            self.log.log_it("RetryParse Exception.Task{}".format(task), 'INFO')
            if task.get('retry', None):
                if task.get('retried', 0) < task.get('retry'):
                    task.update({'retried': task.get('retried', 1) + 1})
                    self.downloader_parser_q.put(task)
            return
        except RetryParseEnForce:
            self.log.log_it("RetryParse Exception.Task{}".format(task), 'INFO')
            self.downloader_parser_q.put(task)
            return
        except Exception as e:
            # FIXME FileNotFoundError
            # traceback.print_exc(file=open(os.path.join(config.get('LOG_PATH'), 'parser_traceback'), 'a'))
            traceback.print_exc()
            self.log.log_it("解析错误。错误信息：{}。Task：{}".format(str(e), task), 'WARN')
            return

        if tasks and isinstance(tasks, list):
            self.log.log_it("获取新任务{}个。".format(len(tasks)), 'INFO')
            for new_task in tasks:
                self.task_manager.register(new_task['tid'])
                self.to_download_q.put(new_task)
        elif tasks:
            self.log.log_it("获取新任务1个。", 'INFO')
            self.task_manager.register(tasks['tid'])
            self.to_download_q.put(tasks)
        self.task_manager.unregister(task['tid'])
        return task_with_parsed_data

    def run(self):
        while not self._exit:
            task_with_parsed_data = self.parser()
            if task_with_parsed_data:
                self.result_q.put(task_with_parsed_data)


class Resulter(Thread):
    def __init__(
            self,
            to_download_q: PriorityQueue,
            downloader_parser_q: PriorityQueue,
            result_q: Queue,
            name: str,
            lock):
        super().__init__(name=name)
        self.result_q = result_q
        self.downloader_parser_q = downloader_parser_q
        self.to_download_q = to_download_q

        self._exit = False
        self.log = Log(self.name)
        self.lock = lock
        self.task_manager = TaskManager(self.lock)

    def exit(self):
        self._exit = True

    def result(self):
        with COND:
            COND.notify_all()

        try:
            task = self.result_q.get_nowait()
        except Empty:
            time.sleep(1)
            return

        try:
            task['resulter'](task)
        except RetryDownload:
            self.log.log_it("RetryDownload Exception.Task{}".format(task), 'INFO')
            if task.get('retry', None):
                if task.get('retried', 0) < task.get('retry'):
                    task.update({'retried': task.get('retried', 1) + 1})
                    self.to_download_q.put(task)
            return
        except RetryDownloadEnForce:
            self.log.log_it("RetryDownloadEnForce Exception.Task{}".format(task), 'INFO')
            self.to_download_q.put(task)
            return
        except RetryParse:
            self.log.log_it("RetryParse Exception.Task{}".format(task), 'INFO')
            if task.get('retry', None):
                if task.get('retried', 0) < task.get('retry'):
                    task.update({'retried': task.get('retried', 1) + 1})
                    self.downloader_parser_q.put(task)
            return
        except RetryParseEnForce:
            self.log.log_it("RetryParse Exception.Task{}".format(task), 'INFO')
            self.downloader_parser_q.put(task)
        except RetryResult:
            self.log.log_it("RetryResult Exception.Task{}".format(task), 'INFO')
            if task.get('retry', None):
                if task.get('retried', 0) < task.get('retry'):
                    task.update({'retried': task.get('retried', 1) + 1})
                    self.result_q.put(task)
            return
        except RetryResultEnForce:
            self.log.log_it("RetryResultEnForce Exception.Task{}".format(task), 'INFO')
            self.result_q.put(task)
            return

        except Exception as e:
            # FIXME FileNotFoundError
            # traceback.print_exc(file=open(os.path.join(config.get('LOG_PATH'), 'parser_traceback'), 'a'))
            traceback.print_exc()
            self.log.log_it("Resulter函数错误。错误信息：{}。Task：{}".format(str(e), task), 'WARN')

    def run(self):
        while not (TaskManager.ALLDONE and self.result_q.empty()):
            self.result()


class Crawler:
    def __init__(self,
                 to_download_q,
                 downloader_parser_q,
                 result_q,
                 parser_worker_count=CRAWLER_CONFIG.get('PARSER_WORKER', 1),
                 downloader_worker_count=CRAWLER_CONFIG.get('DOWNLOADER_WORKER', 1),
                 resulter_worker_count=CRAWLER_CONFIG.get('RESULTER_WORKER', 1),
                 session=requests.session()):
        self.parser_worker_count = parser_worker_count
        self.downloader_worker_count = downloader_worker_count
        self.resulter_worker_count = resulter_worker_count
        self.downloader_worker = []
        self.parser_worker = []
        self.resulter_worker = []
        self.log = Log("Crawler")

        self.to_download_q = to_download_q
        self.downloader_parser_q = downloader_parser_q
        self.result_q = result_q

        self.session = session
        self.lock = Lock()
        self.task_manager = TaskManager(self.lock)

    def start(self):
        for i in range(self.downloader_worker_count):
            _worker = Downloader(self.to_download_q, self.downloader_parser_q, self.result_q, "Downloader {}".format(i),
                                 self.lock, self.session, )
            self.downloader_worker.append(_worker)
            self.log.log_it("启动 Downloader {}".format(i), 'INFO')
            _worker.start()

        for i in range(self.parser_worker_count):
            _worker = Parser(self.to_download_q, self.downloader_parser_q, self.result_q, "Parser {}".format(i),
                             self.lock)
            self.parser_worker.append(_worker)
            self.log.log_it("启动 Parser {}".format(i), 'INFO')
            _worker.start()

        for i in range(self.resulter_worker_count):
            _worker = Resulter(self.to_download_q, self.downloader_parser_q, self.result_q, "Resulter {}".format(i),
                               self.lock)
            self.resulter_worker.append(_worker)
            self.log.log_it("启动 Resulter {}".format(i), 'INFO')
            _worker.start()

        while True:
            time.sleep(1)
            if self.task_manager.is_empty():
                for worker in self.downloader_worker:
                    worker.exit()
                for worker in self.parser_worker:
                    worker.exit()

                resulter_not_alive = False
                while not resulter_not_alive:
                    resulter_not_alive = True
                    time.sleep(1)
                    for worker in self.resulter_worker:
                        resulter_not_alive &= not worker.is_alive()
                return

# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/10 14:05

import json
import os
import re
from copy import deepcopy
from queue import Queue, PriorityQueue
from urllib.parse import urlparse, unquote

from web2kindle.libs.crawler import Crawler, RetryTask, Task
from web2kindle.libs.utils import HTML2Kindle, write, format_file_name
from web2kindle.libs.log import Log
from pyquery import PyQuery

from web2kindle.config import zhihu_zhuanlan_config

html2kindle = HTML2Kindle()
log = Log("zhihu_zhuanlan")


def main(zhuanlan_name_list, page):
    iq = PriorityQueue()
    oq = PriorityQueue()
    result_q = Queue()
    crawler = Crawler(iq, oq, result_q)

    for zhuanlan_name in zhuanlan_name_list:
        new_header = deepcopy(zhihu_zhuanlan_config.DEFAULT_HEADERS)
        new_header.update({'Referer': 'https://zhuanlan.zhihu.com/{}'.format(zhuanlan_name)})
        task = Task.make_task({
            'url': 'https://zhuanlan.zhihu.com/api/columns/{}/posts?limit=20&offset={}'.format(zhuanlan_name, page),
            'method': 'GET',
            'meta': {'headers': new_header, 'verify': False},
            'parser': parser_list,
            'priority': 0,
            'save': {'cursor': 0},
            # 专栏ID
            'name': zhuanlan_name,
            'retry': 3,
            'save_path': os.path.join(zhihu_zhuanlan_config.SAVE_PATH, zhuanlan_name)
        })

        iq.put(task)

    crawler.start()
    for zhuanlan_name in zhuanlan_name_list:
        html2kindle.make_book_multi(os.path.join(zhihu_zhuanlan_config.SAVE_PATH, str(zhuanlan_name)))
    os._exit(0)


def parser_downloader_img(task):
    if task['response']:
        write(os.path.join(task['save_path'], 'static'), urlparse(task['response'].url).path[1:],
              task['response'].content, mode='wb')
    return None, None


def parser_content(task):
    title = task['title']
    download_img_list = []
    new_tasks = []

    try:
        response = task['response']
        if not response:
            raise RetryTask

        text = response.text
        if not re.search('<textarea id="preloadedState" hidden>(.*?)</textarea>', text):
            log.log_it('不能读取内容数据？（是否被ban？） {}'.format(response.url), 'INFO')
            raise RetryTask

        raw_json = re.search('<textarea id="preloadedState" hidden>(.*?)</textarea>', text).group(1)
        post = json.loads(raw_json)['database']['Post']
        content = post[list(post.keys())[0]]['content']

        download_img_list.extend(re.findall('src="(http.*?)"', content))

        pq = PyQuery(content)
        # 删除无用的img标签
        pq('img[src^="data"]').remove()
        content = pq.html()
        # 更换为本地相对路径
        content = re.sub('src="(.*?)"', lambda x: 'src="./static/{}"'.format(urlparse(x.group(1)).path[1:]), content)
        # 超链接的转换
        content = re.sub('//link.zhihu.com/\?target=(.*?)"', lambda x: unquote(x.group(1)), content)
        content = re.sub('<noscript>(.*?)</noscript>', lambda x: x.group(1), content, flags=re.S)

        html2kindle.make_content(title, content, os.path.join(task['save_path'], format_file_name(title, '.html')))

        img_header = deepcopy(zhihu_zhuanlan_config.DEFAULT_HEADERS)
        img_header.update({'Referer': response.url})
        for img_url in download_img_list:
            new_tasks.append(Task({
                'url': img_url,
                'method': 'GET',
                'meta': {'headers': img_header, 'verify': False},
                'parser': parser_downloader_img,
                'save_path': task['save_path'],
                'priority': 10,
            }))
    except Exception:
        html2kindle.make_content(title, '', os.path.join(task['save_path'], format_file_name(title, '.html')))
        raise Exception

    return None, new_tasks


def parser_list(task):
    response = task['response']
    new_tasks = []
    opf = []

    if not response:
        raise RetryTask

    data = json.loads(response.text)

    if len(data) != 0:
        # TODO：if ban?
        log.log_it('不能读取列表数据？（是否已经完结？） {}'.format(response.url), 'INFO')
        next_page_task = deepcopy(task)
        next_page_task.update(
            {'url': re.sub('offset=\d+', 'offset={}'.format(task['save']['cursor'] + 20), next_page_task['url'])})
        next_page_task['save'].update({'cursor': next_page_task['save']['cursor'] + 20})
        new_tasks.append(next_page_task)
    else:
        return None, None

    for item in data:
        # item['title']为文章的标题
        opf.append({'href': format_file_name(item['title'], '.html')})
        save = deepcopy(task['save'])
        new_task = Task({
            'url': 'https://zhuanlan.zhihu.com' + item['url'],
            'method': 'GET',
            'meta': task['meta'],
            'parser': parser_content,
            'priority': 5,
            'save': save,
            'name': task['name'],
            'title': item['title'],
            'save_path': task['save_path']
        })
        new_tasks.append(new_task)

    zhuanlan_name = task['name'] + '（第{}页）'.format(str(task['save']['cursor']))
    opf_path = os.path.join(task['save_path'], format_file_name(zhuanlan_name, '.opf'))

    html2kindle.make_table(opf, os.path.join(task['save_path'], format_file_name(zhuanlan_name, '_table.html')))
    html2kindle.make_opf(zhuanlan_name, opf, format_file_name(zhuanlan_name, '_table.html'), opf_path)

    return None, new_tasks


if __name__ == '__main__':
    main(['vinca520'], 0)

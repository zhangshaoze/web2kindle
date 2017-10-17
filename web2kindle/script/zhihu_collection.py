# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/9 19:07
import os
import re
import time
from copy import deepcopy
from queue import Queue, PriorityQueue
from urllib.parse import urlparse, unquote

from web2kindle.libs.crawler import Crawler, RetryTask, Task
from web2kindle.libs.utils import HTML2Kindle, write, format_file_name
from web2kindle.libs.log import Log
from pyquery import PyQuery

from web2kindle.config import zhihu_collection_config

html2kindle = HTML2Kindle()
log = Log('zhihu_collection')


def main(collection_num_list, start, end):
    iq = PriorityQueue()
    oq = PriorityQueue()
    result_q = Queue()
    crawler = Crawler(iq, oq, result_q)

    for collection_num in collection_num_list:
        task = Task.make_task({
            'url': 'https://www.zhihu.com/collection/{}?page={}'.format(collection_num, start),
            'method': 'GET',
            'meta': {'headers': zhihu_collection_config.DEFAULT_HEADERS, 'verify': False},
            'parser': parser_collection,
            'priority': 0,
            'retry': 3,
            'save': {'start': start, 'end': end,
                     'save_path': os.path.join(zhihu_collection_config.SAVE_PATH, str(collection_num))},
        })
        iq.put(task)
    crawler.start()
    for collection_num in collection_num_list:
        html2kindle.make_book_multi(os.path.join(zhihu_collection_config.SAVE_PATH, str(collection_num)))
    os._exit(0)


def parser_downloader_img(task):
    if task['response']:
        write(os.path.join(task['save']['save_path'], 'static'), urlparse(task['response'].url).path[1:],
              task['response'].content, mode='wb')
    else:
        log.log_it("无法下载图片（无Response）。URL：{}".format(task['url']), 'WARN')
    return None, None


def parser_collection(task):
    response = task['response']
    if not response:
        raise RetryTask

    text = response.text
    pq = PyQuery(text)
    download_img_list = []
    new_tasks = []
    opf = []

    now_page_num = re.search('page=(\d*)$', response.url)
    if now_page_num:
        now_page_num = int(now_page_num.group(1))
    else:
        now_page_num = 1

    collection_name = pq('.zm-item-title').eq(0).text().strip() + ' 第{}页'.format(now_page_num)
    log.log_it("获取收藏夹[{}]".format(collection_name), 'INFO')

    for i in pq('.zm-item').items():
        if i('.author-link-line a').text():
            author_name = i('.answer-head a.author-link').text()
        else:
            # 防止重名
            author_name = '匿名{}'.format(int(time.time()))

        title = i('.zm-item-title a').text() + '（作者：{}）'.format(author_name)
        content = i('.content').text()
        voteup_count = i('a.zm-item-vote-count').text()
        author_name = i('.answer-head a.author-link').text()
        created_time = i('p.visible-expanded a').text()

        # 需要下载的静态资源
        download_img_list.extend(re.findall('src="(http.*?)"', content))

        # 更换为本地相对路径
        content = re.sub('src="(.*?)"', lambda x: 'src="./static/{}"'.format(urlparse(x.group(1)).path[1:]), content)
        # 超链接的转换
        content = re.sub('//link.zhihu.com/\?target=(.*?)"', lambda x: unquote(x.group(1)), content)

        article_path = format_file_name(title, '.html')
        opf.append({'id': article_path, 'href': article_path})
        html2kindle.make_content(title, content,
                                 os.path.join(task['save']['save_path'], format_file_name(title, '.html')),
                                 {'author_name': author_name, 'voteup_count': voteup_count,
                                  'created_time': created_time})

    table_path = format_file_name(collection_name, '_table.html')
    opf_path = os.path.join(task['save']['save_path'], format_file_name(collection_name, '.opf'))
    html2kindle.make_table(opf, os.path.join(task['save']['save_path'], table_path))
    html2kindle.make_opf(collection_name, opf, table_path, opf_path)

    # Get next page url
    if now_page_num < task['save']['end']:
        pq.make_links_absolute(response.url)
        next_page = pq('.zm-invite-pager span:last a').eq(0).attr('href')
        if next_page:
            next_page_task = deepcopy(task)
            next_page_task.update({'url': next_page, 'priority': 0})
            new_tasks.append(next_page_task)

    img_header = deepcopy(zhihu_collection_config.DEFAULT_HEADERS)
    img_header.update({'Referer': response.url})
    for img_url in download_img_list:
        new_tasks.append(Task.make_task({
            'url': img_url,
            'method': 'GET',
            'meta': {'headers': img_header, 'verify': False},
            'parser': parser_downloader_img,
            'priority': 5,
            'save': task['save']
        }))

    return None, new_tasks


if __name__ == '__main__':
    main(['19903734'], 1, 2)

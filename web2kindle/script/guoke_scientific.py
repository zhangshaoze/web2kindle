# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 17-10-23 下午7:14
import os
import re
from copy import deepcopy
from queue import Queue, PriorityQueue
from urllib.parse import urlparse

from web2kindle.libs.crawler import Crawler, RetryTask, Task
from web2kindle.libs.utils import HTML2Kindle, write, format_file_name, load_config, check_config
from web2kindle.libs.log import Log
from bs4 import BeautifulSoup

SCRIPT_CONFIG = load_config('./web2kindle/config/guoke_scientific_config.yml')
MAIN_CONFIG = load_config('./web2kindle/config/config.yml')
HTML2KINDLE = HTML2Kindle(MAIN_CONFIG.get('KINDLEGEN_PATH'))
LOG = Log("guoke_scientific")
API_URL = "http://www.guokr.com/apis/minisite/article.json?retrieve_type=by_subject&limit=20&offset={}&_=1508757235776"
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
}
check_config(MAIN_CONFIG, SCRIPT_CONFIG, 'SAVE_PATH', LOG)


def main(start, end, kw):
    iq = PriorityQueue()
    oq = PriorityQueue()
    result_q = Queue()
    crawler = Crawler(iq, oq, result_q)
    default_headers = deepcopy(DEFAULT_HEADERS)
    default_headers.update({'Referer': 'http://www.guokr.com/scientific/'})

    task = Task.make_task({
        'url': API_URL.format(start),
        'method': 'GET',
        'meta': {'headers': default_headers, 'verify': False},
        'parser': parser_list,
        'priority': 0,
        'save': {
            'cursor': start,
            'start': start,
            'end': end,
            'kw': kw,
            'save_path': SCRIPT_CONFIG['SAVE_PATH'],
        },
        'retry': 3,
    })
    iq.put(task)

    crawler.start()
    HTML2KINDLE.make_book_multi(SCRIPT_CONFIG['SAVE_PATH'])
    os._exit(0)


def parser_list(task):
    response = task['response']
    if not response:
        raise RetryTask

    new_tasks = []
    opf = []

    try:
        data = response.json()
    except Exception as e:
        LOG.log_it('解析JSON出错（如一直出现，而且浏览器能正常访问，可能是网站代码升级，请通知开发者。）\nERRINFO:{}'
                   .format(str(e)), 'WARN')
        raise RetryTask

    try:
        for each_result in data['result']:
            title = each_result['title']
            url = each_result['url']
            date_group = re.search('(.*?)T(.*?)\+', each_result['date_created'])
            date = date_group.group(1) + ' ' + date_group.group(2)

            meta = deepcopy(task['meta'])
            save = deepcopy(task['save'])
            save.update({
                'title': title,
                'date': date
            })
            new_task = Task.make_task({
                'url': url,
                'method': 'GET',
                'parser': parser_content,
                'priority': 1,
                'meta': meta,
                'save': save
            })
            new_tasks.append(new_task)

            opf.append({'href': format_file_name(title, '.html')})
    except KeyError:
        LOG.log_it('JSON KEY出错（如一直出现，而且浏览器能正常访问，可能是网站代码升级，请通知开发者。）', 'WARN')
        raise RetryTask

    if opf:
        opf_name = '果壳网_科学人（第{}~{}篇）'.format(task['save']['cursor'], task['save']['cursor'] + 20)
        opf_path = os.path.join(task['save']['save_path'], format_file_name(opf_name, '.opf'))

        HTML2KINDLE.make_table(opf, os.path.join(task['save']['save_path'], format_file_name(opf_name, '_table.html')))
        HTML2KINDLE.make_opf(opf_name, opf, format_file_name(opf_name, '_table.html'), opf_path)

    # 获取下一页
    meta = deepcopy(task['meta'])
    save = deepcopy(task['save'])
    save['cursor'] += 20
    if save['cursor'] < save['end'] and not len(data['result']) < 20:
        new_task = Task.make_task({
            'url': API_URL.format(save['cursor']),
            'method': 'GET',
            'meta': meta,
            'parser': parser_list,
            'priority': 0,
            'save': save,
            'retry': 3,
        })
        new_tasks.append(new_task)

    return None, new_tasks


def parser_content(task):
    response = task['response']
    if not response:
        raise RetryTask

    new_tasks = []
    download_img_list = []
    opf = []
    soup = BeautifulSoup(response.text, 'lxml')

    content_select = soup.select('.document')
    # 移除每页后面无用的信息
    if content_select:
        for to_del in soup.select('.copyright'):
            to_del.decompose()

    content = str(content_select)
    # bs4会自动加html和body 标签
    content = re.sub('<html><body>(.*?)</body></html>', lambda x: x.group(1), content, flags=re.S)
    download_img_list.extend(re.findall('src="(http.*?)"', content))
    # 更换为本地相对路径
    content = re.sub('src="(.*?)"', convert_link, content)

    # 去掉"[]"
    content = content[1:-1]

    # 文件名太长无法制作mobi
    title = task['save']['title']
    if len(title) > 55:
        _ = 55 - 3
        title = title[:_] + '...'

    bs2 = BeautifulSoup(content, 'lxml')
    # 居中图片
    for tab in bs2.select('img'):
        tab.wrap(bs2.new_tag('div', style='text-align:center;'))
        tab['style'] = "display: inline-block;"
    content = str(bs2)

    article_path = format_file_name(title, '.html')
    opf.append({'id': article_path, 'href': article_path})
    HTML2KINDLE.make_content(title, content,
                             os.path.join(task['save']['save_path'], format_file_name(title, '.html')),
                             {'author_name': '', 'voteup_count': '',
                              'created_time': task['save']['date']})

    if task['save']['kw'].get('img', True):
        img_header = deepcopy(DEFAULT_HEADERS)
        img_header.update({'Referer': response.url})
        for img_url in download_img_list:
            new_tasks.append(Task.make_task({
                'url': img_url,
                'method': 'GET',
                'meta': {'headers': img_header, 'verify': False},
                'parser': parser_downloader_img,
                'priority': 2,
                'save': task['save']
            }))
    return None, new_tasks


def parser_downloader_img(task):
    if task['response']:
        write(os.path.join(task['save']['save_path'], 'static'), urlparse(task['response'].url).path[1:],
              task['response'].content, mode='wb')
    return None, None


def convert_link(x):
    return 'src="./static/{}"'.format(urlparse(x.group(1)).path[1:])


if __name__ == '__main__':
    main(0, 20, {'img': False})

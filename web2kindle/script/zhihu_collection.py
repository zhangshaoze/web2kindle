# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/9 19:07
import os
import re
import random
from copy import deepcopy
from queue import Queue, PriorityQueue
from urllib.parse import urlparse, unquote

from web2kindle.libs.crawler import Crawler, md5string, RetryTask, Task
from web2kindle.libs.utils import HTML2Kindle, write, format_file_name, load_config, check_config
from web2kindle.libs.log import Log
from bs4 import BeautifulSoup

SCRIPT_CONFIG = load_config('./web2kindle/config/zhihu_collection_config.yml')
MAIN_CONFIG = load_config('./web2kindle/config/config.yml')
HTML2KINDLE = HTML2Kindle(MAIN_CONFIG.get('KINDLEGEN_PATH'))
LOG = Log('zhihu_collection')
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
}

check_config(MAIN_CONFIG, SCRIPT_CONFIG, 'SAVE_PATH', LOG)


def main(collection_num_list, start, end, kw):
    iq = PriorityQueue()
    oq = PriorityQueue()
    result_q = Queue()
    crawler = Crawler(iq, oq, result_q)

    for collection_num in collection_num_list:
        task = Task.make_task({
            'url': 'https://www.zhihu.com/collection/{}?page={}'.format(collection_num, start),
            'method': 'GET',
            'meta': {'headers': DEFAULT_HEADERS, 'verify': False},
            'parser': parser_collection,
            'priority': 0,
            'retry': 3,
            'save': {'start': start,
                     'end': end,
                     'kw': kw,
                     'save_path': os.path.join(SCRIPT_CONFIG['SAVE_PATH'], str(collection_num))},
        })
        iq.put(task)
    crawler.start()
    for collection_num in collection_num_list:
        HTML2KINDLE.make_book_multi(os.path.join(SCRIPT_CONFIG['SAVE_PATH'], str(collection_num)))
    os._exit(0)


def parser_downloader_img(task):
    if task['response']:
        if 'www.zhihu.com/equation' not in task['url']:
            write(os.path.join(task['save']['save_path'], 'static'), urlparse(task['response'].url).path[1:],
                  task['response'].content, mode='wb')
        else:
            write(os.path.join(task['save']['save_path'], 'static'), md5string(task['url']) + '.svg',
                  task['response'].content,
                  mode='wb')
    return None, None


def convert_link(x):
    if 'www.zhihu.com/equation' not in x.group(1):
        return 'src="./static/{}"'.format(urlparse(x.group(1)).path[1:])
    # svg等式的保存
    else:
        a = 'src="./static/{}.svg"'.format(md5string(x.group(1)))
        return a


def parser_collection(task):
    response = task['response']
    if not response:
        raise RetryTask

    text = response.text
    bs = BeautifulSoup(text, 'lxml')
    download_img_list = []
    new_tasks = []
    opf = []

    now_page_num = re.search('page=(\d*)$', response.url)
    if now_page_num:
        now_page_num = int(now_page_num.group(1))
    else:
        now_page_num = 1

    try:
        collection_name = bs.select('.zm-item-title')[0].string.strip() + ' 第{}页'.format(now_page_num)
    except Exception as e:
        LOG.log_it("无法获取收藏列表（如一直出现，而且浏览器能正常访问知乎，可能是知乎代码升级，请通知开发者。）\nERRINFO:{} ".format(str(e)), 'WARN')
        raise RetryTask

    LOG.log_it("获取收藏夹[{}]".format(collection_name), 'INFO')

    if not bs.select('.zm-item'):
        LOG.log_it("无法获取收藏列表（如一直出现，而且浏览器能正常访问知乎，可能是知乎代码升级，请通知开发者。）", 'WARN')
        raise RetryTask

    for i in bs.select('.zm-item'):
        if i.select('.answer-head a.author-link'):
            author_name = i.select('.answer-head a.author-link')[0].string
        else:
            # 防止重名
            author_name = '匿名{}'.format(random.randint(0, 999999))

        title = i.select('.zm-item-title a')[0].string if i.select('.zm-item-title a') else ''

        # 文件名太长无法制作mobi
        if len(title) + len(author_name) + 2 > 55:
            _ = 55 - len(author_name) - 2 - 3
            title = title[:_] + '...' '（{}）'.format(author_name)
        else:
            title = title + '（{}）'.format(author_name)

        content = i.select('.content')[0].string if i.select('.content') else ''
        voteup_count = i.select('a.zm-item-vote-count')[0].string if i.select('a.zm-item-vote-count') else ''
        created_time = i.select('p.visible-expanded a')[0].string if i.select('p.visible-expanded a') else ''

        bs2 = BeautifulSoup(content, 'lxml')

        for tab in bs2.select('img[src^="data"]'):
            # 删除无用的img标签
            tab.decompose()

        # 居中图片
        for tab in bs2.select('img'):
            if 'equation' not in tab['src']:
                tab.wrap(bs2.new_tag('div', style='text-align:center;'))
                tab['style'] = "display: inline-block;"

        content = str(bs2)
        # bs4会自动加html和body 标签
        content = re.sub('<html><body>(.*?)</body></html>', lambda x: x.group(1), content, flags=re.S)

        # 公式地址转换（傻逼知乎又换地址了）
        # content = content.replace('//www.zhihu.com', 'http://www.zhihu.com')

        # 需要下载的静态资源
        download_img_list.extend(re.findall('src="(http.*?)"', content))

        # 更换为本地相对路径
        content = re.sub('src="(.*?)"', convert_link, content)

        # 超链接的转换
        content = re.sub('//link.zhihu.com/\?target=(.*?)"', lambda x: unquote(x.group(1)), content)

        article_path = format_file_name(title, '.html')
        opf.append({'id': article_path, 'href': article_path})
        HTML2KINDLE.make_content(title, content,
                                 os.path.join(task['save']['save_path'], format_file_name(title, '.html')),
                                 {'author_name': author_name, 'voteup_count': voteup_count,
                                  'created_time': created_time})

    table_path = format_file_name(collection_name, '_table.html')
    opf_path = os.path.join(task['save']['save_path'], format_file_name(collection_name, '.opf'))
    HTML2KINDLE.make_table(opf, os.path.join(task['save']['save_path'], table_path))
    HTML2KINDLE.make_opf(collection_name, opf, table_path, opf_path)

    # Get next page url
    if now_page_num < task['save']['end']:
        # bs.make_links_absolute(response.url)
        next_page = bs.select('.zm-invite-pager span a')
        if next_page and next_page[-1].string == '下一页':
            next_page = re.sub('\?page=\d+', '', task['url']) + next_page[-1]['href']
            new_tasks.append(Task.make_task({
                'url': next_page,
                'method': 'GET',
                'priority': 0,
                'save': task['save'],
                'meta': task['meta'],
                'parser': parser_collection
            }))

    if task['save']['kw'].get('img', True):
        img_header = deepcopy(DEFAULT_HEADERS)
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
    main(['205859764'], 1, 10, {'img': True})

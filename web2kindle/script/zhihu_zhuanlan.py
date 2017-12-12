# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/10 14:05
import os
import re
from copy import deepcopy
from queue import Queue, PriorityQueue
from urllib.parse import urlparse, unquote

from web2kindle.libs.crawler import Crawler, RetryTask, Task
from web2kindle.libs.utils import HTML2Kindle, write, format_file_name, md5string, load_config, check_config
from web2kindle.libs.log import Log
from bs4 import BeautifulSoup

SCRIPT_CONFIG = load_config('./web2kindle/config/zhihu_zhuanlan_config.yml')
MAIN_CONFIG = load_config('./web2kindle/config/config.yml')
HTML2KINDLE = HTML2Kindle(MAIN_CONFIG.get('KINDLEGEN_PATH'))
LOG = Log("zhihu_zhuanlan")
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
}

check_config(MAIN_CONFIG, SCRIPT_CONFIG, 'SAVE_PATH', LOG)


def main(zhuanlan_name_list, start, end, kw):
    iq = PriorityQueue()
    oq = PriorityQueue()
    result_q = Queue()
    crawler = Crawler(iq, oq, result_q)

    for zhuanlan_name in zhuanlan_name_list:
        new_header = deepcopy(DEFAULT_HEADERS)
        new_header.update({'Referer': 'https://zhuanlan.zhihu.com/{}'.format(zhuanlan_name)})
        task = Task.make_task({
            'url': 'https://zhuanlan.zhihu.com/api/columns/{}/posts?limit=20&offset={}'.format(zhuanlan_name, start),
            'method': 'GET',
            'meta': {'headers': new_header, 'verify': False},
            'parser': parser_list,
            'priority': 0,
            'save': {'cursor': start,
                     'save_path': os.path.join(SCRIPT_CONFIG['SAVE_PATH'], zhuanlan_name),
                     'start': start,
                     'end': end,
                     'kw': kw,
                     'name': zhuanlan_name},
            'retry': 3,
        })

        iq.put(task)

    crawler.start()
    for zhuanlan_name in zhuanlan_name_list:
        HTML2KINDLE.make_book_multi(os.path.join(SCRIPT_CONFIG['SAVE_PATH'], str(zhuanlan_name)))
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


def parser_list(task):
    response = task['response']
    new_tasks = []
    opf = []

    if not response:
        raise RetryTask

    try:
        data = response.json()
        data.reverse()
    except Exception as e:
        LOG.log_it('解析JSON出错（如一直出现，而且浏览器能正常访问知乎，可能是知乎代码升级，请通知开发者。）\nERRINFO:{}'
                   .format(str(e)), 'WARN')
        raise RetryTask

    if len(data) != 0:
        if task['save']['cursor'] < task['save']['end'] - 20:
            next_page_task = deepcopy(task)
            next_page_task.update(
                {'url': re.sub('offset=\d+', 'offset={}'.format(task['save']['cursor'] + 20), next_page_task['url'])})
            next_page_task['save'].update({'cursor': next_page_task['save']['cursor'] + 20})
            new_tasks.append(next_page_task)
    else:
        LOG.log_it('不能读取专栏列表。（如一直出现，而且浏览器能正常访问知乎，可能是知乎代码升级，请通知开发者。）', 'WARN')
        raise RetryTask

    for item in data:
        opf.append({'href': format_file_name(item['title'], '.html')})
        new_task = Task.make_task({
            'url': 'https://zhuanlan.zhihu.com' + item['url'],
            'method': 'GET',
            'meta': task['meta'],
            'parser': parser_content,
            'priority': 5,
            'save': task['save'],
            'title': item['title'],
        })
        new_tasks.append(new_task)
    if opf:
        zhuanlan_name = task['save']['name'] + '（第{}页）'.format(str(task['save']['cursor']))
        opf_path = os.path.join(task['save']['save_path'], format_file_name(zhuanlan_name, '.opf'))

        HTML2KINDLE.make_table(opf,
                               os.path.join(task['save']['save_path'], format_file_name(zhuanlan_name, '_table.html')))
        HTML2KINDLE.make_opf(zhuanlan_name, opf, format_file_name(zhuanlan_name, '_table.html'), opf_path)

    return None, new_tasks


def parser_content(task):
    title = task['title']

    # 文件名太长无法制作mobi
    if len(title) > 55:
        _ = 55 - len(title) - 3
        title = title[:_] + '...'

    download_img_list = []
    new_tasks = []

    try:
        response = task['response']
        if not response:
            raise RetryTask

        bs = BeautifulSoup(response.text, 'lxml')

        content_tab = bs.select('.PostIndex-content')
        if content_tab:
            content = str(content_tab[0])
        else:
            LOG.log_it("不能找到文章的内容。（如一直出现，而且浏览器能正常访问知乎，可能是知乎代码升级，请通知开发者。）", 'WARN')
            raise RetryTask

        author_name = bs.select('.PostIndex-authorName')[0].string if bs.select('.PostIndex-authorName') else ''

        voteup_count = re.search('likesCount&quot;:(\d+),', response.text).group(1) if re.search(
            'likesCount&quot;:(\d+),', response.text) else ''

        created_time = str(bs.select('.PostIndex-header .HoverTitle')[1]['data-hover-title']) if len(
            bs.select('.PostIndex-header .HoverTitle')) == 2 else ''

        bs = BeautifulSoup(content, 'lxml')
        for tab in bs.select('img[src^="data"]'):
            # 删除无用的img标签
            tab.decompose()

        # 居中图片
        for tab in bs.select('img'):
            if 'equation' not in tab['src']:
                tab.wrap(bs.new_tag('div', style='text-align:center;'))
                tab['style'] = "display: inline-block;"

            # 删除gif
            if task['save']['kw']['gif'] is False:
                if 'gif' in tab['src']:
                    tab.decompose()
                    continue

        content = str(bs)
        # bs4会自动加html和body 标签
        content = re.sub('<html><body>(.*?)</body></html>', lambda x: x.group(1), content, flags=re.S)

        # 公式地址转换（傻逼知乎又换地址了）
        # content = content.replace('//www.zhihu.com', 'http://www.zhihu.com')

        download_img_list.extend(re.findall('src="(http.*?)"', content))

        # 更换为本地相对路径
        content = re.sub('src="(.*?)"', convert_link, content)

        # 超链接的转换
        content = re.sub('//link.zhihu.com/\?target=(.*?)"', lambda x: unquote(x.group(1)), content)
        content = re.sub('<noscript>(.*?)</noscript>', lambda x: x.group(1), content, flags=re.S)

        HTML2KINDLE.make_content(title, content,
                                 os.path.join(task['save']['save_path'], format_file_name(title, '.html')),
                                 {'author_name': author_name, 'voteup_count': voteup_count,
                                  'created_time': created_time})

        if task['save']['kw'].get('img', True):
            img_header = deepcopy(DEFAULT_HEADERS)
            img_header.update({'Referer': response.url})
            for img_url in download_img_list:
                new_tasks.append(Task.make_task({
                    'url': img_url,
                    'method': 'GET',
                    'meta': {'headers': img_header, 'verify': False},
                    'parser': parser_downloader_img,
                    'save': task['save'],
                    'priority': 10,
                }))
    except RetryTask:
        HTML2KINDLE.make_content(title, '', os.path.join(task['save']['save_path'], format_file_name(title, '.html')))
        raise RetryTask
    except Exception as e:
        import traceback
        traceback.print_exc()
        HTML2KINDLE.make_content(title, '', os.path.join(task['save']['save_path'], format_file_name(title, '.html')))
        raise e

    return None, new_tasks


if __name__ == '__main__':
    main(['PatrickZhang'], 0, 20, {'img': True, 'gif': False})

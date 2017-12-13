# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 17-12-11 下午10:52
# !/usr/bin/env python
import os
import re
import datetime
import traceback
from copy import deepcopy
from queue import Queue, PriorityQueue
from urllib.parse import urlparse

from web2kindle.libs.crawler import Crawler, RetryTask, Task
from web2kindle.libs.send_email import SendEmail2Kindle
from web2kindle.libs.utils import HTML2Kindle, write, format_file_name, load_config, check_config
from web2kindle.libs.log import Log
from bs4 import BeautifulSoup

SCRIPT_CONFIG = load_config('./web2kindle/config/qdaily_config.yml')
MAIN_CONFIG = load_config('./web2kindle/config/config.yml')
HTML2KINDLE = HTML2Kindle(MAIN_CONFIG.get('KINDLEGEN_PATH'))
LOG = Log("qdaily_home")
API_URL = 'https://www.qdaily.com/homes/articlemore/{}.json'
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
}
check_config(MAIN_CONFIG, SCRIPT_CONFIG, 'SAVE_PATH', LOG)
API_BUSINESS = 'https://www.qdaily.com/categories/categorymore/18/{}.json'
API_INTELLIGENT = 'https://www.qdaily.com/categories/categorymore/4/{}.json'
API_DESIGN = 'https://www.qdaily.com/categories/categorymore/17/{}.json'
API_FASHION = 'https://www.qdaily.com/categories/categorymore/19/{}.json'
API_ENTERTAINMENT = 'https://www.qdaily.com/categories/categorymore/3/{}.json'
API_CITY = 'https://www.qdaily.com/categories/categorymore/5/{}.json'
API_GAME = 'https://www.qdaily.com/categories/categorymore/54/{}.json'
API_LONG = 'https://www.qdaily.com/tags/tagmore/1068/{}.json'


def main(start, end, kw):
    # start:2017/12/11
    # end:2017/12/12
    iq = PriorityQueue()
    oq = PriorityQueue()
    result_q = Queue()
    crawler = Crawler(iq, oq, result_q)
    try:
        start_l = [int(_) for _ in start.split('-')]
        end_l = [int(_) for _ in end.split('-')]
        start_t = int(datetime.datetime(start_l[0], start_l[1], start_l[2]).timestamp()) + 60 * 60 * 24
        end_t = int(datetime.datetime(end_l[0], end_l[1], end_l[2]).timestamp())
    except:
        LOG.log_it('日期格式错误', 'WARN')
        traceback.print_exc()
        return

    global API_URL
    if 'type' in kw:
        if kw['type'] == 'business':
            API_URL = API_BUSINESS
        elif kw['type'] == 'intelligent':
            API_URL = API_INTELLIGENT
        elif kw['type'] == 'design':
            API_URL = API_DESIGN
        elif kw['type'] == 'fashion':
            API_URL = API_FASHION
        elif kw['type'] == 'entertainment':
            API_URL = API_ENTERTAINMENT
        elif kw['type'] == 'city':
            API_URL = API_CITY
        elif kw['type'] == 'game':
            API_URL = API_GAME
        elif kw['type'] == 'long':
            API_URL = API_LONG
        elif kw['type'] == 'home':
            pass
    else:
        kw.update({'type': 'home'})

    new_header = deepcopy(SCRIPT_CONFIG.get('DEFAULT_HEADERS'))
    new_header.update({'Referer': 'https://www.qdaily.com/'})
    task = Task.make_task({
        'url': API_URL.format(start_t),
        'method': 'GET',
        'meta': {'headers': new_header, 'verify': False},
        'parser': parser_list,
        'priority': 0,
        'save': {'cursor': start_t,
                 'save_path': os.path.join(SCRIPT_CONFIG['SAVE_PATH'],
                                           'qdaily_{}_{}_{}'.format(kw['type'], start, end)),
                 'start': start_t,
                 'end': end_t,
                 'kw': kw,
                 'page': 1,
                 'name': 'qdaily_{}_{}_{}'.format(kw['type'], start, end)},
        'retry': 3,
    })
    iq.put(task)

    crawler.start()
    HTML2KINDLE.make_book_multi(
        os.path.join(SCRIPT_CONFIG['SAVE_PATH'], str('qdaily_{}_{}_{}'.format(kw['type'], start, end))))

    if kw.get('email'):
        with SendEmail2Kindle() as s:
            s.send_all_mobi(
                os.path.join(SCRIPT_CONFIG['SAVE_PATH'], str('qdaily_{}_{}_{}'.format(kw['type'], start, end))))
    os._exit(0)


def parser_downloader_img(task):
    if task['response']:
        write(os.path.join(task['save']['save_path'], 'static'), urlparse(task['response'].url).path[1:],
              task['response'].content, mode='wb')
    return None, None


def convert_link(x):
    return 'src="./static/{}"'.format(urlparse(x.group(1)).path[1:])


def parser_list(task):
    response = task['response']
    new_tasks = []
    opf = []

    if not response:
        raise RetryTask

    try:
        data = response.json()
    except Exception as e:
        LOG.log_it('解析JSON出错（如一直出现，而且浏览器能正常访问，可能是代码升级，请通知开发者。）ERRINFO:{}'
                   .format(str(e)), 'WARN')
        raise RetryTask

    try:
        if len(data['data']) != 0:
            if data['data']['last_key'] > task['save']['end'] - 144209:
                next_page_task = deepcopy(task)
                next_page_task.update(
                    {'url': API_URL.format(data['data']['last_key'])})
                next_page_task['save'].update({'cursor': data['data']['last_key'], 'page': task['save']['page'] + 1})
                new_tasks.append(next_page_task)
        else:
            LOG.log_it('不能读取专栏列表。（如一直出现，而且浏览器能正常访问，可能是代码升级，请通知开发者。）', 'WARN')
            raise RetryTask

        for item in data['data']['feeds']:
            if item['datatype'] == 'article':
                item = item['post']
                opf.append({'href': format_file_name(item['title'], '.html')})
                new_task = Task.make_task({
                    'url': 'https://www.qdaily.com/articles/{}.html'.format(str(item['id'])),
                    'method': 'GET',
                    'meta': task['meta'],
                    'parser': parser_content,
                    'priority': 5,
                    'save': task['save'],
                    'title': item['title'],
                    'created_time': item['publish_time'],
                    'voteup_count': item['praise_count']
                })
                new_tasks.append(new_task)
    except KeyError:
        LOG.log_it('JSON KEY出错（如一直出现，而且浏览器能正常访问，可能是网站代码升级，请通知开发者。）', 'WARN')
        raise RetryTask

    if opf:
        opf_files_name = task['save']['name'] + '（第{}页）'.format(str(task['save']['page']))
        opf_path = os.path.join(task['save']['save_path'], format_file_name(opf_files_name, '.opf'))

        HTML2KINDLE.make_table(opf,
                               os.path.join(task['save']['save_path'], format_file_name(opf_files_name, '_table.html')))
        HTML2KINDLE.make_opf(opf_files_name, opf, format_file_name(opf_files_name, '_table.html'), opf_path)

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

        response.encoding = 'utf-8'
        bs = BeautifulSoup(response.text, 'lxml')

        content_tab = bs.select('.article-detail-bd > .detail')
        if content_tab:
            content = str(content_tab[0])
        else:
            LOG.log_it("不能找到文章的内容。（如一直出现，而且浏览器能正常访问，可能是代码升级，请通知开发者。）", 'WARN')
            raise RetryTask

        author_name = '未知'
        voteup_count = task['voteup_count']
        created_time = task['created_time']

        bs = BeautifulSoup(content, 'lxml')

        # 居中图片
        for tab in bs.select('img'):
            if len(tab.attrs['class']) != 1:
                tab.decompose()
                continue

            # 删除gif
            if task['save']['kw']['gif'] is False:
                if 'gif' in tab['data-src']:
                    tab.decompose()
                    continue

            tab.wrap(bs.new_tag('div', style='text-align:center;'))
            tab['style'] = "display: inline-block;"

        content = str(bs)
        # bs4会自动加html和body 标签
        content = re.sub('<html><body>(.*?)</body></html>', lambda x: x.group(1), content, flags=re.S)

        download_img_list.extend(re.findall('src="(http.*?)"', content))

        # 更换为本地相对路径
        content = re.sub('src="(.*?)"', convert_link, content)
        content = content.replace('data-src', 'src')

        HTML2KINDLE.make_content(title, content,
                                 os.path.join(task['save']['save_path'], format_file_name(title, '.html')),
                                 {'author_name': author_name, 'voteup_count': voteup_count,
                                  'created_time': created_time})

        if task['save']['kw'].get('img', True):
            img_header = deepcopy(SCRIPT_CONFIG.get('DEFAULT_HEADERS'))
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
    main('2017-12-12', '2017-12-11', {'img': True, 'gif': False, 'type': 'home', 'email': True})

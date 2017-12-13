# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/11 23:38
import os
import re
import datetime
from copy import deepcopy
from queue import Queue, PriorityQueue
from urllib.parse import urlparse, unquote

from web2kindle.libs.crawler import Crawler, RetryTask, Task
from web2kindle.libs.send_email import SendEmail2Kindle
from web2kindle.libs.utils import HTML2Kindle, write, format_file_name, load_config, md5string, check_config
from web2kindle.libs.log import Log
from bs4 import BeautifulSoup

SCRIPT_CONFIG = load_config('./web2kindle/config/zhihu_answers_config.yml')
MAIN_CONFIG = load_config('./web2kindle/config/config.yml')
LOG = Log("zhihu_answers")
HTML2KINDLE = HTML2Kindle(MAIN_CONFIG.get('KINDLEGEN_PATH'))
API_URL = "https://www.zhihu.com/api/v4/members/{}/answers?include=data%5B*%5D.is_normal%2Cadmin_closed_comment%2" \
          "Creward_info%2Cis_collapsed%2Cannotation_action%2Cannotation_detail%2Ccollapse_reason%2Ccollapsed_by%2" \
          "Csuggest_edit%2Ccomment_count%2Ccan_comment%2Ccontent%2Cvoteup_count%2Creshipment_settings%2Ccomment_" \
          "permission%2Cmark_infos%2Ccreated_time%2Cupdated_time%2Creview_info%2Cquestion%2Cexcerpt%2Crelationship." \
          "is_authorized%2Cvoting%2Cis_author%2Cis_thanked%2Cis_nothelp%2Cupvoted_followees%3Bdata%5B*%5D.author." \
          "badge%5B%3F(type%3Dbest_answerer)%5D.topics&offset={}&limit=20&sort_by=created"
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
}

check_config(MAIN_CONFIG, SCRIPT_CONFIG, 'SAVE_PATH', LOG)


def main(zhihu_answers_list, start, end, kw):
    """
    爬虫流程
    请求答主主页->获取main.app.js文件->在main.app.js文件里获取auth->带auth的header请求知乎api
    """
    iq = PriorityQueue()
    oq = PriorityQueue()
    result_q = Queue()
    crawler = Crawler(iq, oq, result_q)

    for zhihu_answers in zhihu_answers_list:
        task = Task.make_task({
            'url': 'https://www.zhihu.com/people/{}/answers?page={}'.format(zhihu_answers, start),
            'method': 'GET',
            'meta': {'headers': DEFAULT_HEADERS, 'verify': False},
            'parser': get_main_js,
            'priority': 0,
            'save': {
                'cursor': start,
                'start': start,
                'end': end,
                'kw': kw,
                'name': zhihu_answers,
                'save_path': os.path.join(SCRIPT_CONFIG['SAVE_PATH'], zhihu_answers),
                'base_url': 'https://www.zhihu.com/people/{}/answers?page={}'.format(zhihu_answers, start),
            },
            'retry': 3,
        })
        iq.put(task)

    crawler.start()

    for zhihu_answers in zhihu_answers_list:
        HTML2KINDLE.make_book_multi(os.path.join(SCRIPT_CONFIG['SAVE_PATH'], str(zhihu_answers)))

    if kw.get('email'):
        for zhihu_answers in zhihu_answers_list:
            with SendEmail2Kindle() as s:
                s.send_all_mobi(os.path.join(SCRIPT_CONFIG['SAVE_PATH'], str(zhihu_answers)))
    os._exit(0)


def get_main_js(task):
    response = task['response']
    if not response:
        raise RetryTask

    text = response.text

    js_id = re.search('src="https://static.zhihu.com/heifetz/main.app.(.*?)"', text)
    if not js_id:
        LOG.log_it("无法获得main_js的地址（如一直出现，而且浏览器能正常访问知乎，可能是知乎代码升级，请通知开发者。）", 'WARN')
        raise RetryTask
    js_url = 'https://static.zhihu.com/heifetz/main.app.{}'.format(js_id.group(1))

    new_headers = deepcopy(DEFAULT_HEADERS)
    new_headers.update({"Referer": task['save']['base_url']})
    meta = deepcopy(task['meta'])
    meta['headers'] = new_headers

    new_task = Task.make_task({
        'url': js_url,
        'method': 'GET',
        'parser': get_auth,
        'priority': 1,
        'meta': meta,
        'save': task['save']
    })
    return None, new_task


def get_auth(task):
    response = task['response']
    if not response:
        raise RetryTask

    text = response.text

    auth = None
    for _ in re.findall('h="(.*?)"', text):
        if len(_) == 32:
            auth = _

    if not auth:
        LOG.log_it("无法获得auth（如一直出现，而且浏览器能正常访问知乎，可能是知乎代码升级，请通知开发者。）", 'WARN')
        raise RetryTask

    new_headers = deepcopy(DEFAULT_HEADERS)
    new_headers.update({"Referer": task['save']['base_url'], "authorization": "oauth {}".format(auth)})
    meta = deepcopy(task['meta'])
    meta['headers'] = new_headers

    new_task = Task.make_task({
        'url': API_URL.format(task['save']['name'], task['save']['cursor']),
        'method': 'GET',
        'parser': get_answer,
        'priority': 2,
        'meta': meta,
        'save': task['save']
    })
    return None, new_task


def get_answer(task):
    new_tasks_list = []
    download_img_list = []
    response = task['response']
    opf = []

    try:
        json_data = response.json()
    except Exception as e:
        LOG.log_it('解析JSON出错（如一直出现，而且浏览器能正常访问知乎，可能是知乎代码升级，请通知开发者。）\nERRINFO:{}'
                   .format(str(e)), 'WARN')
        raise RetryTask

    if json_data['paging']['is_end'] is False and task['save']['cursor'] < task['save']['end'] - 20:
        new_task = deepcopy(task)
        new_task['save']['cursor'] += 20
        new_task.update({
            'url': API_URL.format(new_task['save']['name'], new_task['save']['cursor']),
            'method': 'GET',
            'parser': get_answer,
            'priority': 2,
            'retried': 0,
        })
        new_tasks_list.append(new_task)

    for answer in json_data['data']:
        title = answer['question']['title']

        # 文件名太长无法制作mobi
        if len(title) > 55:
            _ = 55 - len(title) - 3
            title = title[:_] + '...'

        author_name = answer['author']['name']
        author_headline = answer['author']['headline']
        content = answer['content']
        comment_count = answer['comment_count']
        voteup_count = answer['voteup_count']
        created_time = datetime.datetime.fromtimestamp(answer['created_time']).strftime('%Y-%m-%d')

        bs = BeautifulSoup(content, 'lxml')

        # 删除无用的img标签
        for tab in bs.select('img[src^="data"]'):
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

        opf.append({'href': format_file_name(title, '.html')})

        HTML2KINDLE.make_content(title, content,
                                 os.path.join(task['save']['save_path'], format_file_name(title, '.html')),
                                 {'author_name': author_name, 'voteup_count': voteup_count,
                                  'created_time': created_time})

    if opf:
        opf_name = task['save']['name'] + '（第{}~{}篇）'.format(task['save']['cursor'], task['save']['cursor'] + 20)
        opf_path = os.path.join(task['save']['save_path'], format_file_name(opf_name, '.opf'))

        HTML2KINDLE.make_table(opf, os.path.join(task['save']['save_path'], format_file_name(opf_name, '_table.html')))
        HTML2KINDLE.make_opf(opf_name, opf, format_file_name(opf_name, '_table.html'), opf_path)

    if task['save']['kw'].get('img', True):
        img_header = deepcopy(DEFAULT_HEADERS)
        img_header.update({'Referer': task['save']['base_url']})
        for img_url in download_img_list:
            new_tasks_list.append(Task.make_task({
                'url': img_url,
                'method': 'GET',
                'meta': {'headers': img_header, 'verify': False},
                'parser': parser_downloader_img,
                'save': task['save'],
                'priority': 3,
            }))

    return None, new_tasks_list


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


if __name__ == '__main__':
    main(['zhong-wen-sen'], 1, 20, {'img': True, 'gif': False})

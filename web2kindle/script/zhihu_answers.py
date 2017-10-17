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
from web2kindle.libs.utils import HTML2Kindle, write, format_file_name
from web2kindle.libs.log import Log
from pyquery import PyQuery

from web2kindle.config import zhihu_zhuanlan_config

html2kindle = HTML2Kindle()
log = Log("zhihu_answers")
api_url = "https://www.zhihu.com/api/v4/members/{}/answers?include=data%5B*%5D.is_normal%2Cadmin_closed_comment%2Creward_info%2Cis_collapsed%2Cannotation_action%2Cannotation_detail%2Ccollapse_reason%2Ccollapsed_by%2Csuggest_edit%2Ccomment_count%2Ccan_comment%2Ccontent%2Cvoteup_count%2Creshipment_settings%2Ccomment_permission%2Cmark_infos%2Ccreated_time%2Cupdated_time%2Creview_info%2Cquestion%2Cexcerpt%2Crelationship.is_authorized%2Cvoting%2Cis_author%2Cis_thanked%2Cis_nothelp%2Cupvoted_followees%3Bdata%5B*%5D.author.badge%5B%3F(type%3Dbest_answerer)%5D.topics&offset={}&limit=20&sort_by=created"


def main(zhihu_answers_list, start, end):
    iq = PriorityQueue()
    oq = PriorityQueue()
    result_q = Queue()
    crawler = Crawler(iq, oq, result_q)

    for zhihu_answers in zhihu_answers_list:
        task = Task.make_task({
            'url': 'https://www.zhihu.com/people/{}/answers?page={}'.format(zhihu_answers, start),
            'method': 'GET',
            'meta': {'headers': zhihu_zhuanlan_config.DEFAULT_HEADERS, 'verify': False},
            'parser': get_main_js,
            'priority': 0,
            'save': {
                'cursor': 0,
                'start': start,
                'end': end,
                # 专栏ID`
                'name': zhihu_answers,
                'save_path': os.path.join(zhihu_zhuanlan_config.SAVE_PATH, zhihu_answers),
                'base_url': 'https://www.zhihu.com/people/{}/answers?page={}'.format(zhihu_answers, start),
            },
            'retry': 3,
        })
        iq.put(task)

    crawler.start()
    for zhihu_answers in zhihu_answers_list:
        html2kindle.make_book_multi(os.path.join(zhihu_zhuanlan_config.SAVE_PATH, str(zhihu_answers)))
    os._exit(0)


def get_main_js(task):
    response = task['response']
    if not response:
        raise RetryTask

    text = response.text

    js_id = re.search('src="https://static.zhihu.com/heifetz/main.app.(.*?)"', text)
    if not js_id:
        log.log_it("无法获得main_js的地址", 'INFO')
        raise RetryTask
    js_url = 'https://static.zhihu.com/heifetz/main.app.{}'.format(js_id.group(1))

    new_headers = deepcopy(zhihu_zhuanlan_config.DEFAULT_HEADERS)
    new_headers.update({"Referer": task['save']['base_url']})
    new_task = deepcopy(task)
    new_task['meta']['headers'] = new_headers
    new_task.update({
        'url': js_url,
        'method': 'GET',
        'parser': get_auth,
        'priority': 1,
        'retried': 0,
    })
    return None, new_task


def get_auth(task):
    response = task['response']
    if not response:
        raise RetryTask

    text = response.text

    auth = re.search('w=t.CLIENT_ALIAS="(.*?)"', text)
    if not auth:
        log.log_it("无法获得auth", 'INFO')
        raise RetryTask

    new_task = deepcopy(task)
    new_headers = deepcopy(zhihu_zhuanlan_config.DEFAULT_HEADERS)
    new_headers.update({"Referer": task['save']['base_url'], "authorization": "oauth {}".format(auth.group(1))})
    new_task['meta']['headers'] = new_headers
    new_task['save'].update({'headers': new_headers})
    new_task.update({
        'url': api_url.format(task['save']['name'], task['save']['cursor']),
        'method': 'GET',
        'parser': get_answer,
        'priority': 2,
        'retried': 0,
    })
    return None, new_task


def get_answer(task):
    new_tasks_list = []
    download_img_list = []
    response = task['response']
    opf = []

    json_data = response.json()

    if json_data['paging']['is_end'] is False and task['save']['cursor'] < task['save']['end'] - 20:
        new_task = deepcopy(task)
        new_task['save']['cursor'] += 20
        new_task.update({
            'url': api_url.format(new_task['save']['name'], new_task['save']['cursor']),
            'method': 'GET',
            'parser': get_answer,
            'priority': 2,
            'retried': 0,
        })
        new_tasks_list.append(new_task)

    for answer in json_data['data']:
        title = answer['question']['title']
        author_name = answer['author']['name']
        author_headline = answer['author']['headline']
        content = answer['content']
        comment_count = answer['comment_count']
        voteup_count = answer['voteup_count']
        created_time = datetime.datetime.fromtimestamp(answer['created_time']).strftime('%Y-%m-%d')

        pq = PyQuery(content)
        # 删除无用的img标签
        pq('img[src^="data"]').remove()
        content = pq.html()
        download_img_list.extend(re.findall('src="(http.*?)"', content))

        # 更换为本地相对路径
        content = re.sub('src="(.*?)"', lambda x: 'src="./static/{}"'.format(urlparse(x.group(1)).path[1:]), content)
        # 超链接的转换
        content = re.sub('//link.zhihu.com/\?target=(.*?)"', lambda x: unquote(x.group(1)), content)
        content = re.sub('<noscript>(.*?)</noscript>', lambda x: x.group(1), content, flags=re.S)

        opf.append({'href': format_file_name(title, '.html')})

        html2kindle.make_content(title, content,
                                 os.path.join(task['save']['save_path'], format_file_name(title, '.html')),
                                 {'author_name': author_name, 'voteup_count': voteup_count,
                                  'created_time': created_time})

    if opf:
        opf_name = task['save']['name'] + '（第{}~{}篇）'.format(task['save']['cursor'], task['save']['cursor'] + 20)
        opf_path = os.path.join(task['save']['save_path'], format_file_name(opf_name, '.opf'))

        html2kindle.make_table(opf, os.path.join(task['save']['save_path'], format_file_name(opf_name, '_table.html')))
        html2kindle.make_opf(opf_name, opf, format_file_name(opf_name, '_table.html'), opf_path)

    # img_header = deepcopy(zhihu_zhuanlan_config.DEFAULT_HEADERS)
    # img_header.update({'Referer': task['save']['base_url']})
    # for img_url in download_img_list:
    #     new_tasks_list.append(Task.make_task({
    #         'url': img_url,
    #         'method': 'GET',
    #         'meta': {'headers': img_header, 'verify': False},
    #         'parser': parser_downloader_img,
    #         'save_path': task['save']['save_path'],
    #         'priority': 3,
    #     }))

    return None, new_tasks_list


def parser_downloader_img(task):
    if task['response']:
        write(os.path.join(task['save_path'], 'static'), urlparse(task['response'].url).path[1:],
              task['response'].content, mode='wb')
    return None, None


if __name__ == '__main__':
    main(['chen-zi-long-50-58'], 1, 20)

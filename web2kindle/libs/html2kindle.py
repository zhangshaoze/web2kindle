# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 17-12-14 下午8:23
import codecs
import random
from multiprocessing import cpu_count

import os
from jinja2 import Template
from functools import partial

from web2kindle.libs.log import Log
from web2kindle.libs.utils import read_file, get_system, format_file_name, split_list

if get_system() == 'Linux':
    KINDLE_GEN_PATH = './web2kindle/bin/kindlegen_linux'
elif get_system() == 'Windows':
    KINDLE_GEN_PATH = r'.\web2kindle\bin\kindlegen.exe'
else:
    KINDLE_GEN_PATH = './web2kindle/bin/kindlegen_mac'


class HTML2Kindle:
    content_template = Template(read_file('./web2kindle/templates/kindle_content.html'))
    opf_template = Template(read_file('./web2kindle/templates/kindle_opf.html'))
    index_template = Template(read_file('./web2kindle/templates/kindle_table.html'))
    ncx_template = Template(read_file('./web2kindle/templates/kindle_ncx.ncx'))

    def __init__(self, items, path, book_name, kindlegen_path=KINDLE_GEN_PATH):
        # self.template_env = Environment(loader=PackageLoader('web2kindle'))
        # self.content_template = self.template_env.get_template('kindle_content.html')
        # self.opf_template = self.template_env.get_template('kindle_opf.html')
        # self.index_template = self.template_env.get_template('kindle_table.html')
        # 打包成exe之后会有bug
        self.kindlegen_path = kindlegen_path if kindlegen_path is not None else KINDLE_GEN_PATH

        self.items = items
        self.book_name = str(book_name)
        self.path = path
        self.to_remove = set()
        self.log = Log('HTML2Kindle')

        if not os.path.exists(os.path.split(path)[0]):
            os.makedirs((os.path.split(path)[0]))

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
        self.remove()

    def __enter__(self):
        return self

    def remove(self):
        for i in self.to_remove:
            try:
                os.remove(i)
            except FileNotFoundError:
                pass

    def make_metadata(self, window=20):
        spilt_items = split_list(self.items, window)

        # 根据window分割电子书
        for index, items in enumerate(spilt_items):
            self.log.log_it("制作 {}_{} 的元数据".format(self.book_name, str(index)), 'INFO')
            opf = []
            table = []
            table_name = '{}_{}.html'.format(self.book_name, str(index))
            opf_name = '{}_{}.opf'.format(self.book_name, str(index))
            ncx_name = '{}_{}.ncx'.format(self.book_name, str(index))
            table_path = os.path.join(self.path, table_name)
            opf_path = os.path.join(self.path, opf_name)
            ncx_path = os.path.join(self.path, ncx_name)

            # 标记，以便删除
            self.to_remove.add(table_path)
            self.to_remove.add(opf_path)

            for item in items:
                kw = {'author_name': item[5], 'voteup_count': item[4], 'created_time': item[3]}
                # 文件名=title+author
                article_path = os.path.join(self.path, format_file_name(item[1], item[5]) + '.html')
                if os.path.exists(article_path):
                    # 防止文件名重复
                    article_path = article_path + ''.join(
                        [chr(random.choice(list(set(range(65, 123)) - set(range(91, 97))))) for i in range(3)])

                self.make_content(item[1], item[2], article_path, kw)
                # 标记，以便删除
                self.to_remove.add(article_path)
                opf.append({'id': article_path, 'href': article_path, 'title': item[1]})
                table.append({'href': article_path, 'name': item[1]})

            self.make_table(table, table_path)
            self.make_opf(self.book_name + '_' + str(index), opf, table_path, opf_path, ncx_path)
            self.make_ncx(self.book_name + '_' + str(index), opf, table_path, ncx_path)

    def make_opf(self, title, navigation, table_path, opf_path, ncx_path):
        rendered_content = self.opf_template.render(title=title, navigation=navigation, table_href=table_path,
                                                    ncx_href=ncx_path)
        with codecs.open(opf_path, 'w', 'utf_8_sig') as f:
            f.write(rendered_content)

    def make_ncx(self, title, navigation, table_path, opf_path):
        rendered_content = self.ncx_template.render(title=title, navigation=navigation, table_href=table_path)
        with codecs.open(opf_path, 'w', 'utf_8_sig') as f:
            f.write(rendered_content)

    def make_content(self, title, content, path, kw=None):
        rendered_content = self.content_template.render(title=title, content=content, kw=kw)
        with codecs.open(path, 'w', 'utf_8_sig') as f:
            f.write(rendered_content)

    def make_table(self, navigation, path):
        rendered_content = self.index_template.render(navigation=navigation)
        with codecs.open(path, 'w', 'utf_8_sig') as f:
            f.write(rendered_content)

    @staticmethod
    def _make_book(kindlegen_path, log_path, path):
        os.system("{} -dont_append_source {} >> {}".format(kindlegen_path, path, log_path))

    def make_book_multi(self, rootdir, overwrite=True):
        from multiprocessing import Pool
        self.log.log_it("新建 {} 个线程制作mobi文件.正在制作中，请稍后".format(str(cpu_count())), 'INFO')
        pool = Pool(cpu_count())
        opf_list = self.get_opf(rootdir, overwrite)
        pool.map(partial(self._make_book, self.kindlegen_path, os.path.join(self.path, 'kindlegen.log')), opf_list)

    def make_book(self, rootdir, overwrite=True):
        opf_list = self.get_opf(rootdir, overwrite)
        self.log.log_it("正在制作中，请稍后", 'INFO')
        for i in opf_list:
            os.system("{} -dont_append_source {} > {}".format(self.kindlegen_path, os.path.join(rootdir, i),
                                                              os.path.join(self.path, 'kindlegen.log')))

    def get_opf(self, rootdir, overwrite):
        result = []
        mobi = []
        for i in os.listdir(rootdir):
            if not os.path.isdir(os.path.join(rootdir, i)):
                if i.lower().endswith('mobi'):
                    mobi.append(i)

        for i in os.listdir(rootdir):
            if not os.path.isdir(os.path.join(rootdir, i)):
                if i.lower().endswith('opf'):
                    if overwrite:
                        result.append(os.path.join(rootdir, i))
                    else:
                        if i.replace('opf', 'mobi') not in mobi:
                            result.append(os.path.join(rootdir, i))
        return result

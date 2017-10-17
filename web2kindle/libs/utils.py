# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/10 9:52
import codecs
import os
import re
import yaml
from functools import partial
from multiprocessing import cpu_count

from jinja2 import Environment, PackageLoader


def load_config(path):
    try:
        f = open(path, 'r', encoding='utf-8')
    except UnicodeDecodeError:
        f = open(path, 'r')
    return yaml.load(f)


class HTML2Kindle:
    def __init__(self, kindlegen_path):
        self.template_env = Environment(loader=PackageLoader('web2kindle'))
        self.content_template = self.template_env.get_template('kindle_content.html')
        self.opf_template = self.template_env.get_template('kindle.html')
        self.index_template = self.template_env.get_template('kindle_index.html')
        self.kindlegen_path = kindlegen_path

    def make_opf(self, title, navigation, table_href, path):
        rendered_content = self.opf_template.render(title=title, navigation=navigation, table_href=table_href)
        if not os.path.exists(os.path.split(path)[0]):
            os.makedirs((os.path.split(path)[0]))
        with codecs.open(path, 'w', 'utf_8_sig') as f:
            f.write(rendered_content)

    def make_content(self, title, content, path, kw=None):
        rendered_content = self.content_template.render(title=title, content=content, kw=kw)
        if not os.path.exists(os.path.split(path)[0]):
            os.makedirs((os.path.split(path)[0]))
        with codecs.open(path, 'w', 'utf_8_sig') as f:
            f.write(rendered_content)

    def make_table(self, navigation, path):
        rendered_content = self.index_template.render(navigation=navigation)
        if not os.path.exists(os.path.split(path)[0]):
            os.makedirs((os.path.split(path)[0]))
        with codecs.open(path, 'w', 'utf_8_sig') as f:
            f.write(rendered_content)

    @staticmethod
    def _make_book(kindlegen_path, path):
        os.system("{} {}".format(kindlegen_path, path))

    def make_book_multi(self, rootdir):
        from multiprocessing import Pool
        pool = Pool(cpu_count())
        path_l = []
        for i in os.listdir(rootdir):
            if not os.path.isdir(os.path.join(rootdir, os.path.join(rootdir, i))):
                if i.lower().endswith('opf'):
                    path_l.append(os.path.join(rootdir, i))
        pool.map(partial(self._make_book, self.kindlegen_path), path_l)

    def make_book(self, rootdir):
        for i in os.listdir(rootdir):
            if not os.path.isdir(os.path.join(rootdir, i)):
                if i.lower().endswith('opf'):
                    os.system("{} {}".format(self.kindlegen_path, os.path.join(rootdir, i)))


def write(folder_path, file_path, content, mode='wb'):
    path = os.path.join(folder_path, file_path)
    if not os.path.exists(os.path.split(path)[0]):
        os.makedirs((os.path.split(path)[0]))
    with open(path, mode) as f:
        f.write(content)


def codes_write(folder_path, file_path, content, mode='wb'):
    path = os.path.join(folder_path, file_path)
    if not os.path.exists(os.path.split(path)[0]):
        os.makedirs((os.path.split(path)[0]))
    with open(path, mode) as f:
        f.write(content)


def format_file_name(file_name, a=''):
    return re.sub(r'[ \\/:*?"<>→|]', '', file_name) + a


def read_file(path):
    try:
        with open(path, 'r') as f:
            return [i.strip() for i in list(f.readlines())]
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return str(e)

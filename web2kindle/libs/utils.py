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
import hashlib
import platform
from functools import partial
from functools import wraps

from multiprocessing import cpu_count

from jinja2 import Template

md5string = lambda x: hashlib.md5(x.encode()).hexdigest()


def singleton(cls):
    instances = {}

    @wraps(cls)
    def getinstance(*args, **kw):
        if cls not in instances:
            instances[cls] = cls(*args, **kw)
        return instances[cls]

    return getinstance


def load_config(path):
    try:
        f = open(path, 'r', encoding='utf-8')
    except UnicodeDecodeError:
        f = open(path, 'r')
    return yaml.load(f)


def get_system():
    return platform.system()


if get_system() == 'Linux':
    KINDLE_GEN_PATH = './web2kindle/bin/kindlegen_linux'
elif get_system() == 'Windows':
    KINDLE_GEN_PATH = r'.\web2kindle\bin\kindlegen.exe'
else:
    KINDLE_GEN_PATH = './web2kindle/bin/kindlegen_mac'


class HTML2Kindle:
    def __init__(self, kindlegen_path=KINDLE_GEN_PATH):
        # self.template_env = Environment(loader=PackageLoader('web2kindle'))
        # self.content_template = self.template_env.get_template('kindle_content.html')
        # self.opf_template = self.template_env.get_template('kindle.html')
        # self.index_template = self.template_env.get_template('kindle_index.html')
        # 打包成exe之后会有bug

        self.content_template = Template(read_file('./web2kindle/templates/kindle_content.html'))
        self.opf_template = Template(read_file('./web2kindle/templates/kindle.html'))
        self.index_template = Template(read_file('./web2kindle/templates/kindle_index.html'))

        self.kindlegen_path = kindlegen_path if kindlegen_path is not None else KINDLE_GEN_PATH

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
        os.system("{} -dont_append_source {}".format(kindlegen_path, path))

    def make_book_multi(self, rootdir, overwrite=True):
        from multiprocessing import Pool
        pool = Pool(cpu_count())
        opf_list = self.get_opf(rootdir, overwrite)
        pool.map(partial(self._make_book, self.kindlegen_path), opf_list)

    def make_book(self, rootdir, overwrite=True):
        opf_list = self.get_opf(rootdir, overwrite)
        for i in opf_list:
            os.system("{} -dont_append_source {}".format(self.kindlegen_path, os.path.join(rootdir, i)))

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


def find_file(rootdir, pattern):
    finded = []
    for i in os.listdir(rootdir):
        if not os.path.isdir(os.path.join(rootdir, i)):
            if re.search(pattern, i):
                finded.append(os.path.join(rootdir, i))
    return finded


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
    return re.sub(r'[ \\/:*?"<>→|+]', '', file_name) + a


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    return str(text)


def read_file_to_list(path):
    try:
        with open(path, 'r') as f:
            return [i.strip() for i in list(f.readlines())]
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return str(e)


def check_config(main_config, script_config, config_name, logger):
    if config_name not in script_config:
        if config_name in main_config:
            script_config.update(main_config.get('DEFAULT_HEADERS'))
        else:
            logger.log_it("在配置文件中没有发现'DEFAULT_HEADERS'项，请确认主配置文件中或脚本配置文件中存在该项。", 'ERROR')
            os._exit(0)

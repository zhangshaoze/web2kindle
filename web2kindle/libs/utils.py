# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/10 9:52
import os
import re
import yaml
import hashlib
import platform

from functools import wraps


def md5string(x):
    return hashlib.md5(x.encode()).hexdigest()


def singleton(cls):
    instances = {}

    @wraps(cls)
    def getinstance(*args, **kw):
        if cls not in instances:
            instances[cls] = cls(*args, **kw)
        else:
            return instances[cls]
        return cls(*args, **kw)

    return getinstance


def load_config(path):
    try:
        f = open(path, 'r', encoding='utf-8')
    except UnicodeDecodeError:
        f = open(path, 'r')
    return yaml.load(f)


def get_system():
    return platform.system()


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
        try:
            os.makedirs((os.path.split(path)[0]))
        except FileExistsError:
            pass
    with open(path, mode) as f:
        f.write(content)


def codes_write(folder_path, file_path, content, mode='wb'):
    path = os.path.join(folder_path, file_path)
    if not os.path.exists(os.path.split(path)[0]):
        os.makedirs((os.path.split(path)[0]))
    with open(path, mode) as f:
        f.write(content)


def format_file_name(file_name, a=''):
    file_name = re.sub(r'[ \\/:*?"<>→|+]', '', file_name)

    if a:
        # 文件名太长无法保存mobi
        if len(file_name) + len(a) + 2 > 55:
            _ = 55 - len(a) - 2 - 3
            file_name = file_name[:_] + '...（{}）'.format(a)
        else:
            file_name = file_name + '（{}）'.format(a)
    else:
        if len(file_name) > 55:
            _ = 55 - 3
            file_name = file_name[:_] + '...'
        else:
            file_name = file_name
    return file_name


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


def split_list(the_list, window):
    return [the_list[i:i + window] for i in range(0, len(the_list), window)]

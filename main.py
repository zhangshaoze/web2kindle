# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/11 12:30
import click

import web2kindle.script.zhihu_collection
import web2kindle.script.zhihu_zhuanlan
from web2kindle.libs.utils import read_file


@click.group()
def cli():
    pass


@cli.command('zhihu_collection')
@click.option('--i')
@click.option('--f')
@click.option('--page', default=1)
def zhihu_collection_main(i, f, page):
    if i:
        web2kindle.script.zhihu_collection.main([i], page)
    elif f:
        collection_list = read_file(f)
        if isinstance(collection_list, list):
            web2kindle.script.zhihu_collection.main(collection_list, page)
        else:
            click.echo(collection_list)


@cli.command('zhihu_zhuanlan')
@click.option('--i')
@click.option('--f')
@click.option('--page', default=0)
def zhihu_collection_main(i, f, page):
    if i:
        web2kindle.script.zhihu_zhuanlan.main([i], page)
    elif f:
        zhuanlan_list = read_file(f)
        if isinstance(zhuanlan_list, list):
            web2kindle.script.zhihu_zhuanlan.main(zhuanlan_list, page)
        else:
            click.echo(zhuanlan_list)


if __name__ == '__main__':
    cli()

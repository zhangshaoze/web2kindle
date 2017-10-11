# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Vincent<vincent8280@outlook.com>
#         http://wax8280.github.io
# Created on 2017/10/11 12:30
import click

import web2kindle.script.zhihu_collection


@click.group()
def cli():
    pass


@cli.command('zhihu_collection')
@click.argument('n')
@click.option('--p', default=1)
def zhihu_collection_main(n, p):
    web2kindle.script.zhihu_collection.main(n, p)


@cli.command('bdist_wheel')
def bdist_wheel():
    click.echo('bdist_wheel called')


if __name__ == '__main__':
    cli()

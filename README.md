# 关于Web2Kindle

`Web2Kindle`是一个批量获取某些网页并将其转换为适合Kindle观看的电子书的程序。

# TODO
* 知乎登录功能

# 更新日志

### 0.1.0.0

测试版第一版

### 0.1.0.1

* 修复了一直重试的Bug，默认重试次数为3。
* 文章里面可以显示作者、创建时间、赞数。
* 设置开始和结束的范围（page参数已荒废）。
* 修复了专栏倒叙的Bug。
* 配置文件更改为YAML格式。
* 可以修改`Download`和`Parser`的数量。

### 0.1.1.0

* Task注册功能（自动判断无任务）



# 使用方法

## 安装Python

本程序使用Python3.6编写，您可前往[Python官网](https://www.python.org/)下载大于Python3.6的版本。

## 安装依赖库

切换到本项目目录下后，在控制台输入如下命令安装
```
pip install -r requirement
```

## 配置

配置文件在`config`目录下。配置文件其实是一个`yml`文件。

参考[配置](./配置)与[脚本](脚本)两章配置好配置文件。

## 使用

如使用本程序下载知乎某收藏夹（[https://www.zhihu.com/collection/59744917](https://www.zhihu.com/collection/59744917)与[https://www.zhihu.com/collection/67258836](https://www.zhihu.com/collection/67258836)）。

有一个本文文件`C:\Users\vincent8280\web2kindle\a.txt`。里面放着要下载的收藏夹的编号。

```
67258836
59744917
```

切换到本项目目录下后，在控制台输入如下命令：

```
python main.py zhihu_collection --f="C:\Users\vincent8280\web2kindle\a.txt"
```

运行结果如下（部分）：

```
启动。输入Q结束。
[2017-10-11 21:44:31,579][Crawler] 启动 Downloader 0
[2017-10-11 21:44:31,580][Crawler] 启动 Parser 0
[2017-10-11 21:44:31,580][Downloader 0] 请求 https://www.zhihu.com/collection/67258836?page=1
[2017-10-11 21:44:32,428][Downloader 0] 请求 https://www.zhihu.com/collection/59744917?page=1
[2017-10-11 21:44:32,459][zhihu_collection] 获取收藏夹[知乎找抽系列 第1页]
[2017-10-11 21:44:32,528][Parser 0] 获取新任务5个。
[2017-10-11 21:44:33,559][Downloader 0] 请求 https://pic2.zhimg.com/32aa4dc0b3a1d4f3a59ed969e5c8eeb1_b.jpg
[2017-10-11 21:44:33,596][zhihu_collection] 获取收藏夹[Read it later 第1页]
[2017-10-11 21:44:33,659][Parser 0] 获取新任务31个。
[2017-10-11 21:44:33,728][Downloader 0] 请求 https://pic1.zhimg.com/048d1383a27aa22284945f140d72ef74_b.png
.....
[2017-10-11 21:44:36,601][Downloader 0] 请求 https://pic4.zhimg.com/1688f4754c030827305f0afe99d9d023_b.png
[2017-10-11 21:44:36,685][Downloader 0] Scheduler to Downloader队列为空，Downloader 0等待中。
[2017-10-11 21:44:36,685][Downloader 0] Downloader to Parser队列不为空。Downloader 0被唤醒。
[2017-10-11 21:44:36,701][Downloader 0] Scheduler to Downloader队列为空，Downloader 0等待中。
Q

*************************************************************
 Amazon kindlegen(Windows) V2.9 build 1029-0897292
 命令行电子书制作软件
 Copyright Amazon.com and its Affiliates 2014
*************************************************************

信息(prcgen):I1047: 已添加的元数据dc:Title        "知乎找抽系列 第1页"
.....
信息(prcgen):I1037: 创建 Mobi 域名文件出现警告！

*************************************************************
 Amazon kindlegen(Windows) V2.9 build 1029-0897292
 命令行电子书制作软件
 Copyright Amazon.com and its Affiliates 2014
*************************************************************

信息(prcgen):I1047: 已添加的元数据dc:Title        "Read it later 第1页"
.....
信息(prcgen):I1037: 创建 Mobi 域名文件出现警告！
```

调用KindleGen制作电子书部分为多进程，所以部分显示不正常。

本程序还没实现自动判断下载完成，当很久无请求的之后，说明队列为空，请求已完成。此时手动输入“Q”来开始制作电子书。

# 配置

配置文件在`config`目录下。配置文件其实是一个`yml`文件，该文件以`yml`为后缀名。对于每个单独的脚本都有不同的配置文件，另有一个`config.yml`通用配置文件。

## config.py

```
# 注意冒号旁的两个空格
KINDLEGEN_PATH : 'C:\Users\web2kinle_save\kindlegen.exe'
LOG_PATH : 'C:\Users\web2kinle_save\log'
LOG_LEVEL : 'DEBUG'
DOWNLOADER_WORKER : 1
PARSER_WORKER : 1
```

- KINDLEGEN_PATH：KindleGen.exe程序所在路径
- LOG_PATH：日志文件
- LOG_LEVEL：日志等级
- DOWNLOADER_WORKER：启动Downloader的数量，建议为1~3。
- PARSER_WORKER：启动Parser的数量，建议为1。

# 脚本

对于每个网站都要编写不同的脚本来获取、解析、清洗元数据，最后调用`HTML2Kindle`类的`make_opf`、`make_content`、`make_table`来制作OPF、内容、目录文件。

我们可以通过以下命令来运行脚本

```
python main.py 脚本名称 参数
```

## 知乎

### zhihu_collection

批量获取知乎收藏夹。

```
//批量获取https://www.zhihu.com/collection/191640375第五页到最后一页
python main.py zhihu_collection --i=191640375 --page=5

//批量获取c:\a.txt文本文件下所有编号所示的收藏夹
python main.py zhihu_collection --f="c:\a.txt"
```

`c:\a.txt`文本文件。里面放着要下载的收藏夹的编号。分别用换行符隔开。

```
67258836
59744917
```

#### 参数

- --i：知乎收藏夹的编号。如[https://www.zhihu.com/collection/191640375](https://www.zhihu.com/collection/191640375)的编号为“191640375”
- --f：存放知乎收藏夹的号文本文件的路径。

可选参数：

- --start：开始页码数，如要从第五页开始`--start=5`
- --end：结束页码数，如要第十页结束`--end=10`

#### 配置

在`config`目录下新建一个`zhihu_collection_config.yml`文件。

```
DEFAULT_HEADERS : {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
}

SAVE_PATH : 'C:\Users\web2kinle_save'
```

- DEFAULT_HEADERS：请求头，默认即可。
- SVAE_PATH：保存路径名。会自动在此目录以`collection_num`生产一个子目录，元数据即保存在此子目录中。

### zhihu_zhuanlan

批量获取知乎专栏。

```
//批量获取https://zhuanlan.zhihu.com/vinca520第三篇到最后一篇
python main.py zhihu_collection --i=vinca520 --page=3

//批量获取c:\a.txt文本文件下所有编号所示的专栏
python main.py zhihu_collection --f="c:\a.txt"
```

`c:\a.txt`文本文件。里面放着要下载的专栏的编号。分别用换行符隔开。

```
vinca520
alenxwn
```
#### 参数

- --i：知乎专栏的编号。如[https://zhuanlan.zhihu.com/vinca520](https://zhuanlan.zhihu.com/vinca520)的编号为“vinca520”
- --f：存放知乎专栏编号文本文件的路径。

可选参数：

- --start：开始篇数，如要从第五篇开始`--start=5`
- --end：结束篇数，如要第十篇结束`--end=10`

#### 配置

在`config`目录下新建一个`zhihu_zhuanlan_config.yml`文件。

```
DEFAULT_HEADERS : {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
}

SAVE_PATH : 'C:\Users\web2kinle_save'
```

- DEFAULT_HEADERS：请求头，默认即可。
- SVAE_PATH：保存路径名。会自动在此目录以`collection_num`生产一个子目录，元数据即保存在此子目录中。

### zhihu_answers

批量获取知乎某人的全部回答。

```
//批量获取https://www.zhihu.com/people/zhong-wen-sen/answers第三篇到最后一篇
python main.py zhihu_answers --i=vinca520 --page=3

//批量获取c:\a.txt文本文件下所有答主的所有答案
python main.py zhihu_answers --f="c:\a.txt"
```

`c:\a.txt`文本文件。里面放着要下载的专栏的编号。分别用换行符隔开。

```
zhong-wen-sen
chen-zi-long-50-58
```

#### 参数

- --i：知乎答主的ID。如[https://www.zhihu.com/people/zhong-wen-sen/answers](https://www.zhihu.com/people/zhong-wen-sen/answers)的ID为“zhong-wen-sen”
- --f：存放知乎答主ID文本文件的路径。

可选参数：

- --start：开始篇数，如要从第五篇开始`--start=5`
- --end：结束篇数，如要第十篇结束`--end=10`

#### 配置

在`config`目录下新建一个`zhihu_answers_config.yml`文件。

```
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
}

SAVE_PATH : 'C:\Users\web2kinle_save'
```

- DEFAULT_HEADERS：请求头，默认即可。
- SVAE_PATH：保存路径名。会自动在此目录以`collection_num`生产一个子目录，元数据即保存在此子目录中。

# KindleGen

本项目使用Amazon官方的KindleGen生产mobi格式的电子书。

制作mobi必须编写两个文件：opf和ncx。他们可以理解为KindleGen的makefile，KindleGen通过这两个文件索引HTML，目录和其他多媒体资源。

## OPF

```html
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="BookId">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
<dc:title>电子书标题</dc:title>
<dc:language>en-us</dc:language>
</metadata>
<manifest>
     <!-- table of contents [mandatory] -->
    <item id="tochtml" media-type="application/xhtml+xml" href="toc.html"/>
    <item id="item0" media-type="application/xhtml+xml" href="Artical-1277621753.html"/>
    ...
    <!--下面是图片-->
     <item id="0.368541311142" media-type="image/jpg" href="Images/-1720404282.jpg"/>
</manifest>
<spine toc="desertfire">
  <!-- 下面描述了KG生成电子书后文本的顺序 -->
    <itemref idref="toc"/>  
    <itemref idref="tochtml"/>  
    <itemref idref="item31"/>
</spine>
<guide>
    <reference type="toc" title="Table of Contents" href="toc.html"></reference>
    <reference type="text" title="Welcome" href="toc.html"></reference>
</guide>
</package>
```

| 类型                | 作用            | 必须           |
| ----------------- | ------------- | ------------ |
| title             | 显示在封面的标题      | 是            |
| table of contents | 所有资源和对应的id    | 必须，id需要全局一致  |
| spine             | 给出生产电子书后页面的顺序 | 默认按照资源声明顺序浏览 |
| guide             | 提供目录的html等    | 可选           |

需要注意的有以下几点：

- 所有资源都需要一个id,命名任意，但不能重复。
- `media-type`描述了资源的类型，记住两类基本就够用了，`application/xhtml+xml`代表HTML文件，`image/jpg`或 `image/png`代表图片。
- 其他都可以省略，只是会影响电子书完整性。
- 由于这两个文件内部其实都是HTML，所以修改编辑都很容易。

## HTML

KindleGen只需要一个`<body>`标签即可。

```html
<body>
<head><meta charset="UTF-8"/></head>
内容
</body>
```

## 注意事项

本人遇过KindleGen转换出乱码的情况，后来通过“带BOM的UTF-8”编码解决。
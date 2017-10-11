# 关于Web2Kindle

`Web2Kindle`是一个批量获取某些网页并将其转换为适合Kindle观看的电子书的程序。

# 使用方法

## 安装Python

本程序使用Python3.6编写，您可前往[Python官网](https://www.python.org/)下载大于Python3.6的版本。

## 安装依赖库

切换到本项目目录下后，在控制台输入如下命令安装
```
pip install -r requirement
```

## 配置

配置文件在`config`目录下。配置文件其实是一个`.py`文件。

参考**配置**与**脚本**两章配置好配置文件。

## 使用

如使用本程序下载知乎某收藏夹（https://www.zhihu.com/collection/191640375）。

切换到本项目目录下后，在控制台输入如下命令：

```
python main.py zhihu_collection 191640375
```

运行结果如下（部分）：

```
Microsoft Windows [版本 10.0.14393]
(c) 2016 Microsoft Corporation。保留所有权利。

C:\Users\vincent8280\PycharmProjects\web2kindle>python main.py zhihu_collection 191640375
启动。输入Q结束。
[2017-10-11 16:32:59,262][Crawler] 启动 Downloader 0
[2017-10-11 16:32:59,262][Crawler] 启动 Parser 0
[2017-10-11 16:32:59,262][Downloader 0] 请求 https://www.zhihu.com/collection/191640375?page=1
[2017-10-11 16:33:02,881][Downloader 0] Scheduler to Downloader队列为空，Downloader 0等待中。
[2017-10-11 16:33:02,930][zhihu_collection] 获取收藏夹[20101010 第1页]
[2017-10-11 16:33:03,012][Parser 0] 获取新任务107个。
[2017-10-11 16:33:03,012][Downloader 0] Downloader to Parser队列不为空。Downloader 0被唤醒。
[2017-10-11 16:33:03,012][Downloader 0] 请求 https://pic1.zhimg.com/v2-be841a4a200e7cc0398fea8e3054c4f0_b.png
....
[2017-10-11 16:33:09,516][Downloader 0] 请求 https://pic3.zhimg.com/v2-69182c7e1f05afef702fb87ad875583a_b.png
[2017-10-11 16:33:09,552][Downloader 0] 请求 https://www.zhihu.com/collection/191640375?page=2
[2017-10-11 16:33:10,838][Downloader 0] Scheduler to Downloader队列为空，Downloader 0等待中。
[2017-10-11 16:33:10,854][zhihu_collection] 获取收藏夹[20101010 第2页]
[2017-10-11 16:33:10,938][Parser 0] 获取新任务112个。
[2017-10-11 16:33:10,938][Downloader 0] Downloader to Parser队列不为空。Downloader 0被唤醒。
[2017-10-11 16:33:10,938][Downloader 0] 请求 https://pic2.zhimg.com/50/v2-a33a10cdedce64c97ff180602ef901ed_b.jpg
[2017-10-11 16:33:10,985][Downloader 0] 请求 http://pic4.zhimg.com/v2-40d92275cb20456f4b1160d5e1fa64bf_b.jpg
......
[2017-10-11 16:33:18,761][Downloader 0] Scheduler to Downloader队列为空，Downloader 0等待中。
[2017-10-11 16:33:18,761][Downloader 0] Downloader to Parser队列不为空。Downloader 0被唤醒。
[2017-10-11 16:33:18,761][Downloader 0] Scheduler to Downloader队列为空，Downloader 0等待中。
Q
Bye Bye!


*************************************************************************************************************************
*
 Am aAzmoanz okni nkdilnedgelne(gWeinn(dWoiwnsd)o wVs2).9  Vb2u.i9l db u1i0l2d9 -100829972-9028 9
292
  命命令令行行电电子子书书制制作作软软件件

  CCooppyyrriigghhtt  AAmmaazzoonn..ccoomm  aanndd  iittss  AAffffiilliiaatteess  22001144

*************************************************************************************************************************
*
信息(prcgen):I1015: 创建 PRC 文件
信息(prcgen):I1006: 分析超链接
警告(prcgen):W14016: 没有指定封面
信息(prcgen):I1015: 创建 PRC 文件
信息(prcgen):I1006: 分析超链接
警告(prcgen):W14016: 没有指定封面
.....
```

调用KindleGen制作电子书部分为多进程，所以部分显示不正常。

本程序还没实现自动判断下载完成，当很久无请求的之后，说明队列为空，请求已完成。此时手动输入“Q”来开始制作电子书。

# 配置

配置文件在`config`目录下。配置文件其实是一个`py`文件。对于每个单独的脚本都有不同的配置文件，另有一个`config.py`通用配置文件。

为了不用转义，对于所有路径名，请使用raw字符串（r'......'或r"......"）。

## config.py

```
KINDLEGEN_PATH = r'C:\Users\web2kinle_save\kindlegen.exe'
LOG_PATH = r'C:\Users\web2kinle_save\log'
LOG_LEVEL = 'DEBUG'
```

- KINDLEGEN_PATH：KindleGen.exe程序所在路径
- LOG_PATH：日志文件
- LOG_LEVEL：日志等级

# 脚本

对于每个网站都要编写不同的脚本来获取、解析、清洗元数据，最后调用`HTML2Kindle`类的`make_opf`、`make_content`、`make_table`来制作OPF、内容、目录文件。

我们可以通过以下命令来运行脚本

```
python main.py 脚本名称 参数
```

## 现有脚本

### zhihu_collection

批量获取知乎收藏夹。如批量获取[https://www.zhihu.com/collection/191640375](https://www.zhihu.com/collection/191640375)第五页到最后一页：

```
python main.py zhihu_collection 191640375 --page=5
```

### 参数

必须参数：

- collection_num：知乎收藏夹的编号。如[https://www.zhihu.com/collection/191640375](https://www.zhihu.com/collection/191640375)的编号为“191640375”

可选参数：

- --page：开始页码数，如要从第五页开始`--page=5`

### 配置

在`config`目录下新建一个`zhihu_collection_config.py`文件。

```
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
}

SAVE_PATH = r'C:\Users\web2kinle_save'
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

##HTML

KindleGen只需要一个`<body>`标签即可。

```html
<body>
<head><meta charset="UTF-8"/></head>
内容
</body>
```

## 注意事项

本人遇过KindleGen转换出乱码的情况，后来通过“带BOM的UTF-8”编码解决。
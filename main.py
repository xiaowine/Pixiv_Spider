import datetime
from argparse import ArgumentParser
from logging import DEBUG
from os import listdir, makedirs, sep
from os.path import exists, splitext
from re import findall
from signal import SIGINT, SIGTERM, signal
from time import time
from typing import Type

from hjson import HjsonDecodeError, loads
from py7zr import SevenZipFile
from requests import Response, get as http_get, post as http_post
from requests.exceptions import ConnectionError, SSLError

from libs.Logger import Logger


class ResultData:
    status_code = 0
    content = ""
    text = ""


class Pixiv:

    def __init__(self):
        self.header = {"accept": "image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8", "referer": "https://www.pixiv.net/"}

        daily_url = "https://www.pixiv.net/ranking.php?mode=daily&content=illust&p=1&format=json"  # 每日
        weekly_url = "https://www.pixiv.net/ranking.php?mode=weekly&content=illust&p=1&format=json"  # 每周
        monthly_url = "https://www.pixiv.net/ranking.php?mode=monthly&content=illust&p=1&format=json"  # 每月
        rookie_url = "https://www.pixiv.net/ranking.php?mode=rookie&content=illust&p=1&format=json"  # 新人
        original_url = "https://www.pixiv.net/ranking.php?mode=original&p=1&format=json"  # 原创
        male_url = "https://www.pixiv.net/ranking.php?mode=male&p=1&format=json"  # 受男性欢迎
        female_url = "https://www.pixiv.net/ranking.php?mode=female&p=1&format=json"  # 受女性欢迎
        daily_r18_url = "https://www.pixiv.net/ranking.php?mode=daily_r18&p=2&format=json"  # daily_r18
        weekly_r18_url = "https://www.pixiv.net/ranking.php?mode=weekly_r18&p=1&format=json"  # weekly_r18
        male_r18_url = "https://www.pixiv.net/ranking.php?mode=male_r18&p=2&format=json"  # male_r18
        female_r18_url = "https://www.pixiv.net/ranking.php?mode=female_r18&p=2&format=json"  # female_r18

        self.image_url_template = "https://i.pximg.net/img-original/img/{}"
        self.url_dicts = {"daily": daily_url, "weekly": weekly_url, "monthly": monthly_url, "rookie": rookie_url, "original": original_url, "male": male_url, "female": female_url,
                          "daily_r18": daily_r18_url, "weekly_r18": weekly_r18_url, "male_r18": male_r18_url, "female_r18": female_r18_url}
        self.url_type_keys = list(self.url_dicts.keys())
        self.url_type_lists = list(self.url_dicts.keys())
        self.now_time = datetime.date.today().__format__(f"%Y{sep}%m{sep}%d")
        self.now_path = ""

        self.response_handle = None
        self.downloading = False

        self.http_proxy = {}
        self.is_zip = False
        self.spider_type = "daily"
        self.is_debug = False
        self.send = False
        self.channel_id = 0
        self.bot_token = ""
        self.log = Logger()

    def argparse(self) -> None:
        parser = ArgumentParser()
        proxy_help = """Set the proxy in json format, for example: {"http": "socks5://192.168.1.3:20170", 
                                   "https":"socks5://192.168.1.3:20170"} """
        compress_help = """Compress and package the crawled pictures"""
        type_help = self.url_type_lists.__str__()
        debug_help = "Whether to output debug content"
        send_help = "Send to Telegram channel"
        channel_id_help = "Telegram channel ID"
        bot_token_help = "Telegram channel ID"
        proxy_default = {}
        compress_default = False
        type_default = "daily"
        debug_default = False
        send_default = False
        channel_id_default = 0
        bot_token_default = 0
        parser.add_argument("-p", "--proxy", help=proxy_help, type=str, nargs='?', const=proxy_default, default=proxy_default)
        parser.add_argument("-c", "--compress", help=compress_help, type=bool, nargs='?', const=compress_default, default=compress_default)
        parser.add_argument("-t", "--type", help=type_help, type=str, nargs='?', const=type_default, default=type_default)
        parser.add_argument("-d", "--debug", help=debug_help, type=bool, nargs='?', const=debug_default, default=debug_default)
        parser.add_argument("-s", "--send", help=send_help, type=bool, nargs='?', const=send_default, default=send_default)
        parser.add_argument("-i", "--channelid", help=channel_id_help, type=int, nargs='?', const=channel_id_default, default=channel_id_default)
        parser.add_argument("-b", "--bottoken", help=bot_token_help, type=str, nargs='?', const=bot_token_default, default=bot_token_default)
        args = parser.parse_args()
        try:
            self.http_proxy = loads(args.proxy.__str__())
        except HjsonDecodeError:
            self.log.warn("代理参数错误")
            break_program()
        self.is_zip = args.compress
        if args.type in self.url_type_lists:
            self.spider_type = args.type
        else:
            self.log.warn("爬取类型参数错误")
            break_program()

        self.is_debug = args.debug
        if args.debug:
            self.log.set_level(DEBUG)
        self.send = args.send
        self.channel_id = args.channelid
        self.bot_token = args.bottoken

        self.now_path = f"photo{sep}{self.spider_type}{sep}{self.now_time}"
        is_exist_dirs(self.now_path)
        is_exist_dirs("zips")

    def show_parameter(self):
        self.log.debug(f"代理参数：{self.http_proxy}")
        self.log.debug(f"是否打包：{self.is_debug}")
        self.log.debug(f"爬取类型参数：{self.spider_type}")
        self.log.debug(f"Debug：{self.is_debug}")
        self.log.debug(f"发送到Telegram channel：{self.send}")
        self.log.debug(f"Telegram channel id：{self.channel_id}")
        self.log.debug(f"Telegram  bot token：{self.bot_token.__str__()[:8]}")

    def main(self) -> None:

        location = [splitext(i)[0] for i in listdir(self.now_path)]
        self.log.debug(location)
        urls = self.url_dicts[self.spider_type]
        self.log.info(f"开始获取 {self.spider_type} 排行榜")
        response = self.get(urls)
        self.log.debug(response.text)
        self.log.info("获取结束，开始处理排行榜内容")
        self.log.debug(f"请求响应码：{response.status_code}")
        if response.status_code != 200:
            self.log.info("排行榜数据异常")
            break_program()
        self.log.info("实体化排行榜")
        try:
            self.response_handle = loads(response.text)
        except HjsonDecodeError as e:
            self.log.info(f"实体化排行榜异常：{e.msg}/t response：{response.text}")
            break_program()

        for index, i in enumerate(self.response_handle['contents'][::-1]):
            self.log.info("-" * 40)
            self.log.info("-" * 40)
            # self.log.info(i['url'])
            self.log.info(f"开始处理排行榜 第 {40-index} 名")
            image_url_re_dicts = findall("https://i.pximg.net/c/240x480/img-master/img/(.*)_p.*_master1200.jpg",
                                         i['url'])
            self.log.info(f"共 {i['illust_page_count']} 张图")
            for ii in range(int(i['illust_page_count'])):
                self.log.info("-" * 20)
                self.log.info(f"处理 第 {40-index} 名 第 {ii + 1} 张图")
                image_url_re = image_url_re_dicts[0]
                image_name = f'[{i["user_name"]}] {i["title"]}_p{ii}' \
                    .replace("<", "") \
                    .replace(">", "") \
                    .replace("|", "") \
                    .replace("\\", "") \
                    .replace("/", "") \
                    .replace("\"", "'") \
                    .replace(":", "") \
                    .replace("*", "")
                if image_name in location:
                    self.log.info("图片已存在")
                else:
                    for scheme in ["png", "jpg"]:
                        self.log.info(f"尝试下载此图的 {scheme}")
                        self.log.info(f"{image_url_re}_p{ii}.{scheme}")
                        image_url = self.image_url_template.format(f"{image_url_re}_p{ii}.{scheme}")
                        image = self.get(image_url)
                        if image.status_code == 200:
                            self.log.info(f"开始新线程下载此图的 {scheme}")
                            self.log.info(f"此图链接为 {image_url}")
                            self.write_file(image.content, image_name, scheme)
                            self.downloading = True
                            break
                        else:
                            self.log.info(f"尝试下载此图的 {scheme} 失败")

        if self.is_zip:
            self.log.info("开始打包")
            with SevenZipFile(f"zips{sep}Compressed.7z", 'w') as archive:
                archive.writeall(self.now_path)

    def get(self, url):
        try:
            return http_get(url, proxies=self.http_proxy, headers=self.header)
        except SSLError:
            self.log.info("get请求错误")
            return ResultData
            pass
        except ConnectionError:
            self.log.info("get连接失败")
            return ResultData
            pass

    def post(self, url, data, files) -> Response | Type[ResultData]:
        try:
            return http_post(url, proxies=self.http_proxy, headers=self.header, data=data, files=files)
        except SSLError:
            self.log.info("post请求错误，跳过此次")
            return ResultData
            pass
        except ConnectionError:
            self.log.info("post连接失败，跳过此次")
            return ResultData
            pass

    # @new_thread
    def write_file(self, data, name, suffix) -> None:
        with open(f"{self.now_path}{sep}{name}.{suffix}", mode='wb+') as f:
            f.write(data)
            self.log.info(f'写入图片成功！文件名 {name}.{suffix}')
            self.downloading = False
            f.seek(0)
            if self.send:
                self.log.info(f"开始发送到Telegram channel：{self.channel_id}")
                file = {f"{name}.{suffix}": f.read()}
                url = f'https://api.telegram.org/bot{self.bot_token}/sendMediaGroup'
                data = {'chat_id': self.channel_id, 'media': '[{"type": "document", "media": "attach://%s", "parse_mode": "MarkdownV2", "caption": ""}]' % f"{name}.{suffix}"}
                # file = {"photo": f.read()}
                # url = f'https://api.telegram.org/bot{self.bot_token}/sendPhoto'
                # data = {'chat_id': self.channel_id}
                req = self.post(url, data=data, files=file)
                if req.status_code == 200:
                    self.log.info("发送到Telegram channel 成功")
                    self.log.debug(req.text)
                else:
                    self.log.info(f"Telegram channel 失败：{req.text}")


def break_program(*arg) -> None:
    pixiv.log.info("中断操作，程序退出")
    exit(0)


def is_exist_dirs(dir_path) -> None:
    if not exists(dir_path):
        makedirs(dir_path)


if __name__ == '__main__':
    start_time = time()
    signal(SIGINT, break_program)
    signal(SIGTERM, break_program)
    pixiv = Pixiv()
    pixiv.argparse()
    pixiv.show_parameter()
    pixiv.main()
    pixiv.log.info(f"爬取结束,用时：{time() - start_time}s")

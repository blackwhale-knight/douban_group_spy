#!/usr/bin/env python
# coding=utf-8

import os
import re
import random
import time
from datetime import datetime

from bs4 import BeautifulSoup

from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import make_aware

from douban_group_spy.const import USER_AGENT, DATETIME_FORMAT, DATE_FORMAT

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'douban_group_spy.settings')
import django
django.setup()

import click
import requests
import logging

from douban_group_spy.settings import DOU_LIST_BASE_URL, DOUBAN_BASE_HOST, COOKIE
from douban_group_spy.models import Doulist, DoulistPost


lg = logging.getLogger(__name__)


def process_doulist_posts(posts):
    for t in posts:
        post = DoulistPost.objects.filter(post_id=t['id']).first()
        # ignore same id
        if post:
            lg.info(f'[post] update existing post: {post.post_id}')
            post.updated = make_aware(datetime.strptime(t['updated'], DATETIME_FORMAT))
            post.title = t['title']
            post.save(force_update=['updated', 'title'])
            continue
        post = DoulistPost(
            post_id=t['id'],
            alt=t['alt'],
            title=t['title'], content=t['content'], comments=t['comments'],
            photo_list=t['photos'],
            created=make_aware(datetime.strptime(t['created'], DATETIME_FORMAT)),
            updated=make_aware(datetime.strptime(t['updated'], DATETIME_FORMAT))
        )
        post.save(force_insert=True)
        lg.info(f'[post] save doulist post: {post.post_id}')


def crawl(doulist_id):
    lg.info(f'start crawling doulist: {doulist_id}')
    try:
        doulist = Doulist.objects.get(id=doulist_id)
    except ObjectDoesNotExist:
        lg.info(DOU_LIST_BASE_URL.format(DOUBAN_BASE_HOST, doulist_id))
        html = requests.get(DOU_LIST_BASE_URL.format(DOUBAN_BASE_HOST, doulist_id), headers={'User-Agent': USER_AGENT, 'Cookie': COOKIE}).text
        dl_info = BeautifulSoup(html,'lxml')
        lg.info(f'Getting doulist: {doulist_id} successful')
        doulist = Doulist(
            id=doulist_id,
            name=dl_info.select_one('h1').get_text().strip(),
            alt=f'https://www.douban.com/doulist/{doulist_id}',
        )
        doulist.save(force_insert=True)

    kwargs = {
        'url': DOU_LIST_BASE_URL.format(DOUBAN_BASE_HOST, doulist_id),
        'headers': {'User-Agent': USER_AGENT,'Cookie': COOKIE}
    }
    req = getattr(requests, 'get')(**kwargs)
    lg.info(f'getting: {req.url}, status: {req.status_code}')
    # if 400, switch host
    if req.status_code != 200:
        # host = next(douban_base_host)
        kwargs['url'] = DOU_LIST_BASE_URL.format(DOUBAN_BASE_HOST, doulist_id)
        lg.info(f'Rate limit, switching host')
        req = getattr(requests, 'get')(**kwargs)
        lg.info(f'getting doulist: {req.url}, status: {req.status_code}')
        if req.status_code != 200:
            lg.warning(f'Fail to getting: {req.url}, status: {req.status_code}')

    dl_info = BeautifulSoup(req.text,'lxml')
    pages=int(dl_info.find('span', {'class' : 'thispage'}).get('data-total-page'))

    for p in range(pages):
        time.sleep(random.randint(5,8))
        # host = next(douban_base_host)
        kwargs = {
            'url': DOU_LIST_BASE_URL.format(DOUBAN_BASE_HOST, doulist_id),
            'params': {'start': p*25},
            'headers': {'User-Agent': USER_AGENT,'Cookie': COOKIE}
        }
        req = getattr(requests, 'get')(**kwargs)
        lg.info(f'getting: {req.url}, status: {req.status_code}')
        # if 400, switch host
        if req.status_code != 200:
            # host = next(douban_base_host)
            kwargs['url'] = DOU_LIST_BASE_URL.format(DOUBAN_BASE_HOST, doulist_id)
            lg.info(f'Rate limit, switching host')
            req = getattr(requests, 'get')(**kwargs)
            lg.info(f'getting group: {req.url}, status: {req.status_code}')
            if req.status_code != 200:
                lg.warning(f'Fail to getting: {req.url}, status: {req.status_code}')
                continue
                
        soup = BeautifulSoup(req.text,'lxml')        
        posts=[]
        for row in soup.find_all("div", {"class": "bd doulist-note"}):
            link=row.select_one('div[class="title"] a')
            link_href=link["href"]
            post_detail_html = requests.get(link_href, headers={'User-Agent': USER_AGENT, 'Cookie': COOKIE}).text
            post_detail = BeautifulSoup(post_detail_html,'lxml')
            try:
                post_content=post_detail.select_one('div[class="topic-content"]')
                post_comments=post_detail.find_all("p", class_='reply-content')
                comments=[]
                for comment in post_comments:
                    comments.append(comment.get_text())
                post_photos=[]
                for photo_row in post_content.select('img'):
                    post_photos.append(photo_row['src'])  
            except:
                continue
   
            result={}
            result['id']=int(re.findall(r"https://www.douban.com/group/topic/(.+?)/",link_href)[0])
            result['title']=post_detail.title.get_text().strip()
            result['content']=post_content.get_text().strip()
            result['comments']=comments
            result['alt']=link_href
            result['photos']=post_photos
            result['created']=post_detail.select_one('.create-time').get_text()
            result['updated']=post_detail.select_one('.create-time').get_text()

            posts.append(result)
        process_doulist_posts(posts)    


@click.command(help='example: python3 doulist_crawler.py -dl 154060327')
@click.option('--doulists', '-dl', help='doulist id', multiple=True, required=True, type=str)
@click.option('-v', help='Show debug info', is_flag=True)
def main(doulists: tuple, v):
    if v:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    while True:
        for dl_id in doulists:
            crawl(dl_id)


if __name__ == '__main__':
    main()

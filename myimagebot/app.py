# -*- coding: utf8 -*-

from flask import Flask, request, Response
from myimagebot import config
import json
import urllib
import requests
import os

app = Flask('MyImageBot')
app.config.from_object(config)


@app.route('/')
def index():
    url = 'https://apis.daum.net/mypeople/group/send.json'
    data = {
        'groupId': 'GID_yl1J2',
        'content': 'Hello~'
    }
    r = requests.post(url, data)
    return r.text


@app.route('/callback', methods=['POST'])
def callback():
    print json.dumps(request.form, indent=4)
    print request.cookies

    content = request.form.get('content')
    if 'myp_pci' in content:
        url = 'https://apis.daum.net/mypeople/file/download.json'
        url += '?apikey=' + config.API_KEY
        url += '&fileId=' + content
        filename = content.split(':')[1] + '.png'
        path = os.path.abspath(
            os.path.join(app.root_path, '../var/upload', filename)
        )
        urllib.urlretrieve(url, path)
        print 'Saved:', filename

        group_id = request.form.get('groupId')
        if group_id:
            url = 'https://apis.daum.net/mypeople/group/send.json'
            url += '?apikey=' + config.API_KEY
            data = {
                'groupId': group_id,
                'content': 'http://myimagebot.xoul.kr/upload/' + filename
            }
            r = requests.post(url, data)
            print r.text
            return r.text
        else:
            buddy_id = request.form.get('buddyId')
            url = 'https://apis.daum.net/mypeople/buddy/send.json'
            url += '?apikey=' + config.API_KEY
            data = {
                'buddyId': buddy_id,
                'content': 'http://myimagebot.xoul.kr/upload/' + filename
            }
            r = requests.post(url, data)
            print r.text
            return r.text
    return Response('')

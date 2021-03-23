# -*- coding: utf-8 -*-
import sys
import json
import uuid
import yaml
import base64
import requests
from pyDes import des, CBC, PAD_PKCS5
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from urllib3.exceptions import InsecureRequestWarning
import time
from dingtalkchatbot.chatbot import DingtalkChatbot


debug = False
if debug:
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)



def getYmlConfig(yaml_file='config.yml'):
    file = open(yaml_file, 'r', encoding="utf-8")
    file_data = file.read()
    file.close()
    config = yaml.load(file_data, Loader=yaml.FullLoader)
    return dict(config)

config = getYmlConfig(yaml_file='config.yml')



def getTimeStr():
    utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    bj_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
    return bj_dt.strftime("%Y-%m-%d %H:%M:%S")



def log(content):
    print(getTimeStr() + ' ' + str(content))
    sys.stdout.flush()



def getCpdailyApis(user):
    apis = {}
    user = user['user']
    idsUrl = 'https://uis.nbu.edu.cn/authserver'
    ampUrl = 'https://ehall.nbu.edu.cn/newmobile/client'
    ampUrl2 = 'https://nbu.campusphere.net/wec-portal-mobile/client'
    if 'campusphere' in ampUrl or 'cpdaily' in ampUrl:
        parse = urlparse(ampUrl)
        host = parse.netloc
        apis[
            'login-url'] = idsUrl + '/login?service=' + parse.scheme + r"%3A%2F%2F" + host + r'%2Fportal%2Flogin'
        apis['host'] = host
    if 'campusphere' in ampUrl2 or 'cpdaily' in ampUrl2:
        parse = urlparse(ampUrl2)
        host = parse.netloc
        apis[
            'login-url'] = idsUrl + '/login?service=' + parse.scheme + r"%3A%2F%2F" + host + r'%2Fportal%2Flogin'
        apis['host'] = host
    log(apis)
    return apis




def getSession(user, apis):
    user = user['user']
    params = {
        'login_url': 'https://uis.nbu.edu.cn/authserver/login?service=https%3A%2F%2Fnbu.campusphere.net%2Fportal%2Flogin',
        'needcaptcha_url': '',
        'captcha_url': '',
        'username': user['username'],
        'password': user['password']
    }

    cookies = {}
    res = requests.post(url=config['login']['api'], data=params, verify=not debug)
    cookieStr = str(res.json()['cookies'])
    log(cookieStr)
    if cookieStr == 'None':
        log(res.json())
        exit(-1)

    for line in cookieStr.split(';'):
        name, value = line.strip().split('=', 1)
        cookies[name] = value
    session = requests.session()
    session.cookies = requests.utils.cookiejar_from_dict(cookies, cookiejar=None, overwrite=True)
    return session



def getUnSignedTasks(session, apis):
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'content-type': 'application/json',
        'Accept-Encoding': 'gzip,deflate',
        'Accept-Language': 'zh-CN,en-US;q=0.8',
        'Content-Type': 'application/json;charset=UTF-8'
    }
    # 第一次请求每日签到任务接口，主要是为了获取MOD_AUTH_CAS
    res = session.post(
        url='https://{host}/wec-counselor-sign-apps/stu/sign/getStuSignInfosInOneDay'.format(host=apis['host']),
        headers=headers, data=json.dumps({}), verify=not debug)
    # 第二次请求每日签到任务接口，拿到具体的签到任务
    res = session.post(
        url='https://{host}/wec-counselor-sign-apps/stu/sign/getStuSignInfosInOneDay'.format(host=apis['host']),
        headers=headers, data=json.dumps({}), verify=not debug)
    if len(res.json()['datas']['unSignedTasks']) < 1:
        log('当前没有未签到任务')
        exit(-1)

    latestTask = res.json()['datas']['unSignedTasks'][0]
    return {
        'signInstanceWid': latestTask['signInstanceWid'],
        'signWid': latestTask['signWid']
    }



def getDetailTask(session, params, apis):
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'content-type': 'application/json',
        'Accept-Encoding': 'gzip,deflate',
        'Accept-Language': 'zh-CN,en-US;q=0.8',
        'Content-Type': 'application/json;charset=UTF-8'
    }
    res = session.post(
        url='https://{host}/wec-counselor-sign-apps/stu/sign/detailSignInstance'.format(host=apis['host']),
        headers=headers, data=json.dumps(params), verify=not debug)
    data = res.json()['datas']
    return data



def fillForm(task, session, user, apis):
    user = user['user']
    form = {}
    form['signPhotoUrl'] = ''
    if task['isNeedExtra'] == 1:
        extraFields = task['extraField']
        defaults = config['cpdaily']['defaults']
        extraFieldItemValues = []
        for i in range(0, len(extraFields)):
            default = defaults[i]['default']
            extraField = extraFields[i]
            if default['title'] != extraField['title']:
                log('第%d个默认配置项错误，请检查' % (i + 1))
                exit(-1)
            extraFieldItems = extraField['extraFieldItems']
            for extraFieldItem in extraFieldItems:
                if extraFieldItem['content'] == default['value']:
                    extraFieldItemValue = {'extraFieldItemValue': default['value'],
                                           'extraFieldItemWid': extraFieldItem['wid']}
                    extraFieldItemValues.append(extraFieldItemValue)
        form['extraFieldItems'] = extraFieldItemValues
        form['signInstanceWid'] = task['signInstanceWid']
        form['longitude'] = user['lon']
        form['latitude'] = user['lat']
        form['isMalposition'] = task['isMalposition']
        form['position'] = user['address']
        form['uaIsCpadaily'] = True
        return form




# 钉钉机器人通知
def sendDingDing(msg, token, secret):
    log('正在发送钉钉机器人通知...')
    shijian = getTimeStr() + '\n'
    webhook = 'https://oapi.dingtalk.com/robot/send?access_token={0}'.format(token)
    secret = '{0}'.format(secret)
    xiaoding = DingtalkChatbot(webhook, secret=secret)  # 方式二：勾选“加签”选项时使用（v1.5以上新功能）
    xiaoding.send_text(str(shijian) + str(msg), is_at_all=False)


def DESEncrypt(s, key='b3L26XNL'):
    key = key
    iv = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    k = des(key, CBC, iv, pad=None, padmode=PAD_PKCS5)
    encrypt_str = k.encrypt(s)
    return base64.b64encode(encrypt_str).decode()



def submitForm(session, user, form, apis):
    user = user['user']
    extension = {
        "lon": user['lon'],
        "model": "OPPO R11 Plus",
        "appVersion": "8.1.14",
        "systemVersion": "4.4.4",
        "userId": user['username'],
        "systemName": "android",
        "lat": user['lat'],
        "deviceId": str(uuid.uuid1())
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 4.4.4; OPPO R11 Plus Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/33.0.0.0 Safari/537.36 okhttp/3.12.4',
        'CpdailyStandAlone': '0',
        'extension': '1',
        'Cpdaily-Extension': DESEncrypt(json.dumps(extension)),
        'Content-Type': 'application/json; charset=utf-8',
        'Accept-Encoding': 'gzip',
        'Connection': 'Keep-Alive'
    }
    res = session.post(url='https://{host}/wec-counselor-sign-apps/stu/sign/submitSign'.format(host=apis['host']),
                       headers=headers, data=json.dumps(form), verify=not debug)
    message = res.json()['message']
    if message == 'SUCCESS':
        log('自动签到成功')
        sendDingDing('自动签到成功', user['token'], user['secret'])
    else:
        log('自动签到失败，原因是：' + message)
        sendDingDing('自动签到失败，原因是：' + message, user['token'], user['secret'])
        exit(-1)




def main():
    for user in config['users']:
        apis = getCpdailyApis(user)
        session = getSession(user, apis)
        params = getUnSignedTasks(session, apis)
        task = getDetailTask(session, params, apis)
        form = fillForm(task, session, user, apis)
        submitForm(session, user, form, apis)
        


def main_handler(event, context):
    try:
        main()
    except Exception as e:
        raise e
    else:
        return 'success'


if __name__ == '__main__':
    print('-----------------------------------------------------------------------------')
    print(main_handler({}, {}))

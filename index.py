import sys
import requests
import json
import uuid
import base64
from pyDes import des, CBC, PAD_PKCS5
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import oss2
import yaml
import urllib3


urllib3.disable_warnings()


def getYmlConfig(yaml_file='config.yml'):
    file = open(yaml_file, 'r', encoding="utf-8")
    file_data = file.read()
    file.close()
    config = yaml.load(file_data, Loader=yaml.FullLoader)
    return dict(config)

config = getYmlConfig()

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
    schools = requests.get(url='https://mobile.campushoy.com/v6/config/guest/tenant/list',verify = False).json()['data']
    flag = True
    for one in schools:
        if one['name'] == user['school']:
            if one['joinType'] == 'NONE':
                log(user['school'] + ' 未加入今日校园或者学校全称错误')
                exit(-1)
            flag = False
            params = {
                'ids': one['id']
            }
            res = requests.get(url='https://mobile.campushoy.com/v6/config/guest/tenant/info', params=params ,verify = False)
            data = res.json()['data'][0]
            idsUrl = data['idsUrl']
            ampUrl = data['ampUrl']
            ampUrl2 = data['ampUrl2']
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
            break
    if flag:
        log(user['school'] + ' 未加入今日校园或者学校全称错误')
        exit(-1)
    log(apis)
    return apis


def getSession(user, apis):
    user = user['user']
    params = {
        'login_url': apis['login-url'],
        'needcaptcha_url': '',
        'captcha_url': '',
        'username': user['username'],
        'password': user['password']
    }

    cookies = {}

    res = requests.post(url=config['login']['api'], data=params)

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


#获取未签到任务
def getUnSignedTasks(session, apis, user):
    user = user['user']
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'content-type': 'application/json',
        'Accept-Encoding': 'gzip,deflate',
        'Accept-Language': 'zh-CN,en-US;q=0.8',
        'Content-Type': 'application/json;charset=UTF-8'
    }

    res = session.post(
        url='https://{host}/wec-counselor-sign-apps/stu/sign/getStuSignInfosInOneDay'.format(host=apis['host']),
        headers=headers, data=json.dumps({}) ,verify = False)

    res = session.post(
        url='https://{host}/wec-counselor-sign-apps/stu/sign/getStuSignInfosInOneDay'.format(host=apis['host']),
        headers=headers, data=json.dumps({}) ,verify = False) 
    if len(res.json()['datas']['leaveTasks']) < 1: 
        log('当前没有未签到任务')
        sendMessage('获取未签到任务失败！', user['server_key'])
        exit(-1)
    log(res.json())
    latestTask = res.json()['datas']['leaveTasks'][0] 
    return {
        'signInstanceWid': latestTask['signInstanceWid'],
        'signWid': latestTask['signWid']
    }

#获取未签到任务详情
def getDetailTask(session, params, apis ,user):
    user = user['user']
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
        headers=headers, data=json.dumps(params))
    if (res.status_code == 200):
        log('获取任务详情成功')
        data = res.json()['datas']
        return data
    else:
        sendMessage('获取任务详情失败！', user['server_key'])
        exit(-1)




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
                       headers=headers, data=json.dumps(form))
    message = res.json()['message']
    if message == 'SUCCESS':
        sendMessage('自动签到成功', user['server_key'])
    else:
        sendMessage('自动签到失败，原因是：' + message, user['server_key'])


# 发送微信通知
def sendMessage(msg,serverkey):
    serverkey = serverkey
    url = "https://sc.ftqq.com/{serverkey}.send".format(serverkey = serverkey)
    payload={'text': msg,
    'desp': '本脚本开源免费使用 By https://github.com/PwnerZhang/Auto_Sign_For_NBU'}
    files=[]
    headers = {
    'Cookie': ''
    }
    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    log('Severchan运行结果:' + str(response.text))



# 主函数
def main():
    for user in config['users']:
        apis = getCpdailyApis(user)
        session = getSession(user, apis)
        params = getUnSignedTasks(session, apis, user)
        task = getDetailTask(session, params, apis)
        form = fillForm(task, session, user, apis)
        submitForm(session, user, form, apis)


# 启动函数
def main_handler(event, context):
    try:
        main()
        return 'success'
    except:
        return 'fail'


if __name__ == '__main__':
    main()
### 更新日志

> 如果Linux下执行代码报错 FileNotFoundError: [Errno 2] No such file or directory: 'config.yml' ，请将`index.py`中`config.yml`的路径改为绝对路径。

- **2021年3月23日：**

  - PushPlus功能波动，更化成钉钉机器人通知（钉钉机器人密钥获取请自行参考官方文档）

  - 修复接口错误，默认配置为`宁波大学`，其他大学请自行在**index.py**中设定

    > 设定办法：
    >
    > 1. 访问 https://mobile.campushoy.com/v6/config/guest/tenant/list 获取本校`id`
    > 2. 访问 https://mobile.campushoy.com/v6/config/guest/tenant/info?ids=学校id
    > 3. 获取`idsUrl`、`ampUrl`、`ampUrl2`填入**index.py**
    > 4. `login_url`请自行设定

- **2021年1月30日：**
  
  - Serverchan近期服务不稳定，将微信通知改成更稳定的PushPlus
  
- **2021年1月28日：**
  
  - 修复离校签到改成常规签到了，已经修复，下载新的`index.py`替换原来的`index.py`即可，配置文件`config.yml`不需要变动。
  
- **2021年1月27日：**
  - 移除了冗余代码，适配了宁波大学的校外每日签到任务；
  - 修复了今日校园更换接口导致原有接口失效的问题；
  - 修复了今日校园修改生成算法的密钥导致`Cpdaily-Extension`失效的问题；
  - 移除已失效的邮件通知功能，改为微信通知，需要调用Serverchan，配置方法详见注释；
  - 完善了容错机制，增加了两处可能产生错误之处的告警通知；
  - 完善了请求方式，不采用强制SSL；
  - 完善了日志记录，去除了SSL警告；
  - 完善了配置文件`config.yml`的注释，对小白更友好。

### 使用方法

[今日校园自动打卡 NBU](https://pwner.cn/posts/7fdc2e69.html)

### 核心功能

1. 获取未签到任务
2. 获取未签到任务详
3. 提交签到表单

如果你也想要尝试自己抓包编写代码，提供思路供参考。

![image-20210127173416544](https://img.xiehestudio.com/pic_go/20210127173416.png)

### 关于

本项目参考[ZimoLoveShuang/auto-sign](https://github.com/ZimoLoveShuang/auto-sign)，感谢子墨提供的模拟登陆模块。

本项目仅供学习交流使用，请勿用于商业用途。如果发现有商用行为，将关闭模拟登录接口。


import sys
from pathlib import Path
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# 将项目根目录（MemeGenerator/）添加到 Python 路径
project_root = Path(__file__).parent.parent  # 假设 main.py 在 src/ 下
sys.path.append(str(project_root))

import time
# import memeFactory
import twitterApi
from loguru import logger
import config
import json
import requests
import threading
import re
import random
import os
import logging  # 导入标准库logging模块
from io import StringIO  # 导入StringIO

# 首先移除默认的日志处理器
logger.remove()

def find_next_mention(text, target):
    # 匹配 @target 后第一个 @mention
    pattern = rf"@{target}[^@]*(@\w+)(?=[\s\n\t]|$)"
    match = re.search(pattern, text)
    return match.group(-1)[1:] if match else None

def get_ai_response(user_name, tweet_content):
    """
    使用AI API生成对推文的回复
    
    Args:
        user_name (str): 发推文用户的名称
        tweet_content (str): 推文内容
    
    Returns:
        str: AI生成的回复，如果API调用失败则返回默认回复
    """
    default_reply = "Hold on, hold on! Why the fuck are you rushing me? I'm fucking swamped here!"
    alternative_replies = [
        "You're fucking kidding me, right? Give me a god damn break here!",
        "Oh, for fuck's sake! I've got 99 problems and you just became all of them!",
        "Jesus Christ, what do you want from me? I'm drowning in shit over here!",
        "I'm going to need you to back the fuck off for just one minute, ok?",
        "Well excuse the fuck out of me for not responding instantly! What am I, your personal assistant?",
        "Look who's demanding attention! Wait your fucking turn like everyone else."
    ]
    
    # 最大重试次数
    max_retries = 2
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            # 使用prompt模板填充用户信息和推文内容
            prompt = config.PROMPT_TEMPLATE.format(
                user_name=user_name,
                tweet_content=tweet_content
            )
            
            # 构建API请求payload
            payload = {
                "model": config.AI_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "max_tokens": config.AI_MAX_TOKENS,
                "enable_thinking": False,
                "min_p": config.AI_MIN_P,
                "temperature": config.AI_TEMPERATURE + (retry_count * 0.1),  # 每次重试增加一点温度
                "frequency_penalty": config.AI_FREQUENCY_PENALTY,
                "n": 1,
                "response_format": {"type": "text"}
            }
            
            headers = {
                "Authorization": f"Bearer {config.AI_API_TOKEN}",
                "Content-Type": "application/json"
            }
            
            # 发送请求到AI API
            logger.debug(f"向AI API发送请求处理推文(尝试{retry_count+1}/{max_retries+1}): {tweet_content}")
            logger.debug(f"API请求参数: {payload}")
            response = requests.post(config.AI_API_URL, json=payload, headers=headers, timeout=30)
            
            # 检查响应状态
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"API原始响应: {result}")
                
                # 从响应中提取AI生成的回复文本
                ai_reply = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.debug(f"提取的AI回复: '{ai_reply}'")
                
                # 检查回复是否为空
                if not ai_reply or len(ai_reply.strip()) == 0:
                    if retry_count < max_retries:
                        logger.warning(f"AI返回了空回复，第{retry_count+1}次重试")
                        retry_count += 1
                        continue
                    else:
                        logger.warning(f"AI返回了空回复，已达到最大重试次数，使用随机备选回复")
                        return random.choice(alternative_replies)
                
                # 检查回复是否包含中文字符
                has_chinese = any('\u4e00' <= char <= '\u9fff' for char in ai_reply)
                if has_chinese:
                    if retry_count < max_retries:
                        logger.warning(f"AI回复包含中文字符，第{retry_count+1}次重试。原回复: {ai_reply}")
                        retry_count += 1
                        continue
                    else:
                        logger.warning(f"AI回复仍然包含中文字符，已达到最大重试次数，使用随机备选回复")
                        return random.choice(alternative_replies)
                    
                # 检查回复语言 - 使用简单的启发式方法
                # 如果回复包含常见的中文标点或特定的中文短语，认为是中文
                chinese_markers = ['。', '，', '、', '：', '；', '！', '？', '谢谢', '您好', '请', '的']
                if any(marker in ai_reply for marker in chinese_markers):
                    if retry_count < max_retries:
                        logger.warning(f"AI回复可能是中文，第{retry_count+1}次重试。原回复: {ai_reply}")
                        retry_count += 1
                        continue
                    else:
                        logger.warning(f"AI回复仍然可能是中文，已达到最大重试次数，使用随机备选回复")
                        return random.choice(alternative_replies)
                
                logger.info(f"成功获取有效的AI回复: '{ai_reply}'")
                return ai_reply
            else:
                logger.error(f"API请求失败，状态码 {response.status_code}: {response.text}")
                if retry_count < max_retries:
                    logger.warning(f"API请求失败，第{retry_count+1}次重试")
                    retry_count += 1
                    time.sleep(1)  # 失败后等待1秒再重试
                    continue
                else:
                    logger.warning(f"API请求失败，已达到最大重试次数，使用随机备选回复")
                    return random.choice(alternative_replies)
                
        except Exception as e:
            logger.error(f"调用AI API时出错: {str(e)}")
            if retry_count < max_retries:
                logger.warning(f"发生异常，第{retry_count+1}次重试")
                retry_count += 1
                time.sleep(1)  # 失败后等待1秒再重试
                continue
            else:
                logger.warning(f"发生异常，已达到最大重试次数，使用随机备选回复")
                return random.choice(alternative_replies)
    
    # 如果走到这里（正常情况不会），也返回随机备选回复
    return random.choice(alternative_replies)

def download_avatar(screen_name):
    newurl = xapi.get_user_avatar_url(screen_name)
    old = avatardata.get(screen_name,None)
    if old:
        # 曾有记录
        oldurl = old['url']
        if oldurl == newurl:
            return old['path']
    response = requests.get(newurl, stream=True)
    # 要么没记录，要么更新头像了
    if response.status_code == 200:
        timestamp = int(time.time())
        file_path = f'lib/rawAvatar/{screen_name}_{timestamp}.jpg'
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        avatardata[screen_name] = {'url': newurl, 'path': file_path, 'proceed':[], 'timestamp':timestamp}
        with open('save/avatar.json', 'w') as f:
            json.dump(avatardata, f, indent=4)
        return file_path
    else:
        logger.error(f"Failed to download avatar for {screen_name}, status code: {response.status_code}")
        return None

def create_meme(screen_name, meme_name):
    his = avatardata.get(screen_name,None)
    if his:
        # 曾有记录
        proceed = his['proceed']
        if meme_name in proceed:
            timestamp = his['timestamp']
            return rf'lib/{meme_name}/{screen_name}_{timestamp}.{MEMES[meme_name]}'
    # 要么没记录，要么没做过这种
    avatar_path = download_avatar(screen_name)
    timestamp = avatardata[screen_name]['timestamp']
    if meme_name == 'petpet':
        meme_path = memeFactory.generate_meme(meme_name,screen_name,timestamp,MEMES[meme_name],[avatar_path],args={"circle": True})
        avatardata[screen_name]['proceed'].append(meme_name)
        return meme_path
    if meme_name in ['clown_mask','gun']:
        meme_path = memeFactory.generate_meme(meme_name,screen_name,timestamp,MEMES[meme_name],[avatar_path],args={"mode": random.choice(['behind','front'])})
        avatardata[screen_name]['proceed'].append(meme_name)
        return meme_path
    if meme_name == 'bubble_tea':
        meme_path = memeFactory.generate_meme(meme_name,screen_name,timestamp,MEMES[meme_name],[avatar_path],args={"position": random.choice(['right','left','both'])})
        avatardata[screen_name]['proceed'].append(meme_name)
        return meme_path
    if meme_name == 'kaleidoscope':
        meme_path = memeFactory.generate_meme(meme_name,screen_name,timestamp,MEMES[meme_name],[avatar_path],args={"circle": random.choice([True,False])})
        avatardata[screen_name]['proceed'].append(meme_name)
        return meme_path
    if meme_name == 'mourning':
        meme_path = memeFactory.generate_meme(meme_name,screen_name,timestamp,MEMES[meme_name],[avatar_path],args={"black": random.choice([True,False])})
        avatardata[screen_name]['proceed'].append(meme_name)
        return meme_path
    if meme_name == 'pixelate':
        meme_path = memeFactory.generate_meme(meme_name,screen_name,timestamp,MEMES[meme_name],[avatar_path],args={"number": random.randint(10,300)})
        avatardata[screen_name]['proceed'].append(meme_name)
        return meme_path
    if meme_name == 'read_book':
        meme_path = memeFactory.generate_meme(meme_name,screen_name,timestamp,MEMES[meme_name],[avatar_path],texts_lst=[random.choice(['Way2Rich','Way2Poor','Way2Web3','Way2Heaven','Way2Hell'])])
        avatardata[screen_name]['proceed'].append(meme_name)
        return meme_path
    if meme_name == 'wish_fail':
        meme_path = memeFactory.generate_meme(meme_name,screen_name,timestamp,MEMES[meme_name],texts_lst=[random.choice(['GoRich','GoPoor','BTCgo0','BNBgo0','ETH>BTC'])])
        avatardata[screen_name]['proceed'].append(meme_name)
        return meme_path
    if meme_name == 'symmetric':
        meme_path = memeFactory.generate_meme(meme_name,screen_name,timestamp,MEMES[meme_name],[avatar_path],args={"direction": random.choice(['right','left','bottom','top'])})
        avatardata[screen_name]['proceed'].append(meme_name)
        return meme_path
    if meme_name in ['charpic','dog_of_vtb','hold_tight','jerry_stare','konata_watch','let_me_in','potato','raise_image','smash','think_what','tomb_yeah','trance']:
        meme_path = memeFactory.generate_meme(meme_name,screen_name,timestamp,MEMES[meme_name],[avatar_path])
        avatardata[screen_name]['proceed'].append(meme_name)
        return meme_path
    else:
        logger.error(f"No such meme name: {meme_name}")
        return None
    
def main(tid,tweet):
    # 处理每篇推文
    full_text:str = tweet['full_text']
    mentions:list = tweet['entities']['user_mentions']
    user_screen_name = tweet.get('user', {}).get('screen_name', '未知用户')  # 获取发推文用户的名称
    
    # 详细记录推文信息，帮助调试
    logger.debug(f"处理推文 ID: {tid}, 用户: {user_screen_name}")
    logger.debug(f"推文全文: '{full_text}'")
    logger.debug(f"提及实体: {mentions}")
    
    # 检查用户提及内容是否只有@我们的用户名
    only_username_mention = False
    
    # 1. 基于实体检测 - 判断是否只有提及我们自己
    mentions_us = False
    for mention in mentions:
        if mention['screen_name'] == USERNAME:
            mentions_us = True
            break
    
    if not mentions_us:
        logger.debug(f"推文没有提及我们的用户名，跳过特殊处理")
        return  # 如果没有提及我们，直接返回不处理
    else:
        # 2. 如果提及了我们，进一步判断是否只是@我们而没有其他实质内容
        
        # 删除所有@提及后，检查是否还有实质内容
        content_without_mentions = full_text
        for mention in mentions:
            screen_name = mention['screen_name']
            mention_text = f"@{screen_name}"
            content_without_mentions = content_without_mentions.replace(mention_text, "")
        
        # 仅做最小限度的清理 - 只去掉首尾空白，保留实际内容
        cleaned_content = content_without_mentions.strip()
        
        # 打印原始文本和清理后的内容，帮助调试
        logger.debug(f"原始文本: '{full_text}'")
        logger.debug(f"去掉提及后: '{content_without_mentions}'")
        logger.debug(f"清理后的内容: '{cleaned_content}'")
        
        # 判断是否是真正的空提及 - 只有在删除所有提及后完全没有内容时才算
        is_truly_empty = (len(cleaned_content) == 0)
        
        logger.debug(f"提及分析: 去掉提及后的内容='{cleaned_content}', 内容长度={len(cleaned_content)}, 内容完全为空={is_truly_empty}")
        
        # 只有在真正完全没有内容时才使用固定回复
        if is_truly_empty:
            only_username_mention = True
            logger.info(f"用户 {user_screen_name} 只提及了我们的用户名，没有任何其他内容")
    
    # 处理推文回复
    if only_username_mention:
        # 如果用户提及内容只有@我们的用户名，直接回复特定文本，不经过AI
        reply_text = "You're so high and mighty, completely silent. What the fuck are you playing at?"
        logger.info(f"对完全空提及使用预设回复: '{reply_text}'")
    else:
        # 有实际内容的推文，使用AI生成回复
        logger.info(f"处理来自用户 {user_screen_name} 的非空提及推文: '{cleaned_content}'")
        
        # 调用AI API获取回复内容 - 现在get_ai_response会自动重试并返回有效回复
        reply_text = get_ai_response(user_screen_name, full_text.strip())
        logger.info(f"最终使用的AI回复: '{reply_text}'")
    
    # 构建回复参数
    reply = {
        "in_reply_to_tweet_id": str(tid)
    }
    
    # 发送回复
    logger.info(f"正在发送回复: '{reply_text}'")
    result = xapi.send_tweet(reply_text, reply=reply)
    logger.info(f'发送推文结果: {result}')

    # 更新最后处理的推文ID
    basicdata['lastTweetId'] = tid
    
    # 更新最后一条推文ID
    with open('save/basic.json', 'w') as f:
        json.dump(basicdata, f, indent=4)
    # 更新头像数据
    with open('save/avatar.json', 'w') as f:
        json.dump(avatardata, f, indent=4)

# 配置拦截标准库日志
class InterceptHandler(logging.Handler):
    def emit(self, record):
        # 获取对应的loguru级别
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 找到调用者信息
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# 拦截所有标准库日志
logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)

# 配置loguru日志记录
logger.add('logs/main.log', level='TRACE', rotation='1 MB', retention='24 Hours', encoding='utf-8', enqueue=True)
logger.add('logs/console.log', level='DEBUG', rotation='1 MB', retention='24 Hours', encoding='utf-8', enqueue=True)
logger.add(sys.stdout, level='INFO', enqueue=True)  # 控制台只显示INFO及以上级别

# 拦截标准输出和标准错误流
class StreamToLogger:
    def __init__(self, level):
        self.level = level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            logger.log(self.level, line.rstrip())
        
    def flush(self):
        pass

# 重定向标准输出和标准错误到logger
sys.stdout = StreamToLogger("INFO")
sys.stderr = StreamToLogger("ERROR")

# 原始日志初始化
USERNAME = config.USERNAME
xapi = twitterApi.Xapi()

with open('save/basic.json', 'r') as f:
    basicdata = json.load(f)
    logger.debug(f'init load basic data: {basicdata}')

with open('save/avatar.json', 'r') as f:
    avatardata = json.load(f)
    logger.debug(f'init load avatar data: {avatardata}')
    
while True:
    current_time = time.localtime()
    print(f"当前时间: {time.strftime('%Y-%m-%d %H:%M:%S', current_time)}, 正在循环检查......")
    try:
        lastTID = basicdata['lastTweetId']
        result = xapi.get_notifications_all()
        # 将调试信息降级为trace级别，不会显示在控制台上
        logger.trace(f'获取到的API响应数据: {result}')
        
        # 添加错误处理，防止KeyError
        try:
            tweets = result['globalObjects']['tweets']
            newtweets = {tid: tweet for tid, tweet in tweets.items() if int(tid) > int(lastTID)}
            if newtweets:
                logger.info(f'发现 {len(newtweets)} 条新推文')
                logger.trace(f'新推文详情: {newtweets}')
            else:
                logger.debug(f'没有新的推文')

            for tid, tweet in newtweets.items():
                main(tid, tweet)
        except KeyError as e:
            # 记录错误但继续执行
            logger.error(f"API返回数据结构异常: {str(e)}")
            logger.debug(f"API返回数据: {result}")
            # 设置newtweets为空字典，确保循环能继续
            newtweets = {}
    except Exception as e:
        # 捕获其他可能的异常
        logger.error(f"程序执行异常: {str(e)}")
    finally:
        time.sleep(config.SLEEPTIME)
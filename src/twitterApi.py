import json
from pprint import pprint
import sys
from time import sleep
import config
import requests
from loguru import logger
from requests_toolbelt.multipart.encoder import MultipartEncoder
from upload_file import upload_file

class Xapi:
    def __init__(self):
        self.endpoint = config.XAPIENDPOINT
        self.apikey = config.APIKEY
        self.authtoken = config.AUTHTOKEN
    
    def process_header(self,headers={}):
        headers['apikey'] = self.apikey
        headers['AuthToken'] = self.authtoken
        return headers
    
    def process_rawresult(self,rawresult):
        if rawresult.status_code != 200:
            logger.error(f"API状态码错误: {rawresult.status_code} - {rawresult.text}")
            return rawresult.json()
        elif rawresult.status_code == 200:
            try:
                logger.trace(f'API响应结果: {rawresult.json()}')
                return rawresult.json()
            except Exception:
                logger.error(f"JSON解析错误: {rawresult.status_code} - {rawresult.text}")
                return rawresult.text
        else:
            logger.error(f"未知错误: {rawresult.status_code} - {rawresult.text}")
            return None
    
    def send_GET_request(self,url,data={},headers={}):
        logger.trace(f"GET {url} with data {data}")
        url = self.endpoint + url
        headers = self.process_header(headers)
        while True:
            try:
                rawresult = requests.get(url=url, params=data, headers=headers, verify=False)
                if rawresult.status_code == 200:
                    break
            except KeyboardInterrupt:
                break
            except:
                pass
        result = self.process_rawresult(rawresult)
        return result
    
    def send_POST_requset(self,url,data={},headers={},file=None):
        logger.trace(f"POST {url} with data {data}")
        url = self.endpoint + url
        headers = self.process_header(headers)
        cType = headers.get('Content-Type')
        while True:
            try:
                if cType == 'application/json':
                    rawresult = requests.post(url=url, json=data, headers=headers, verify=False)
                elif cType == 'multipart/form-data':
                    rawresult = requests.post(url=url, data=data, headers=headers, files=file, verify=False)
                else:
                    rawresult = requests.post(url=url, data=data, headers=headers, verify=False)
                if rawresult.status_code == 200:
                    break
            except KeyboardInterrupt:
                break
            except:
                pass
        result = self.process_rawresult(rawresult)
        return result
        
    def get_notifications_mentions(self):
        url = '/2/notifications/mentions.json'
        result = self.send_GET_request(url)
        return result
    
    def get_notifications_all(self):
        url = '/2/notifications/all.json'
        result = self.send_GET_request(url)
        return result
        
    def search_timeline(self, query):
        url = '/graphql/SearchTimeline'
        data = {'variables':
            {"rawQuery":query,
             "count":40,
             "cursor":"",
             "querySource":"typed_query",
             "product":"Latest",
             "includePromotedContent":False
            }}
        result = self.send_GET_request(url, data)
        return result
    
    def get_user_info(self, screen_name):
        url = f'/1.1/users/show.json'
        data = {'screen_name':screen_name}
        result = self.send_GET_request(url,data)
        return result
    
    def get_user_avatar_url(self, screen_name):
        result = self.get_user_info(screen_name)
        avatar_url = result['profile_image_url'].replace('_normal.','_400x400.')
        return avatar_url
    
    def send_tweet(self,tweet_text:str,reply={},media={}):
        url = '/graphql/CreateTweet'
        data = {"variables": {
                    "tweet_text": tweet_text,
                    "dark_request": False,
                    "semantic_annotation_ids": [],
                    "includePromotedContent": False
                }}
        if reply:
            data['variables']['reply'] = reply
        if media:
            data['variables']['media'] = media
        headers = {'Content-Type': 'application/json'}
        result = self.send_POST_requset(url, data, headers)
        return result
    
    def upload_file(self,file_path):
        return upload_file(file_path)

    def get_screen_name_by_uid(self, uid):
        url = f'/1.1/users/show.json'
        data = {'user_id':str(uid)}
        result = self.send_GET_request(url,data)
        return result['screen_name']
    
    def new_upload_file(self,fp):
        return upload_file(fp)

if __name__ == "__main__":
    logger.remove(0)  # Remove default logger
    logger.add("logs/twitter_listener.log", rotation="1 MB", retention="10 days", level="DEBUG")
    logger.add(sys.stdout, level="INFO")  # Console logs INFO level and above
    xapi = Xapi()
    result = xapi.get_notifications_all()
    with open(r'tmp3.json','w') as f:
        json.dump(result,f,indent=4)
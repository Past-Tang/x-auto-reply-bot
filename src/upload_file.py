import http.client
import json
import mimetypes
from codecs import encode
import config
from loguru import logger
import ssl
ssl._create_default_https_context = ssl._create_unverified_context  # 禁用全局验证

def upload_file(fp):
    filename = fp.split('/')[-1]
    logger.debug(f'filepath:{fp},filename:{filename}')
    conn = http.client.HTTPSConnection("api.apidance.pro")
    dataList = []
    boundary = 'wL36Yn8afVp8Ag7AmP8qZ0SA4n1v9T'
    dataList.append(encode('--' + boundary))
    dataList.append(encode('Content-Disposition: form-data; name=file; filename={0}'.format(filename)))

    fileType = mimetypes.guess_type('')[0] or 'application/octet-stream'
    dataList.append(encode('Content-Type: {}'.format(fileType)))
    dataList.append(encode(''))

    with open(fp, 'rb') as f:
        dataList.append(f.read())
        # print(dataList)
    dataList.append(encode('--'+boundary+'--'))
    dataList.append(encode(''))
    body = b'\r\n'.join(dataList)
    payload = body
    headers = {
    'apikey': config.APIKEY,
    'authtoken': config.AUTHTOKEN,
    'Content-type': 'multipart/form-data; boundary={}'.format(boundary)
    }
    conn.request("POST", "/twitter/upload", payload, headers)
    res = conn.getresponse()
    data = res.read()
    result = data.decode("utf-8")
    try:
        result_js = json.loads(result)
        return result_js
    except:
        logger.warning(result)
        return result

if __name__ == "__main__":
    # 测试
    result = upload_file(r'lib\petpet\TryingMyBot_1746646088.gif')
    print(json.loads(result)['media_id_string'])
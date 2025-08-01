import re
import random
from typing import Dict, List, Tuple, Optional, Callable, Any
import requests
from crypt_1 import PRPCrypt, find_key
import time
from bs4 import BeautifulSoup
import logging
from logging.handlers import RotatingFileHandler
import json
import os
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

# 配置日志记录
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 创建日志格式
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 文件处理器 - 限制日志文件最大10MB，保留3个备份
file_handler = RotatingFileHandler(os.getcwd() + '/log/iptv.log', 
                                 maxBytes=4*1024*1024, 
                                 backupCount=3,
                                 encoding='utf-8')
file_handler.setFormatter(formatter)

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

@dataclass
class Config:
    """配置管理类"""
    key: str = ''
    UserID: str = ''
    mac: str = ''
    STBID: str = ''
    ip: str = ''
    STBType: str = ''
    STBVersion: str = ''
    UserAgent: str = ''
    Authenticator: str = ''
    UDPxy: str = ''
    
    
    @classmethod
    def load(cls, config_file: str = os.path.join(os.path.dirname(__file__), 'config', 'config.json')) -> 'Config':
        """加载配置文件"""
        config = cls()
        if not Path(config_file).exists():
            logger.warning(f"配置文件 {config_file} 不存在")
            return config
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for field in cls.__annotations__:
                    if field in data:
                        setattr(config, field, data[field])
                    
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
        return config
        
    def save(self, config_file: str = 'config.json') -> bool:
        """保存配置文件"""
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                data = {field: getattr(self, field) 
                       for field in self.__annotations__}
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")
            return False





def load_config(config_file=os.path.join(os.path.dirname(__file__), 'config', 'config.json')):
    """加载配置文件"""
    config = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f'配置文件格式错误: {str(e)}')
        except Exception as e:
            logger.error(f'加载配置文件失败: {str(e)}')
    return config

def update_config(key=None, value=None, config_file=os.path.join(os.path.dirname(__file__), 'config', 'config.json')):
    """更新配置文件"""
    if not key or not value:
        logger.error('更新配置需要提供key和value')
        return False
    
    try:
        # 读取现有配置
        config = load_config(config_file)
        # 更新配置项
        config[key] = value
        # 写入更新后的配置
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        logger.info(f'成功更新配置项 {key} = {value}')
        return True
    except Exception as e:
        logger.error(f'更新配置文件失败: {str(e)}')
        return False

config = load_config()

# 从配置文件加载所有配置项

key = config.get('key', '')
if not key and config.get('Authenticator', ''):
    try:
        keys = find_key(config['Authenticator'])
        if keys:
            key = random.choice(keys)
            logger.info(f"从Authenticator解密结果中随机选择key: {key}")
            # 更新配置文件中的key
            update_config('key', key)
    except Exception as e:
        logger.error(f"解密Authenticator时发生错误: {str(e)}")

UserID = config.get('UserID', '')
mac = config.get('mac', '')
STBID = config.get('STBID', '')
ip = config.get('ip', '')
STBType = config.get('STBType', '')
STBVersion = config.get('STBVersion', '')
UserAgent = config.get('UserAgent', '')
Authenticator = config.get('Authenticator', '')

# 检查必要配置项
required_configs = {
    'UserID': UserID,
    'mac': mac,
    # 'STBID': STBID,
    'Authenticator': Authenticator
}

for name, value in required_configs.items():
    if not value:
        logger.error(f"缺少必要配置项: {name}")
        raise ValueError(f"请在config.json中配置{name}")


def get_auth(max_retries: int = 3) -> Optional[Tuple[str, dict, str, str]]:
    """
    获取认证信息
    :param max_retries: 最大重试次数
    :return: (host, cookies, user_token, stbid) 或 None
    """
    AuthenticationIP = config.get('AuthenticationIP','http://182.138.3.142:8082')
    retry_count = 0
    while retry_count < max_retries:
        try:
            # 第一步：获取host
            url = f'{AuthenticationIP}/EDS/jsp/AuthenticationURL?UserID={UserID}&Action=Login'
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'User-Agent': UserAgent,
                'X-Requested-With': 'com.android.smart.terminal.iptv',
            }
            
            logger.info(f'尝试获取认证信息 (尝试 {retry_count + 1}/{max_retries})')
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 记录返回的页面内容
            logger.debug(f"请求返回内容：\n{response.text}")
            
            # 从response的url中解析host
            from urllib.parse import urlparse
            host = urlparse(response.url).netloc
            logger.info(f"解析得到服务器地址: {host}")
            
            # 第二步：获取token
            auth_url = f'http://{host}/EPG/jsp/authLoginHWCTC.jsp'
            auth_headers = {
                'User-Agent': UserAgent,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': f'http://{host}/EPG/jsp/AuthenticationURL?UserID={UserID}&Action=Login',
                'X-Requested-With': 'com.android.smart.terminal.iptv',
            }
            auth_data = {
                'UserID': UserID,
                'VIP': ''
            }
            
            auth_response = requests.post(auth_url, headers=auth_headers, data=auth_data, timeout=10)
            auth_response.raise_for_status()
            
            # 记录原始响应内容
            logger.debug(f"authLogin响应内容：\n{auth_response.text}")
            
            # 解析返回的HTML内容
            soup = BeautifulSoup(auth_response.text, 'html.parser')
            
                        
            # 匹配EncryptToken
            encrypt_token_pattern = r'var EncryptToken = "([^"]+)"'
            encrypt_match = re.search(encrypt_token_pattern, auth_response.text)
            if not encrypt_match:
                raise ValueError('无法找到EncryptToken')
            EncryptToken = encrypt_match.group(1)
            
            # 匹配userToken
            user_token_pattern = r'document\.authform\.userToken\.value = "([^"]+)"'
            user_token_match = re.search(user_token_pattern, auth_response.text)
            if not user_token_match:
                raise ValueError('无法找到userToken')
            userToken = user_token_match.group(1)
            
            # 第三步：生成Authenticator
            pc = PRPCrypt(key)
            auth_str = f'{key}${EncryptToken}${UserID}${STBID}${ip}${mac}$$CTC'
            logger.info(f"加密前字符串: {auth_str}")
            
            Authenticator = pc.encrypt(auth_str)
            logger.info(f"加密后Authenticator: {Authenticator}")
            
            # 第四步：验证认证
            valid_url = f'http://{host}/EPG/jsp/ValidAuthenticationHWCTC.jsp'
            valid_headers = {
                'User-Agent': UserAgent,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': f'http://{host}/EPG/jsp/authLoginHWCTC.jsp',
            }
            valid_data = {
                'UserID': UserID,
                'Lang': '',
                'SupportHD': '1',
                'NetUserID': '',
                'Authenticator': Authenticator,
                'STBType': STBType,
                'STBVersion': STBVersion,
                'conntype': '',
                'STBID': STBID,
                'templateName': '',
                'areaId': '',
                'userToken': userToken,
                'userGroupId': '',
                'productPackageId': '',
                'mac': mac,
                'UserField': '',
                'SoftwareVersion': '',
                'IsSmartStb': 'undefined',
                'desktopId': 'undefined',
                'stbmaker': '',
                'VIP': '',
            }
            
            valid_response = requests.post(valid_url, headers=valid_headers, data=valid_data, timeout=10)
            valid_response.raise_for_status()
            
            # 记录验证响应内容
            logger.debug(f"验证认证响应内容：\n{valid_response.text}")
            
            # 获取cookies和user_token
            cookies = valid_response.cookies
            logger.info(f"JSESSIONID: {cookies.get('JSESSIONID')}")
            
            # 如果响应是HTML，使用正则表达式提取UserToken和stbid
            if valid_response.headers.get('Content-Type', '').startswith('text/html'):
                html_content = valid_response.text
                
                # 提取UserToken
                user_token_match = re.search(r'name="UserToken"\s*value="([^"]+)"', html_content)
                user_token = user_token_match.group(1) if user_token_match else None
                
                # 提取stbid
                stbid_match = re.search(r'name="stbid"\s*value="([^"]+)"', html_content)
                stbid = stbid_match.group(1) if stbid_match else None
                
                if not user_token or not stbid:
                    logger.error("无法从HTML中提取UserToken或stbid")
                    return None, None, None, None
                    
                logger.info(f"从HTML中提取到UserToken: {user_token}")
                logger.info(f"从HTML中提取到stbid: {stbid}")
                return host, cookies, user_token, stbid
               
            
        except requests.exceptions.RequestException as e:
            logger.error(f'请求失败: {str(e)}')
            retry_count += 1
            if retry_count < max_retries:
                logger.info(f'等待5秒后重试...')
                time.sleep(5)
            continue

def format_xmltv_time(timestamp):
    """将时间戳转换为XMLTV格式"""
    from datetime import datetime
    dt = datetime.strptime(timestamp, '%Y%m%d%H%M%S')
    return dt.strftime('%Y%m%d%H%M%S %z')
            

def process_channel_data(channels: List[Tuple[str, ...]]) -> Dict[str, List[str]]:
    """处理频道数据并生成频道信息映射"""
    channel_info = {}
    channel_ids = []
    
    # 过滤无效频道
    channels = [ch for ch in channels if "画中画" not in ch[1] and "单音轨" not in ch[1] and "热门" not in ch[1] and "直播室" not in ch[1] and "92" not in ch[1] and "精彩推荐专区" not in ch[1] and "精彩导视" not in ch[1]]
    
    # 使用with语句安全处理文件
    with open(os.getcwd() +'/output/sctv.txt', 'w', encoding='utf-8') as ftxt, \
         open(os.getcwd() +'/output/sctv.m3u', 'w', encoding='utf-8') as fm3u:
        
        # 写入文件头
        ftxt.write('央视频道,#genre#\n')
        fm3u.write('#EXTM3U\n')
        
        # 定义频道分类处理函数
        def write_channel(category: str, condition: Callable[[str], bool]):
            for channel in channels:
                if condition(channel[1]):
                    name = "CCTV-14高清" if channel[1] == "CCTV-少儿高清" else channel[1]
                    udpxy = config.get('UDPxy', 'http://192.168.5.1:8888')
                    url = f'{udpxy}/rtp/{channel[3]}'
                    
                    # 写入txt文件
                    
                    if channel[4] == '1': #支持时移的源
                        ftxt.write(f'{name},{channel[6]}#{url}\n')
                    else:
                        ftxt.write(f'{name},{url}#{channel[6]}\n')
                    
                    # 写入m3u文件
                    fm3u.write(f'#EXTINF:-1 group-title="{category}", {name}\n{url}\n')
                    
                    # 记录频道信息
                    channel_ids.append([channel[0], name, channel[2]])
        
        # 处理不同分类的频道
        write_channel('央视频道', lambda name: any(x in name for x in ['CCTV', 'CHC', 'CGTN']))
        ftxt.write('卫视频道,#genre#\n')
        write_channel('卫视频道', lambda name: '卫视' in name)
        ftxt.write('数字频道,#genre#\n')
        write_channel('数字频道', lambda name: '专区' in name)
        ftxt.write('其他频道,#genre#\n')
        write_channel('其他频道', lambda name: not any(x in name for x in ['专区', '卫视', 'CCTV', 'CHC', 'CGTN']))
    
    # 生成频道信息映射
    for i, channel in enumerate(channels):
        channel_info[channel_ids[i][0]] = [channel_ids[i][1], channel_ids[i][2]]
    
    return channel_info

def get_channel_list(host: str, cookies: dict, user_token: str, stbid: str) -> Dict[str, List[str]]:
    """获取频道列表"""
    channel_url = f'http://{host}/EPG/jsp/getchannellistHWCTC.jsp'
    channel_data = {
        'conntype': '',
        'UserToken': user_token,
        'tempKey': '', 
        'stbid': stbid,
        'SupportHD': '1',
        'UserID': UserID,
        'Lang': '1'
    }
    
    response = requests.post(channel_url, cookies=cookies, data=channel_data)
    response.raise_for_status()
    logger.debug(response.text)
    
    # 使用正则表达式提取频道信息
    pattern = re.compile(
        r'ChannelID\=\"(\d+)\",'
        r'ChannelName\=\"(.+?)\",'
        r'UserChannelID\=\"(\d+)\",'
        r'ChannelURL=\"igmp://(.+?)\".+?'
        r'TimeShift\=\"(\d+)\",'
        r'TimeShiftLength\=\"(\d+)\".+?,'
        r'TimeShiftURL\=\"(.+?\.smil)'
    )
    
    channels = pattern.findall(response.text)
    return process_channel_data(channels)
    

def process_epg_data(channel_id: str, channel_name: List[str], response_text: str) -> Optional[List[Dict[str, str]]]:
    """处理EPG数据"""
    import re
    import json
    
    # 提取EPG JSON数据
    match = re.search(r'parent\.jsonBackLookStr\s*=\s*(\[.*?\]);', response_text)
    if not match:
        logger.debug(f"无法从EPG响应中提取JSON数据，跳过频道 {channel_id}")
        return None
        
    try:
        epg_data = json.loads(match.group(1))
        if not epg_data or not isinstance(epg_data, list) or len(epg_data) < 2:
            logger.debug(f"EPG数据为空或不完整，跳过频道 {channel_id}")
            return None
            
        programs_data = []
        for programs in epg_data[1]:
            if isinstance(programs, list):
                for program in programs:
                    if not isinstance(program, dict):
                        continue
                        
                    # 获取节目信息
                    program_data = {
                        'beginTimeFormat': program.get('beginTimeFormat', ''),
                        'endTimeFormat': program.get('endTimeFormat', ''),
                        'programName': program.get('programName', '未知节目')
                    }
                    
                    # 验证时间格式
                    if not program_data['beginTimeFormat'] or not program_data['endTimeFormat']:
                        logger.debug(f"节目时间格式无效，跳过: {program_data}")
                        continue
                        
                    # 格式化时间
                    start_time = format_xmltv_time(program_data['beginTimeFormat'])
                    end_time = format_xmltv_time(program_data['endTimeFormat'])
                    
                    if not start_time or not end_time:
                        logger.debug(f"时间转换失败，跳过: {program_data}")
                        continue
                        
                    # 转义节目名称中的特殊字符
                    program_name = program_data["programName"]
                    program_name = program_name.replace('<', '《').replace('>', '》')
                    program_name = program_name.replace('&', '&amp;')

                    programs_data.append({
                        'channel_name': channel_name[0],
                        'start_time': start_time,
                        'end_time': end_time,
                        'program_name': program_name
                    })
        
        return programs_data
        
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"解析EPG JSON数据失败: {str(e)}")
        return None

def write_epg_file(channel_info: Dict[str, List[str]], epg_data: Dict[str, List[Dict[str, str]]]):
    """写入EPG文件"""
    with open(os.getcwd() +'/output/epg.xml', 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<tv>\n')
        
        # 写入频道信息
        for channel_id, channel_name in channel_info.items():
            f.write(f'  <channel id="{channel_name[0]}">\n')
            f.write(f'    <display-name lang="zh">{channel_name[0]}</display-name>\n')
            f.write('  </channel>\n')
        
        # 写入节目信息
        for channel_id, programs in epg_data.items():
            for program in programs:
                f.write(f'  <programme channel="{program["channel_name"]}" '
                       f'start="{program["start_time"]} +0800" '
                       f'stop="{program["end_time"]} +0800">\n')
                f.write(f'    <title lang="zh">{program["program_name"]}</title>\n')
                f.write(f'    <desc lang="zh"></desc>\n')
                f.write('  </programme>\n')
        
        f.write('</tv>\n')

def get_epg(host: str, cookies: dict, channel_info: Dict[str, List[str]]):
    """获取EPG数据"""
    epg_data = {}
    
    for channel_id, channel_name in channel_info.items():
        logger.info(f"正在获取频道 {channel_name[0]} 的EPG数据")
        
        # 构建请求
        epg_url = f'http://{host}/EPG/jsp/tools/aged/getTvodData.jsp?channelId={channel_id}'
        headers = {
            'User-Agent': UserAgent,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': f'http://{host}/EPG/jsp/tools/aged/getTvodData.jsp'
        }
        data = {
            'conntype': '',
            'UserToken': user_token,
            'tempKey': '',
            'stbid': stbid,
            'SupportHD': '1',
            'UserID': UserID,
            'Lang': '1'
        }
        
        try:
            response = requests.post(epg_url, headers=headers, data=data, cookies=cookies, timeout=10)
            response.raise_for_status()
            
            # 处理EPG数据
            programs = process_epg_data(channel_id, channel_name, response.text)
            if programs:
                epg_data[channel_id] = programs
                
        except requests.exceptions.RequestException as e:
            logger.error(f"获取频道 {channel_name[0]} 的EPG数据失败: {str(e)}")
            continue
    
    # 写入EPG文件
    write_epg_file(channel_info, epg_data)
    logger.info('epg.xml,sctv.m3u,sctv.txt以保存到output目录')

if __name__ == '__main__':
    

    
    host, cookies, user_token, stbid = get_auth()
    logger.info(f"认证结果：host={host}, cookies={cookies}, user_token={user_token}, stbid={stbid}")
    
    if not host:
        print("认证失败，无法获取host地址")
        exit(1)
        
    channel_info = get_channel_list(host, cookies, user_token, stbid)
    get_epg(host, cookies, channel_info)

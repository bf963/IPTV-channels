from Crypto.Cipher import DES3
from typing import Optional
import logging
import os
import datetime

# 配置日志记录
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 创建日志格式
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 文件处理器
file_handler = logging.FileHandler(os.getcwd() + '/log/iptv.log', encoding='utf-8')
file_handler.setFormatter(formatter)

# 标准输出处理器
import sys
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stdout_handler)

def pad(text: str, block_size: int = 8) -> str:
    """填充文本到指定块大小"""
    padding_length = block_size - len(text) % block_size
    padding = chr(padding_length) * padding_length
    return text + padding

def unpad(text: str) -> str:
    """去除填充"""
    padding_length = ord(text[-1])
    return text[:-padding_length]

class PRPCrypt:
    """3DES加密工具类"""
    
    def __init__(self, key: str):
        """初始化加密器"""
        # 将8字节密钥扩展为24字节
        if len(key) == 8:
            self.key = key + key + key  # 重复3次
        else:
            self.key = key.ljust(24, '0')  # 确保key长度为24字节
        self.mode = DES3.MODE_ECB
        
    def encrypt(self, text: str) -> str:
        """加密文本"""
        padded_text = pad(text)
        cryptor = DES3.new(self.key.encode(), self.mode)
        ciphertext = cryptor.encrypt(padded_text.encode())
        return ciphertext.hex()
    
    def decrypt(self, text):#需要解密的字符串，字符串为十六进制的字符串  如"a34f3e3583"....
        # logger.info(f"开始解密，输入长度: {len(text)}")
        try:
            cryptor = DES3.new(self.key, self.mode)
            logger.debug(f"成功创建DES3加密器，key长度: {len(self.key)}")
        except Exception as e:
            if 'degenerates' in str(e):
                raisetxt = 'if key_out[:8] == key_out[8:16] or key_out[-16:-8] == key_out[-8:]:\nraise ValueError("Triple DES key degenerates to single DES")'
                logger.warning('请将调用的DES3.py文件里adjust_key_parity方法中的：%s  注释掉'%raisetxt)
            else:
                logger.error(f"创建DES3加密器失败: {str(e)}")
            raise
            
        try:
            de_text = bytes.fromhex(text)
            plain_text = cryptor.decrypt(de_text)
            logger.debug(f"解密成功，输出长度: {len(plain_text)}")
            return plain_text.replace(b'\x08',b'').decode('utf-8')  #返回 string,不需要再做处理
        except Exception as e:
            # logger.error(f"解密过程失败: {str(e)}")
            raise

def find_key(Authenticator: str) -> list:
    """查找有效的解密key"""
    i = 0
    keys = []
    date_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if len(Authenticator) < 10:
        logger.error("Authenticator长度不足10位")
        Authenticator = input('未配置Authenticator，请输入正确的Authenticator的值：')
        if len(Authenticator) < 10:
            logger.error("输入的Authenticator仍然无效")
            return []
    
    logger.info(f"开始测试00000000-99999999所有八位数字，Authenticator长度: {len(Authenticator)}")
    for x in range(100000000):
        key = str('%08d'%x)
        if x % 500000 == 0:
            logger.info('已经搜索至：-- %s -- '%key)
            
        pc = PRPCrypt('%s'%key)
        try:
            ee = pc.decrypt(Authenticator)
            infos = ee.split('$')
            infotxt = '  随机数:%s\n  TOKEN:%s\n  USERID:%s\n  STBID:%s\n  ip:%s\n  mac:%s\n  运营商:%s'%(infos[0],infos[1],infos[2],infos[3],infos[4],infos[5],infos[7]) if len(infos)>7 else ''
            logger.info('找到key:%s,解密后为:%s\n%s'%(x,ee,infotxt))
            keys.append(key)
            i += 1
            if i > 20:
                break
        except Exception as e:
            pass

    with open(os.getcwd() +'/log/key.txt','w', encoding='utf-8') as f:
        line = '%s\n共找到KEY：%s个,分别为：%s\n解密信息为:%s\n详情：%s'%(date_now,len(keys),','.join(keys),str(ee),infotxt)
        f.write(line)
        f.flush()
            
    return keys


if __name__ == "__main__":
    find_key('263D5D3BFCC8384102C7FB88BEA57FBF27DB4E1595E1A4260E3290D2844A14DF36F59D19F6CDA1F4AC78371C2C59BF9539FE94C3C3B135E4CA0B3BA5971D5FF1F8F78674F2F360EEB0FE440900984C32F52AADA96F5E8DE768F03D0867E95D11EF313CD7FD2C4836A2D6C55F12CF5D3D9ACF96C7F4326CEF1510143A1ACFFAE21A96CAE54F077D35')
    print('111')
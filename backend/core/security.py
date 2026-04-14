import base64

def encode_api_key(api_key: str) -> str:
    """
    简单混淆 API Key (Base64编码)
    """
    if not api_key:
        return ""
    # 对字符串进行base64编码
    key_bytes = api_key.encode('utf-8')
    base64_bytes = base64.b64encode(key_bytes)
    return base64_bytes.decode('utf-8')

def decode_api_key(encoded_key: str) -> str:
    """
    解码被混淆的 API Key (Base64解码)
    """
    if not encoded_key:
        return ""
    try:
        base64_bytes = encoded_key.encode('utf-8')
        key_bytes = base64.b64decode(base64_bytes)
        return key_bytes.decode('utf-8')
    except Exception:
        # 如果解码失败，假定它是明文或无效的
        return encoded_key

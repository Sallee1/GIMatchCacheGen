import requests
import json

from typing import Dict, List, Any
import os


def loadToken(token_path: str) -> Dict[str, Any]:
    """    
    @brief 从本地读取token文件
    @param token_path token文件路径
    @return token的json对应的字典
    """

    if (not os.path.exists(token_path)):
        raise Exception(f"{token_path} not found")

    tokens = {}
    with open(token_path, "r") as f:
        tokens = json.load(f)

    if (tokens == None):
        raise Exception(f"{token_path} is empty")
    return tokens

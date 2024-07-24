import urllib.parse
import requests
import json
import re
from typing import Dict, List, Any
import os
import urllib
import fnmatch


class WebMapDownloader:
    """
    空荧酒馆地下图层下载器
    
    用于提取web_map.json的内容并下载地下图层
    
    因为空荧酒馆服务器资源有限，请不要在开发版本ci中整合此脚本
    """

    def __init__(self, rootpath: str, cvat_map_setting: Dict[str, Any]):
        self.rootpath = rootpath
        self.cvat_map_setting = cvat_map_setting

    def _sanitize_and_build_path(self, url: str) -> str:
        """清理URL路径并构建本地文件路径"""
        match = re.match(r"^(https?://[^/]+)(/.*)", url)
        if not match:
            print(f"[error] URL格式不正确，无法提取路径：{url}")
            return ""
        url_path = match.group(2).lstrip("/")  # 移除前导斜杠
        # url解码
        url_path = urllib.parse.unquote(url_path)
        return os.path.join(self.rootpath, url_path)

    def _download_image(self, url: str) -> bool:
        """下载单个图像并保存至指定路径，确保单个失败不影响整体流程"""
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error: \"{url}\" 下载失败，原因：{e}, 但将继续尝试下载其他图片")
            return False

        # 将url反转义到可读形式
        url = urllib.parse.unquote(url)
        path = self._sanitize_and_build_path(url)

        # 检查url是否在排除名单中
        if ("web_map_layer_ignores" in self.cvat_map_setting):
            for ignore_path in self.cvat_map_setting["web_map_layer_ignores"]:
                if (fnmatch.fnmatch(path, os.path.join(self.rootpath, ignore_path))):
                    print(f"[warn] 跳过下载 \"{url}\"")
                    return True

        os.makedirs(os.path.dirname(path), exist_ok=True)

        try:
            with open(path, "wb") as f:
                f.write(response.content)
            print(f"[info] 成功下载 \"{url}\" 至 \"{path}\"")
            return True
        except IOError as e:
            print(f"[Error] 写入文件\"{path}\"失败，原因：{e}, 继续尝试下载其他图片")
            return False

    def _process_plugin(self, plugin_data: Dict[str, Any]) -> None:
        """递归处理overlay、children、chunks层级结构中的图像下载，仅在最深层级装配模板下载"""
        template = plugin_data["urlTemplate"]
        self._process_level(template, plugin_data)

    def _process_level(self, template: str, level_data: Dict[str, Any], groupValue="", itemValue="", chunkValue="") -> None:
        """递归处理当前层级的数据，决定是否下载或继续深入"""
        if (level_data.get("url", "") != ""):
            url: str = level_data["url"]
            self._download_image(url)
            return

        if "overlays" in level_data:
            for overlay in level_data["overlays"]:
                currentValue = overlay.get("value", "")
                self._process_level(
                    template, overlay, currentValue, itemValue, chunkValue)
            return

        if "children" in level_data:
            for child in level_data["children"]:
                currentValue = child.get("value", "")
                self._process_level(
                    template, child, groupValue, currentValue)
            return

        if "chunks" in level_data:
            for chunk in level_data["chunks"]:
                currentValue = chunk.get("value", "")
                self._process_level(
                    template, chunk, groupValue, itemValue, currentValue)
            return

        self._process_template_and_download(
            template, groupValue, itemValue, chunkValue)

    def _process_template_and_download(self, template, groupValue: str, itemValue: str, chunkValue: str) -> bool:
        """处理模板并尝试下载已填充模板的图像"""

        if (self._check_template_value_is_avilable(template, "{{groupValue}}", groupValue) == False):
            print("[warn] 模板需要参数groupValue，但未找到")
            return False
        if (self._check_template_value_is_avilable(template, "{{itemValue}}", itemValue) == False):
            print("[warn] 模板需要参数itemValue，但未找到")
            return False

        if (self._check_template_value_is_avilable(template, "{{chunkValue}}", chunkValue) == False):
            print("[warn] 模板需要参数chunkValue，但未找到")
            return False

        filled_template = template.replace("{{groupValue}}", groupValue).replace(
            "{{itemValue}}", itemValue).replace("{{chunkValue}}", chunkValue)

        return self._download_image(filled_template)

    def _check_template_value_is_avilable(self, template: str, pattern: str, value: str) -> bool:
        """检查模式串替换是否合法"""
        # 模式串不在模板中，不需要匹配
        if (pattern not in template):
            return True

        # 模式串在模板中，需要匹配，值为空
        if (value is None or value == ""):
            return False

        return True

    def download_web_map(self, webmap_url: str):
        """根据webmap_url下载所有相关图像"""
        try:
            response = requests.get(webmap_url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"获取web_map.json失败，原因：{e}")
            return

        web_map_json = response.json()

        for plugin in web_map_json.get("plugins", {}).values():
            overlay_config = plugin.get("overlayConfig")
            if overlay_config and "overlays" in overlay_config:
                try:
                    self._process_plugin(overlay_config)
                except Exception as e:
                    print(f"[error] 处理插件数据时发生错误：{e}")

# 示例调用
# download_web_map('http://example.com/web_map.json', '/path/to/save')


if __name__ == "__main__":
    cwd = os.getcwd()

    # 01: 解析token文件
    if (os.path.isfile("tokens.json") == False):
        raise FileNotFoundError("tokens.json文件不存在")

    tokens = {}
    with open("tokens.json", "r") as f:
        tokens = json.load(f)

    # 02: 下载web_map.json的资源
    # 读取地区配置文件
    cvat_setting_json_path = "resources/json/cvat_map_setting.json"
    if (not os.path.isfile(cvat_setting_json_path)):
        raise FileNotFoundError("cvat_map_setting.json文件不存在")
    cvat_map_setting = {}
    with open(cvat_setting_json_path, "r", encoding="utf-8") as f:
        cvat_map_setting = json.load(f)

    web_map_url = tokens["web-map_url"]
    downloader = WebMapDownloader("resources/web_map", cvat_map_setting)
    downloader.download_web_map(web_map_url)

import urllib.parse
import requests
import json
import re
from typing import Dict, List, Any, NewType, Tuple
import os
import urllib
import fnmatch
import copy

# 生成地图信息文件，用于辅助生成缓存


KYBounds = Tuple[Tuple[float, float], Tuple[float, float]]
CVBounds = Tuple[float, float, float, float]
JsonObj = Dict[str, Any]
JsonArray = List[Any]
JsonList = List[Any]


class MapInfoGenerator:
    def __init__(self, rootpath: str, cvat_map_setting: JsonObj):
        self.rootpath = rootpath
        self.cvat_map_setting = cvat_map_setting

        self.curent_plugin_key = ""
        self.map_info_obj = {}

    def _process_plugin(self, plugin_data: JsonObj) -> None:
        """递归处理overlay、children、chunks层级结构的信息生成"""
        template = plugin_data["urlTemplate"]
        self._process_level(template, plugin_data)

    def transform_bound(self, bounds: CVBounds, transform: JsonObj) -> CVBounds:
        new_bounds = list(bounds)
        scale: float = transform["scale"]
        translate: List[float] = transform["translate"]
        new_bounds = [new_bounds[i] * scale for i in range(2)]
        new_bounds[0] += translate[0]
        new_bounds[1] += translate[1]
        return (new_bounds[0], new_bounds[1], new_bounds[2], new_bounds[3])

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

    def _get_bound(self, level_data: JsonObj, transform: JsonObj) -> CVBounds | None:
        bounds: CVBounds | None = None

        if ("bounds" in level_data):
            web_map_bounds: KYBounds = level_data["bounds"]
            bounds = self.transform_bound((web_map_bounds[0][0],
                                           web_map_bounds[0][1],
                                           web_map_bounds[1][0] - web_map_bounds[0][0],
                                           web_map_bounds[1][1] - web_map_bounds[0][1]),
                                          transform)
        return bounds

    def _get_img_path(self, level_data: JsonObj, template="", groupValue="", itemValue="", chunkValue="") -> str | None:
        path = None
        url = ""
        if ("url" in level_data):
            url = urllib.parse.unquote(level_data["url"])

        if (path is None and len("urlTemplate") != 0):
            if (len(groupValue) != 0):
                url = url.replace("{{groupValue}}", groupValue)
            if (len(itemValue) != 0):
                url = url.replace("{{itemValue}}", itemValue)
            if (len(chunkValue) != 0):
                url = url.replace("{{chunkValue}}", chunkValue)

        path = self._sanitize_and_build_path(url)

        if (path is not None):
            # 检查url是否在排除名单中
            if ("web_map_layer_ignores" in self.cvat_map_setting):
                for ignore_path in self.cvat_map_setting["web_map_layer_ignores"]:
                    if (fnmatch.fnmatch(path, os.path.join(self.rootpath, ignore_path))):
                        print(f"[warn] 跳过图像{path}")
                        return None
        return path

    def _get_current_transform(self, pluginValue="", groupValue="", itemValue="", chunkValue="") -> JsonObj:
        def update_transform(node_key):
            nonlocal current_node
            if node_key in current_node:
                node = current_node[node_key]
                if "__transform__" in node:
                    ret_transform.update(node["__transform__"])
                return node
            return {}

        transform_root_node: JsonObj = self.cvat_map_setting["web_map_transform"]
        ret_transform: JsonObj = copy.deepcopy(
            transform_root_node["__transform__"])

        nodes_to_check = [pluginValue, groupValue, itemValue, chunkValue]
        current_node = transform_root_node

        for node_key in nodes_to_check:
            if node_key:
                current_node = update_transform(node_key)

        return ret_transform

    def _process_level(self, template: str, level_data: JsonObj, groupValue="", itemValue="", chunkValue="") -> None:
        bound: CVBounds | None = None
        img_path: str | None = None

        if "overlays" in level_data:
            for overlay in level_data["overlays"]:
                currentValue = overlay.get("value", "")
                # 获取当前层级的变换
                transform = self._get_current_transform(self.curent_plugin_key, groupValue, itemValue, chunkValue)
                bound = self._get_bound(overlay, transform)
                img_path = self._get_img_path(overlay, template, groupValue, currentValue, chunkValue)
                self._write_map_info(currentValue, bound, img_path, transform)
                self._process_level(template, overlay, currentValue)

            return

        if "children" in level_data:
            for child in level_data["children"]:
                currentValue = child.get("value", "")
                transform = self._get_current_transform(self.curent_plugin_key, groupValue, itemValue, chunkValue)
                bound = self._get_bound(child, transform)
                img_path = self._get_img_path(child, template, groupValue, currentValue, chunkValue)
                self._write_map_info(currentValue, bound, img_path, transform)
                self._process_level(template, child, currentValue, itemValue)

    def _write_map_info(self, value: str, bound: CVBounds | None, img: str | None, transform: JsonObj) -> None:
        if (bound is not None and img is not None):
            self.map_info_obj[value] = {
                "img_path": img,
                "bound": bound,
                "transform": transform}

    def gen(self, webmap_url: str):
        """获取web_map.json文件"""
        try:
            response = requests.get(webmap_url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"获取web_map.json失败，原因：{e}")
            return

        web_map_json: JsonObj = response.json()
        plugin_json: JsonObj = web_map_json.get("plugins", {})

        for key in plugin_json.keys():
            overlay_config = plugin_json[key].get("overlayConfig")
            if overlay_config and "overlays" in overlay_config:
                try:
                    self.curent_plugin_key = key
                    self._process_plugin(overlay_config)
                except Exception as e:
                    print(f"[error] 处理插件数据时发生错误：{e}")

    def dump(self, file_path: str):
        """将数据写入文件"""
        with open(file_path, "w") as f:
            json.dump(self.map_info_obj, f, indent=4, ensure_ascii=False)
        print(f"[info] 地图信息已写入{file_path}")


if __name__ == "__main__":
    cwd = os.getcwd()

    # 01: 解析token文件
    if (os.path.isfile("tokens.json") == False):
        raise FileNotFoundError("tokens.json文件不存在")

    tokens = {}
    with open("tokens.json", "r") as f:
        tokens = json.load(f)

    # 02: 从web_map.json提取坐标系
    # 读取地区配置文件
    cvat_setting_json_path = "resources/json/cvat_map_setting.json"

    if (not os.path.isfile(cvat_setting_json_path)):
        raise FileNotFoundError("cvat_map_setting.json文件不存在")

    cvat_map_setting = {}

    with open(cvat_setting_json_path, "r", encoding="utf-8") as f:
        cvat_map_setting = json.load(f)

    web_map_url = tokens["web-map_url"]
    generator = MapInfoGenerator("resources/web_map", cvat_map_setting)
    generator.gen(web_map_url)

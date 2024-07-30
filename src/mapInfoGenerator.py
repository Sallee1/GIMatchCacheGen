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

        self.curent_plugin_key = ""  # 当前的插件key
        self.current_obj_name = ""  # 当前的对象名称
        self.layer_info_dict = {}  # 待导出的地图信息json对象

    def _process_plugin(self, plugin_data: JsonObj) -> None:
        """递归处理overlay、children、chunks层级结构的信息生成"""
        template = plugin_data["urlTemplate"]
        self._process_level(template, plugin_data)

    def transform_bound(self, bounds: CVBounds, transform: JsonObj) -> CVBounds:
        new_bounds = list(bounds)
        scale: float = transform["scale"]
        translate: List[float] = transform["translate"]
        new_bounds = [new_bounds[i] * scale for i in range(4)]
        new_bounds[0] += translate[0]
        new_bounds[1] += translate[1]
        return (new_bounds[0], new_bounds[1], new_bounds[2], new_bounds[3])

    def _sanitize_and_build_path(self, url: str) -> str | None:
        """清理URL路径并构建本地文件路径"""
        match = re.match(r"^(https?://[^/]+)(/.*)", url)
        if not match:
            print(f"[error] URL格式不正确，无法提取路径：{url}")
            return ""
        url_path = match.group(2).lstrip("/")  # 移除前导斜杠
        # url解码
        url_path = urllib.parse.unquote(url_path)
        if (url_path is not None):
            # 检查url是否在排除名单中
            if ("web_map_layer_ignores" in self.cvat_map_setting):
                for ignore_path in self.cvat_map_setting["web_map_layer_ignores"]:
                    if (fnmatch.fnmatch(url_path, ignore_path)):
                        print(f"[warn] 跳过图像{url_path}")
                        return None

        out_path = os.path.join(self.rootpath, url_path)
        out_path = out_path.replace("\\", "/")
        return out_path

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

    def _union_bound(self, bound1: CVBounds, bound2: CVBounds) -> CVBounds:
        # Validate the input bounds
        if bound1[2] < 0 or bound1[3] < 0 or bound2[2] < 0 or bound2[3] < 0:
            raise ValueError("Width and height must be non-negative.")

        # Find the top-left corner of the union bounding box
        top_left_x = min(bound1[0], bound2[0])
        top_left_y = min(bound1[1], bound2[1])

        # Find the bottom-right corner of each bounding box
        bottom_right_x1 = bound1[0] + bound1[2]
        bottom_right_y1 = bound1[1] + bound1[3]
        bottom_right_x2 = bound2[0] + bound2[2]
        bottom_right_y2 = bound2[1] + bound2[3]

        # Find the bottom-right corner of the union bounding box
        bottom_right_x = max(bottom_right_x1, bottom_right_x2)
        bottom_right_y = max(bottom_right_y1, bottom_right_y2)

        # Calculate the width and height of the union bounding box
        width = bottom_right_x - top_left_x
        height = bottom_right_y - top_left_y

        return (top_left_x, top_left_y, width, height)

    def _get_img_path(self, level_data: JsonObj, template="", groupValue="", itemValue="", chunkValue="") -> str | None:
        path = None
        url = ""
        if ("url" in level_data):
            url = urllib.parse.unquote(level_data["url"])
        elif (path is None and len("urlTemplate") != 0):
            url = template
            if (len(groupValue) != 0):
                url = url.replace("{{groupValue}}", groupValue)
            if (len(itemValue) != 0):
                url = url.replace("{{itemValue}}", itemValue)
            if (len(chunkValue) != 0):
                url = url.replace("{{chunkValue}}", chunkValue)

            if ("{{" in url):
                return None

        path = self._sanitize_and_build_path(url)
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

    def _process_level(self, template: str, level_data: JsonObj, groupValue="", itemValue="", chunkValue="", bound: CVBounds | None = None) -> None:
        img_path: str | None = None  # 图像路径
        transform = self._get_current_transform(self.curent_plugin_key, groupValue, itemValue, chunkValue)  # 变换信息

        if "overlays" in level_data:
            for overlay in level_data["overlays"]:
                # overlay是顶级级别，清空已经存储的名字
                self.current_obj_name = None
                currentValue = overlay.get("value", "")
                if ("label" in overlay):
                    self.current_obj_name = overlay["label"]
                # 获取当前层级的变换
                transform = self._get_current_transform(self.curent_plugin_key, groupValue, itemValue, chunkValue)
                # 获取边界和图像路径
                bound = self._get_bound(overlay, transform)
                img_path = self._get_img_path(overlay, template, currentValue)
                self._write_map_info(currentValue, self.current_obj_name, bound, img_path, transform)
                self._process_level(template, overlay, currentValue, bound=bound)

            return

        if "children" in level_data:
            for child in level_data["children"]:
                currentValue = child.get("value", "")
                if ("label" in child):
                    self.current_obj_name = child["label"]
                transform = self._get_current_transform(self.curent_plugin_key, groupValue, itemValue, chunkValue)
                # 获取边界和图像路径
                child_bound = self._get_bound(child, transform)
                if(child_bound is not None):
                    bound = child_bound
                
                img_path = self._get_img_path(child, template, groupValue, currentValue)
                self._write_map_info(currentValue, self.current_obj_name, bound, img_path, transform)
                # 如果有chunks，则使用chunk提供的bound
                if ("chunks" in child):
                    bound = None
                self._process_level(template, child, groupValue, currentValue, bound=bound)

        if "chunks" in level_data:
            chunk_json_array: JsonArray = []
            for chunk in level_data["chunks"]:
                currentValue = chunk.get("value", "")
                # chunk不对名字改写
                transform = self._get_current_transform(self.curent_plugin_key, groupValue, itemValue, chunkValue)
                # 获取边界和图像路径
                chunk_bound = self._get_bound(chunk, transform)
                chunk_img_path = self._get_img_path(chunk, template, groupValue, itemValue, currentValue)

                if (chunk_bound is None or chunk_img_path is None):
                    continue
                # 将chunk的边界框组合起来
                if (bound is None):
                    bound = chunk_bound
                else:
                    bound = self._union_bound(bound, chunk_bound)
                chunk_json_array.append({
                    "img_path": chunk_img_path,
                    "bound": chunk_bound,
                })

            self._write_map_info(itemValue, self.current_obj_name, bound, img_path, transform, chunk_json_array)

    def _write_map_info(self, value: str, name: str | None, bound: CVBounds | None, img_path: str | None, transform: JsonObj|None, chunks: JsonArray | None = None) -> None:
        if (bound is not None and (img_path is not None or chunks is not None)):
            layer_info_obj = {}
            if(name is not None):layer_info_obj["name"] = name
            if(bound is not None):layer_info_obj["bound"] = bound
            if(img_path is not None):layer_info_obj["img"] = img_path
            if(chunks is not None):layer_info_obj["chunks"] = chunks
            #对于坐标系，特殊处理
            if(transform is not None):
                if("map" in transform): 
                    map_info_obj = self.cvat_map_setting["map_info"][transform["map"]] 
                    layer_info_obj["map"] = map_info_obj["key"]
                    layer_info_obj["offset"] = map_info_obj["center"]
                    
                if("coord_systems" in transform):
                    coord_system_obj = self.cvat_map_setting["coord_systems"][transform["coord_systems"]]
                    layer_info_obj["type"] = str(transform["coord_systems"]).upper()
                    layer_info_obj["scale_img"] = coord_system_obj["scale_img"]
                    layer_info_obj["scale_axes"] = coord_system_obj["scale_axes"]
                    layer_info_obj["zoom"] = coord_system_obj["zoom"]
            self.layer_info_dict[value] = layer_info_obj
            print(f"[info] 写入数据\"{value}\"({name})")

    def gen(self, webmap_url: str):
        """获取web_map.json文件"""
        try:
            response = requests.get(webmap_url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"获取web_map.json失败，原因：{e}")
            return {}

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

        return self.layer_info_dict


if __name__ == "__main__":
    cwd = os.getcwd()

    # 01: 解析token文件
    with open("tokens.json", "r") as f:
        tokens = json.load(f)

    # 02: 从web_map.json提取坐标系
    # 读取地区配置文件
    cvat_setting_json_path = "resources/json/cvat_map_setting.json"
    with open(cvat_setting_json_path, "r", encoding="utf-8") as f:
        cvat_map_setting = json.load(f)

    web_map_url = tokens["web-map_url"]
    generator = MapInfoGenerator("resources/web_map", cvat_map_setting)
    raw_web_map_info = generator.gen(web_map_url)

    # 合并地图信息
    with open("resources/json/raw_extra_map_info.json", "r", encoding="utf-8") as f:
        raw_extra_map_info = json.load(f)
    for key in raw_extra_map_info.keys():
        raw_web_map_info.update({key: raw_extra_map_info[key]})

    with open("resources/json/raw_merged_map_info.json", "w", encoding="utf-8") as f:
        json.dump(raw_web_map_info, f, indent=4, ensure_ascii=False)

    print(f"[info] 已合并地图信息到{cwd}/resources/json/raw_merged_map_info.json")

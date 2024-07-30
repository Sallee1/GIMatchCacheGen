import copy
import json
import os
from typing import Any, Dict, List, Tuple

import cv2

KYBounds = Tuple[Tuple[float, float], Tuple[float, float]]
CVBounds = Tuple[float, float, float, float]
JsonObj = Dict[str, Any]
JsonArray = List[Any]
JsonList = List[Any]


class KeypointCacheGenerator:
    def __init__(self, respath: str, outpath: str, cvat_map_setting: JsonObj):
        self.respath = respath
        self.outpath = outpath
        self.cvat_map_setting = cvat_map_setting

        surf_descriptor = cv2.xfeatures2d.SURF()
        surf_descriptor.create(
            hessianThreshold=cvat_map_setting.get("hessianThreshold", 100),
            nOctaves=cvat_map_setting.get("nOctaves", 4),
            nOctaveLayers=cvat_map_setting.get("nOctaveLayers", 2),
            extended=cvat_map_setting.get("extended", False),
            upright=cvat_map_setting.get("upright", False)
        )

    def _convert_map_info(self, layer_key: str, layer_obj: JsonObj):
        out_layer_info = copy.deepcopy(layer_obj)
        out_layer_info.pop("img_path", None)
        out_layer_info.pop("chunks", None)
        out_layer_info["cache_path"] = os.path.join(self.outpath, f"{layer_key}.dat").replace("\\", "/")
        return out_layer_info

    def genTiles(self, raw_tile_info: JsonObj):
        pass

    def genLayers(self, raw_map_info: JsonObj):
        layer_info_dict = {}
        # 遍历raw_map_info中的每个条目
        for layer_key in raw_map_info.keys():
            layer_info_dict[layer_key] = self._convert_map_info(layer_key, raw_map_info[layer_key])

        return layer_info_dict


if __name__ == "__main__":
    cwd = os.getcwd()
    # 01: 初始化缓存生成类
    cvat_setting_json_path = "resources/json/cvat_map_setting.json"
    with open(cvat_setting_json_path, "r", encoding="utf-8") as f:
        cvat_map_setting = json.load(f)

    generator = KeypointCacheGenerator("resources/web_map", "output", cvat_map_setting)

    # 02：开始生成缓存
    raw_info_json_path = "resources/json/raw_merged_map_info.json"
    with open(raw_info_json_path, "r", encoding="utf-8") as f:
        raw_info_json = json.load(f)

    map_info = generator.genLayers(raw_info_json)

    # 03：保存地图信息头
    map_info_json_path = "output/map_info.json"
    with open(map_info_json_path, "w", encoding="utf-8") as f:
        json.dump(map_info, f, ensure_ascii=False, indent=4)

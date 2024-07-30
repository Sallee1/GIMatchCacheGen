import copy
import json
import os
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

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

    def _alpha_blend(self, fore: np.ndarray, back: np.ndarray):
        """
        将前景图像与背景图像混合，图像尺寸需要相同且使用8位存储，使用透明度通道作为混合权重
        """
        # 转换为浮点数
        fore = fore.astype(np.float32) / 255.0
        back = back.astype(np.float32) / 255.0

        if (fore.shape[2] == 3):
            # 前景为非透明图像，会完全覆盖背景，直接返回前景图
            out_img = np.zeros((fore.shape[0], fore.shape[1], 4), dtype=np.uint8)
            out_img[:, :, :3] = fore
            return out_img

        fore_alpha = fore[:, :, 3]
        back_alpha = back[:, :, 3]

        out_img = np.zeros((fore.shape[0], fore.shape[1], 4), dtype=np.float32)
        out_img[:, :, :3] = fore[:, :, :3]*fore_alpha[:, :, np.newaxis] + back[:, :, :3] * (1 - fore_alpha[:, :, np.newaxis])
        out_img[:, :, 3] = fore_alpha + back_alpha * (1 - fore_alpha)
        out_img = np.clip(out_img, 0, 1) * 255.0
        out_img = out_img.astype(np.uint8)
        return out_img

    def _mix_img(self, src_img: np.ndarray, dst_img: np.ndarray, tl: Tuple[int, int]) -> np.ndarray:
        """
        自动混合并扩展图像
        :param src_img: 源图像
        :param dst_img: 目标图像
        :param tl: 目标图像左上角坐标（先x后y）
        """
        # 扩展图像
        expand_dst = (max(-tl[0], 0),
                      max(-tl[1], 0),
                      max(dst_img.shape[1], tl[0] + src_img.shape[1]) - dst_img.shape[1],
                      max(dst_img.shape[0], tl[1] + src_img.shape[0]) - dst_img.shape[0])
        expand_dst_img = cv2.copyMakeBorder(dst_img, expand_dst[1], expand_dst[3], expand_dst[0], expand_dst[2], cv2.BORDER_CONSTANT, value=[0, 0, 0, 0])

        expand_src_img = np.zeros(expand_dst_img.shape, dtype=np.uint8)
        expand_src_img[max(tl[1], 0): max(tl[1], 0) + src_img.shape[0], max(tl[0], 0):max(tl[0], 0)+src_img.shape[1]] = src_img

        return self._alpha_blend(expand_src_img, expand_dst_img)

    def _convert_map_info(self, layer_key: str, layer_obj: JsonObj):
        out_layer_info = copy.deepcopy(layer_obj)
        out_layer_info.pop("img_path", None)
        out_layer_info.pop("chunks", None)
        out_layer_info.pop("scale_img", None)
        out_layer_info.pop("scale_axes", None)
        out_layer_info["cache_path"] = os.path.join(self.outpath, f"{layer_key}.dat").replace("\\", "/")
        return out_layer_info

        # 合并块，返回合并后的图像

    debug_img_id = 0

    def _merge_chunks(self, layer_info: JsonObj) -> np.ndarray | None:
        scale_img: float = layer_info["scale_img"]
        scale_axes: float = layer_info["scale_axes"]

        bound_merge: CVBounds = (0, 0, 0, 0)  # 合并后的图像的边界框

        merge_img: np.ndarray | None = None

        for chunk in layer_info["chunks"]:
            img_path = os.path.join(self.respath, chunk["img_path"])
            img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
            if (img is None):
                print(f"[Error] {img_path} 不是有效的图像路径")
                return None

            img = cv2.resize(img, (int(img.shape[1] * scale_img), int(img.shape[0] * scale_img)), interpolation=cv2.INTER_AREA)
            # 当读取第一幅图片
            if (merge_img is None):
                merge_img = img
                bound_merge = chunk["bound"]

                continue
            # 读取其他图像，根据坐标合并
            bound_cur = chunk["bound"]
            bound_old = bound_merge
            bound_merge = self._union_bound(bound_merge, bound_cur)

            # 新图像的左上角坐标
            cur_img_tl = (int((bound_cur[0] - bound_old[0]) / scale_axes), int((bound_cur[1] - bound_old[1]) / scale_axes))

            # 合并图像
            merge_img = self._mix_img(img, merge_img, cur_img_tl)

        # 测试图像合并效果
        if (merge_img is not None and len(layer_info["chunks"]) > 1):
            cv2.imwrite(os.path.join(self.outpath, f"test_{self.debug_img_id:0>5}.png"), merge_img)
            self.debug_img_id += 1
        return merge_img

    def genTiles(self, raw_tile_info: JsonObj):
        pass

    def genLayers(self, raw_map_info: JsonObj):
        layer_info_dict = {}
        # 遍历raw_map_info中的每个条目，生成最终地图信息
        for layer_key in raw_map_info.keys():
            layer_info_dict[layer_key] = self._convert_map_info(layer_key, raw_map_info[layer_key])

            # 如果地图下有子分块，将其合并起来生成图像
            if ("chunks" in raw_map_info[layer_key]):
                img = self._merge_chunks(raw_map_info[layer_key])
            else:
                img_path = os.path.join(self.respath, raw_map_info[layer_key]["img_path"])
                img = cv2.imread(img_path)

        return layer_info_dict


if __name__ == "__main__":
    cwd = os.getcwd()
    # 01: 初始化缓存生成类
    cvat_setting_json_path = "resources/json/cvat_map_setting.json"
    with open(cvat_setting_json_path, "r", encoding="utf-8") as f:
        cvat_map_setting = json.load(f)

        generator = KeypointCacheGenerator(".", "output", cvat_map_setting)

    # 02：开始生成缓存
    raw_info_json_path = "resources/json/raw_merged_map_info.json"
    with open(raw_info_json_path, "r", encoding="utf-8") as f:
        raw_info_json = json.load(f)

    map_info = generator.genLayers(raw_info_json)

    # 03：保存地图信息头
    map_info_json_path = "output/map_info.json"
    with open(map_info_json_path, "w", encoding="utf-8") as f:
        json.dump(map_info, f, ensure_ascii=False, indent=4)

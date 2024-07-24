# cvat_map_setting.json 格式说明

cvat_map_setting.json用于配置生成缓存的流程

* layer_ignores: 通过web_map.json下载文件和生成缓存时忽略的图像，支持通配符
* coord_systems: 坐标系配置

```json
{
    "web_map_layer_ignores": [
        "tile_qd28/*",
        "d/underground/雨林/*",
        "d/underground/沙漠/*",
        "d/underground/沙囿/*",
        "d/underground/4.8/*"
    ],
    "coord_systems": {
        "map_back": {
            "extend": "default",
            "scale_img": 0.5859375,
            "scale_axes": 3.4133333,
            "zoom": 1.0
        },
        "sea": {
            "extend": "map_back",
        },
        "cave": {
            "extend": "map_back",
            "scale_img": 1.171875,
            "scale_axes": 1.7066666,
            "zoom": 2.0
        },
        "city": {
            "extend": "map_back",
            "scale_img": 1.7578125,
            "scale_axes": 1.1377777,
            "zoom": 3.0
        },
        "yuanxiagong":
        {
            "extend": "map_back",
            "center": [16384,10240],
        },
        "cenyanjuyuan":
        {
            "extend": "map_back",
            "center": [16384,4096],
        },
        "jiurizhihai":
        {
            "extend": "map_back",
            "center": [16384, -1024],
        },
        "jiurizhihai_sea":
        {
            "extend": "sea",
            "center": [16384, -1024],
        },
        "jiurizhihai_cave":
        {
            "extend": "sea",
            "center": [16384, -1024],
        }
    },

}
```

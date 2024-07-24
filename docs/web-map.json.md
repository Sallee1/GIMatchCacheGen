# web-map.json格式说明

web-map.json中有关于地图图层的核心配置在plugins[].overlayConfig中

overlayConfig由三级结构组成：

* 组(group): 由多个图层组成的互斥组
* 层(item): 图层显示的基本单位
* 块(chunk): 由于图层有可能被切分，用于表示每一个被切分的分块，不能单独存在

overlayConfig的每一个级别均支持可重写bounds表示边界，这个边界可以被更低的级别重写

生成地图信息文件时遵循以下规则：

* 边界框确定：以不小于item级别的bounds作为地图的边界框，如果最低级别没有bounds，则继承上一级的bounds
* 边界框处理特殊情况：如果item级别没有bounds，但item含有chunks，则bounds为chunks的边界的并集
* 无边界框的情况：如果上级和chunks均没有提供bounds，则跳过生成
* 对应图像确认：遍历所有叶子节点，将value填充到链接模板中
* 硬编码url的情况：如果某个级别存在硬编码的url，则作为单独的图层生成，bounds采用当前级别的边界或者从上级继承
* 最低级别为chunks的图像：同时记录图像和对应的bounds信息作为辅助定位信息，与item中的bounds独立。在生成缓存步骤后，chunks的图像将合并为一个块，且辅助定位信息被擦除

```json
{
    "urlTemplate":"https://url.to/{{groupValue}}/{{itemValue}}/{{chunkValue}}.png",
    "overlays":[
        {
            "label":"组标签",
            "value":"groupValue",  //替代{{groupValue}}
            "bounds":[[0,0],[100,100]],     //【可选】当前组的边界
            "url":"https://url.to/groupValue.png", //【可选】代替urlTemplate，直达链接
            "children":[
                {
                    "label":"层标签",
                    "value":"itemValue",  //替代{{itemValue}}
                    "bounds":[[0,0],[100,100]],     //【可选】当前层边界，重写组边界
                    "url":"https://url.to/itemValue.png", //【可选】代替urlTemplate，直达链接
                    "chunks":[
                        {
                            "value":"chunkValue",  //替代{{chunkValue}}
                            "bounds":[[0,0],[100,100]],     //【可选】当前块边界，重写层边界
                            "url":"https://url.to/chunkValue.png" //【可选】代替urlTemplate，直达链接
                        }
                    ]
                }
            ]
        }
    ]
}
```

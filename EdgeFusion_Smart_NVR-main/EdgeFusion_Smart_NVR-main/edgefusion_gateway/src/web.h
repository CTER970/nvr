#ifndef EDGEFUSION_WEB_H
#define EDGEFUSION_WEB_H

#include "conf.h"

/* 启动内嵌 HTTP 服务器。
 * 端点一览：
 *   GET  /                  静态首页 web_root/index.html
 *   GET  /stream            MJPEG 实时预览
 *   GET  /api/status        聚合状态 JSON
 *   GET  /api/snapshot      单张 JPEG 抓图
 *   GET  /api/recordings    MP4 录像段列表 JSON
 *   GET  /api/events        事件列表 JSON（支持 ?limit=&offset=&type= 查询参数）
 *   GET  /api/event/<id>    单条事件详情 JSON
 *   GET  /api/config        当前配置 JSON（敏感字段已掩码）
 *   POST /api/config        更新配置（JSON 请求体），保存并触发热更新
 *   GET  /rec/<name>        提供 MP4 录像（支持 HTTP Range 分段请求）
 *   GET  /snap/evt_<id>.jpg 提供事件抓拍 JPEG
 *   GET  /<path>            web_root 下的其他静态文件
 */
int  web_start(const gateway_conf_t *cfg);
void web_stop(void);

#endif

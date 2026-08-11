# q1 Seedance 2.0 API 操作规范

## 1. 配置文件

`doubao_api_config.json`：

```json
{
  "api_key": "你的API_KEY",
  "base_url": "https://chat.q1.com/v1",
  "model": "doubao-seedance-2.0"
}
```

API Key 只能保存在本地，不要写入代码、聊天记录或版本库。

## 2. 鉴权方式

所有请求携带：

```http
Authorization: Bearer 你的API_KEY
```

## 3. 上传本地素材

上传接口不带 `/v1`。

### 上传视频

```http
POST https://chat.q1.com/api/upload/video
Content-Type: multipart/form-data
```

表单字段：

- `file`：本地 MP4/MOV 文件
- `convert=false`

返回结果中的 `filename` 是生成任务需要使用的视频 URL。

### 上传音频

```http
POST https://chat.q1.com/api/upload/audio
Content-Type: multipart/form-data
```

表单字段：

- `file`：本地 MP3/WAV 文件
- `convert=false`
- `compress=false`

同样读取返回结果中的 `filename`。

## 4. 提交视频生成任务

```http
POST https://chat.q1.com/v1/videos
Content-Type: application/json; charset=utf-8
```

参考请求：

```json
{
  "model": "doubao-seedance-2.0",
  "prompt": "生成要求和台词约束",
  "n": 1,
  "size": "480x854",
  "seconds": "4",
  "aspect_ratio": "9:16",
  "quality": "480p",
  "generate_audio": true,
  "reference_video": "上传视频返回的filename",
  "reference_audio": "上传音频返回的filename"
}
```

重要规则：

- `reference_video` 和 `reference_audio` 必须填写上传接口返回的 URL。
- 需要生成声音时设置 `generate_audio: true`。
- `seconds` 使用字符串，例如 `"4"`。
- 一次测试建议固定 `n: 1`，避免重复计费。
- 服务可能根据参考视频保留接近的原始尺寸，因此实际输出不一定严格等于 `size`。
- 提交成功会返回任务 `id`，必须保存。

## 5. 查询任务状态

```http
GET https://chat.q1.com/v1/videos/{任务ID}
```

主要状态：

- `queued`：排队中
- `in_progress`：生成中
- `completed`：完成
- `failed`：失败

建议每 10–15 秒查询一次。不要因为进度长时间不变而重复提交。

## 6. 下载成品

任务完成后调用：

```http
GET https://chat.q1.com/v1/videos/{任务ID}/content
```

请求仍需携带鉴权头，并允许跟随 HTTP 重定向。响应内容保存为 `.mp4` 文件。

## 7. 推荐完整流程

```text
读取本地配置
→ 检查素材
→ 上传参考视频
→ 上传参考音频
→ 保存两个 filename
→ 提交 /v1/videos
→ 保存任务 ID
→ 每 10–15 秒查询状态
→ completed 后下载视频
→ 检查时长、尺寸和音轨
```

## 8. 异常处理规范

- `401/403`：检查 API Key、权限或余额。
- `404`：检查接口地址，不要把上传接口错误地拼接在 `/v1` 后面。
- `422`：检查字段类型、尺寸、时长和素材 URL。
- `failed`：记录返回的 `error`，修改参数后再提交。
- 网络超时：先用原任务 ID 查询状态，不要直接重新生成。
- 中文提示词必须按 UTF-8 编码发送，否则可能出现乱码。
- 日志不得打印 API Key，也不要记录完整鉴权头。
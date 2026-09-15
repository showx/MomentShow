# MomentShow

打开你本机已登录的微信，读取当前屏幕上可见的朋友圈，并存成只在这台电脑上的时间线。

微信没有朋友圈官方接口。这个工具只做三件事：拉起 `/Applications/微信.app`、尽量点开「朋友圈」、对**当前窗口里已经显示出来的文字**做截图 OCR。它不会解密微信数据库，也不会注入微信进程。

## 环境

- macOS
- Python 3.10+
- 已安装并登录 [微信 4 for Mac](https://mac.weixin.qq.com/)

```bash
cd MomentShow
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

第一次采集前，给运行它的终端（或 Cursor）打开两项权限：

1. 系统设置 → 隐私与安全性 → 辅助功能
2. 系统设置 → 隐私与安全性 → 屏幕录制

## 使用

采集当前可见朋友圈：

```bash
momentshow capture
```

若自动点击找不到入口，先自己点开朋友圈，再采集当前窗口：

```bash
momentshow capture --manual
```

打开本地时间线（默认 http://127.0.0.1:8765 ）：

```bash
momentshow serve
```

查看状态：

```bash
momentshow status
```

数据文件在 `~/Library/Application Support/MomentShow/moments.db`。

## 限制

- 只能读到采集时窗口里出现过的内容，不是完整历史。
- 昵称、时间和正文来自 OCR，图片动态可能只有作者和时间。
- 采集过程会把微信带到前台并滚动窗口，请不要同时操作鼠标。
- 未登录时无法替你扫码。

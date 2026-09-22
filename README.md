# MomentShow

打开你本机已登录的微信，读取当前屏幕上可见的朋友圈，并存成只在这台电脑上的时间线；也可以读取当前聊天窗口，生成回复草稿，等你确认后再填入或发送。

微信没有朋友圈或个人聊天官方接口。这个工具只做屏幕上已经显示出来的事：拉起 `/Applications/微信.app`、尽量点开「朋友圈」、对**当前窗口里已经显示出来的文字**做截图 OCR，并在你确认后用剪贴板把草稿贴进输入框。它不会解密微信数据库，也不会注入微信进程。

读聊天时优先只扫右侧聊天区，不扫左侧会话列表。微信 4 for Mac 的辅助功能树几乎不暴露气泡文字，所以不能用系统朗读树代替 OCR。

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

第一次采集或帮你回之前，给运行它的终端（或 Cursor）打开两项权限：

1. 系统设置 → 隐私与安全性 → 辅助功能
2. 系统设置 → 隐私与安全性 → 屏幕录制

## 使用

双击 `MomentShow.command`，或：

```bash
momentshow
```

会打开桌面窗口。默认在「帮我回」：先在微信里打开会话，点「读取当前聊天」，改草稿后再「填入」或「填入并发送」。上面切到「朋友圈」即可采集时间线。

命令行仍可用，但不是主入口：

```bash
momentshow capture
momentshow capture --manual
momentshow chat
momentshow chat --fill 1
momentshow serve
momentshow status
```

数据文件在 `~/Library/Application Support/MomentShow/moments.db`。最近一次聊天草稿缓存在同目录的 `chat_session.json`。

## 模型草稿（可选）

没配模型时用规则草稿：顺着说、简短收到、晚点再回。`.env` 里 `MOMENTSHOW_LLM_PROVIDER` 选 `openai` 或 `ollama`，两套都保留，改 PROVIDER 并启用对应那一组即可。失败会自动回退规则草稿。

OpenAI 或兼容接口：

```bash
MOMENTSHOW_LLM_PROVIDER=openai
MOMENTSHOW_LLM_API_KEY=sk-...
MOMENTSHOW_LLM_BASE_URL=https://api.openai.com/v1
MOMENTSHOW_LLM_MODEL=gpt-4o-mini
```

本地 Ollama（当前默认是本机的 `qwen3.8:27b`）：

```bash
MOMENTSHOW_LLM_PROVIDER=ollama
MOMENTSHOW_LLM_BASE_URL=http://127.0.0.1:11434/v1
MOMENTSHOW_LLM_MODEL=qwen3.8:27b
```

也可以放在 `~/Library/Application Support/MomentShow/.env`。已在 shell 里 export 的同名变量优先。`.env` 已加入 gitignore，不会进仓库。用 Ollama 前先确保 `ollama serve` 在跑。

## 限制

- 只能读到采集或读取时窗口里出现过的内容，不是完整历史。
- 昵称、时间和正文来自 OCR，图片动态或纯图片消息可能没有正文。
- 聊天左右气泡靠位置判断，OCR 可能把昵称、时间、气泡混在一起。
- 个人微信没有官方接口；本机库是加密的，这里不会去解密或注入进程。聊天读取目前只能靠屏幕 OCR。
- 采集、读取和填入都会把微信带到前台；填入会占用剪贴板。请不要同时操作鼠标。
- 不会自动发送。只有你明确选择「填入并发送」或 `chat --send` 才会回车。
- 未登录时无法替你扫码。

# 桌面宠物工坊（Python / PySide6）

经典透明 PNG 桌宠：工具窗管理 + 置顶宠窗互动。

> 默认宠物素材来自公开的 Codex 桌宠画廊（粉丝作品），**仅供个人学习，请勿商用分发**。见 `assets/pets/NOTICE.txt`。

## 功能

- 默认五宠真实多帧动画：待机、左右走动、招手、跳跃、跳舞、思考、害羞、挨打、消失/出现
- 配件：**预烘整套帧包**切换（头部/眼睛/倾角逐帧对位，帽子含阴影、材质和高光），解码缓存后即时切换
- 关键词对话：宠物身上内联输入框，回车即回，并触发对应动作
- 一对一互联网联机：花生壳映射 + 邀请码、端到端加密、第二只远程宠物、原文气泡和手动动作同步
- 桌面走动（可开关）、缩放、系统托盘
- 单实例运行：重复启动会直接退出，避免出现两个托盘图标

<img width="1069" height="612" alt="ScreenShot_2026-08-17_110612_564" src="https://github.com/user-attachments/assets/486c59f8-adef-4100-828c-ad988db427e8" />



## 默认宠物

| ID | 名称 | 素材来源 |
|----|------|----------|
| `nailong` | 奶龙 | `erich207/nailong-codex-pet` |
| `dagongniu` | 打工牛 | 画廊 `niumou--jarvis-2` |
| `salarycat` | 打工猫 | 画廊 `salary-cat--zuochunjie` |
| `koukou` | 扣扣企鹅 | 画廊 `koukou-penguin--hoody` |
| `capybara` | 水豚噜噜 | 画廊 `capybara-lulu--jiushu` |

要增加宠物可拿到对应精灵表（1536×1872 或 1536×2288 的 8 列 webp/png），放入 `data/_sheet_cache/<id>.webp`
后在 `scripts/build_pets.py` 的 `PETS` 里加一条，再重建即可。

## 运行

必须在项目根目录：

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m app.main
```

或双击根目录的 `run.bat`。

打包 Windows 免安装发布版：

```powershell
.\.venv\Scripts\pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

输出位于 `release\DesktopPetWorkshop-v1.0.3-win64.zip`。目标电脑无需安装 Python，必须解压并复制整个文件夹，不能只复制 EXE。

重建默认素材与配件帧包（联网下载精灵表，约 1 分钟）：

```powershell
.\.venv\Scripts\python scripts\build_pets.py            # 全部
.\.venv\Scripts\python scripts\build_pets.py nailong    # 单个
```

自检：

```powershell
.\.venv\Scripts\python scripts\smoke_test.py
.\.venv\Scripts\python scripts\peer_smoke_test.py
.\.venv\Scripts\python scripts\online_ui_smoke_test.py
```

## 互联网联机

联机仅支持双方都有的五只默认宠物，一次连接两位用户。

主机先在花生壳创建 HTTP 或 HTTPS 映射，映射到本机端口 `38475`。然后在工坊填写映射地址并点击“创建邀请码”，把邀请码发给好友；好友粘贴邀请码后点击“加入邀请码”。聊天文字与动作数据会在两台电脑之间加密，花生壳映射只负责转发。

HTTP 地址会自动转换为 `ws://`，HTTPS 地址会自动转换为 `wss://`。HTTP 不加密传输层，正式使用建议改为 HTTPS。花生壳是否对当前映射透传 WebSocket 升级请求，必须以实际联机测试结果为准。

## 桌宠操作

| 操作 | 说明 |
|------|------|
| 左键拖拽 | 移动（仅点在非透明像素上） |
| 双击 | 打开聊天输入框 |
| 右键 → 做动作 | 招手 / 跳一下 / 跳舞 / 思考 / 害羞 / 打它 |
| 右键 → 配件 | 9 套预烘配件即时切换 |
| 右键 → 缩放、桌面走动、打开工坊 | 其余设置 |
| 托盘 | 显示宠物 / 打开工坊 / 退出 |



## 宠物包结构

```text
assets/pets/<id>/  或  data/user_pets/<id>/
  manifest.json
  base.png
  actions/<action>/*.png
  variants/<accessory_id>/<action>/*.png
```

## 技术栈

Python 3.10+ · PySide6 · Pillow · cryptography

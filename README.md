# 桌面宠物工坊（Python / PySide6）

经典透明 PNG 桌宠：工具窗管理 + 置顶宠窗互动。

> 默认宠物素材来自公开的 Codex 桌宠画廊（粉丝作品），**仅供个人学习，请勿商用分发**。见 `assets/pets/NOTICE.txt`。

## 功能

- 默认五宠真实多帧动画：待机、左右走动、招手、跳跃、跳舞、思考、害羞、挨打、消失/出现
- 配件：**预烘整套帧包**切换（头部/眼睛/倾角逐帧对位，帽子含阴影、材质和高光），解码缓存后即时切换
- 关键词对话：宠物身上内联输入框，回车即回，并触发对应动作
- 一对一互联网联机：公网 IP 直连、口令端到端加密、第二只远程宠物、原文气泡和手动动作同步
- 桌面走动（可开关）、缩放、系统托盘
- 单实例运行：重复启动会直接退出，避免出现两个托盘图标

<img width="845" height="584" alt="128e39c0-8548-45db-86cb-6ec07cf8d5aa" src="https://github.com/user-attachments/assets/7cf87143-44df-4134-b330-3f81afcc0028" />


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

输出位于 `release\DesktopPetWorkshop-win64.zip`。目标电脑无需安装 Python，必须解压并复制整个文件夹，不能只复制 EXE。

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

1. 主机在路由器中把 TCP 端口（默认 `38475`）转发到运行桌宠的电脑。
2. 主机在工坊填写至少 6 位的临时口令，点击「作为主机」。
3. 主机把公网 IPv4（或域名）、端口和口令发给对方。
4. 对方填写这些信息，点击「连接主机」。
5. 连接后，双方输入的原文会显示在己方宠物上；手动触发的动作也会同步。

运营商 NAT、未配置端口转发或防火墙未放行时，互联网直连无法建立。口令不写入设置文件；握手和后续消息使用 Fernet 加密及完整性校验。

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

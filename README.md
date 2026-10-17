# 创绿家除醛仪 Home Assistant 集成

通过创绿家云端 API（抓包逆向，个人自用）把「智能除醛仪 Pro Max」接入 Home Assistant。

## 功能

| 实体 | 说明 |
|---|---|
| 开关「电源」 | 开机 / 关机（关机复位报文与小程序一致） |
| 开关「童锁」 | 童锁开关 |
| 开关「睡眠模式」 | 对应小程序睡眠开关 |
| 选择器「设备位置」 | 客厅/主卧/书房等 25 个位置，修改即同步到云端 |
| 选择器「工作模式」 | 智能 / 强效 / 母婴（抓包实测映射） |
| 数字「强效档位」 | 1–4 档（协议编码 15/30/60/120；3档为推测。界面剩余时长恒显示30分钟） |
| 风扇「强效净化」 | 强效模式独立实体：开关=进入强效/切回智能，4 档调速（25/50/75/100%）；关机会先开机再进强效 |
| 传感器「甲醛浓度」 | 云端实时数据（environmentalData/view），μg/m³，随设备上报自动更新 |
| 传感器「运行状态」 | 诊断信息：模式/风机/固件/累计运行等 |
| 二元「甲醛超标」 | 云端 exceed 字段 |
| 二元「在线」 | 设备在线状态 |

- 状态轮询默认 60 秒/次（可在「选项」里改），趋势 15 分钟/次。
- token 失效（云端 code:9）时会用 openId + 手机号**自动重新登录**，无需人工干预。

## 安装

1. 把本目录下的 `custom_components/chuanglvjia` 整个复制到 Home Assistant 配置目录的 `custom_components/` 下。
2. 重启 Home Assistant。
3. 「设置 → 设备与服务 → 添加集成」→ 搜索「创绿家」。
4. 填写：
   - **微信 openId**（`oyv-` 开头的字符串），获取方式：
     1. 用手机微信打开创绿家小程序，同时开启抓包工具（手机端可用 HttpCanary / Stream，电脑端可用 Charles / Fiddler）；
     2. 在登录请求 `POST /ae_oss/wx/user/oneKeyEmpower` 的**请求体**里找到 `openId` 字段并复制；
     3. 如果小程序已有登录缓存、不会发登录请求：先在微信里删除该小程序（或清除小程序缓存），再重新打开，就会触发一次登录，抓到 openId；
     4. 本集成的调试日志 / 之前的抓包文件里若已有 `oneKeyEmpower` 记录，也可直接从中复制。
   - **绑定手机号**：创绿家账号绑定的手机号。
   - **绑定显示名**：可留默认「微信用户」。

要求 Home Assistant ≥ 2024.8（使用了新版 ConfigEntry / OptionsFlow API）。

> 集成图标为本项目原创绘制（净化器 + 绿叶 + 分子意象），存放在 `brand/icon.png` 与 `brand/logo.png`（HA 只从集成目录下的 `brand/` 文件夹读取品牌图）。未使用创绿家官方 logo 或商标素材，仅个人自用集成展示，与官方无关联。放置后需**重启 HA 并强制刷新浏览器**（Ctrl+F5）才会显示。

## 重要须知：单会话互踢

创绿家云端是**单 token 会话**：每次重新登录都会踢掉上一个 token。

- 手机小程序**冷启动**会自动重新登录 → HA 的 token 会失效 → HA 会在下个轮询周期自动换新 token → 小程序又被踢。
- 影响：你打开小程序后约 1 分钟内可能提示重新登录；再开一次小程序即可，如此往复。
- 若你主要用手机小程序、HA 只做只读自动化，可以把轮询间隔调大，减少互踢频率。

## 工作模式映射（已实测定稿）

| 模式 | 报文 |
|---|---|
| 智能 | `workMode:0, workModeStatus:0` |
| 强效 | `workMode:2, time:<档位编码>, workModeStatus:3` |
| 母婴 | `workMode:4, workModeStatus:1` |

强效档位编码在 `time` 字段：1档=15、2档=30、4档=120（实测），3档=60（推测）。注意：协议里的 time 是档位编码，**不是**界面上的剩余时长——小程序界面对所有档位都显示「剩余30分钟」。

## 已知限制

- 甲醛浓度是**每小时平均值**（云端 `environmentalData/trend` 接口），不是秒级实时值；实时值走 WebSocket，协议尚未破解。
- 该 trend 接口云端未做 token 校验（仅凭设备码可读），本集成会利用这一点做免鉴权轮询；同时也是厂商侧的安全瑕疵，建议向创绿家反馈。
- 非官方接口，厂商随时可能变更；仅供个人自用，请自行评估风险。

## 目录结构

```
custom_components/chuanglvjia/
├── __init__.py        # 入口：运行时数据、平台装载
├── api.py             # 云端客户端：oneKeyEmpower 登录 / device/view / sendIns / trend
├── binary_sensor.py   # 超标、在线
├── config_flow.py     # 配置流 + 选项（轮询间隔）
├── const.py           # 常量、模式映射
├── coordinator.py     # 设备状态 / 趋势两个协调器
├── entity.py          # 设备实体基类
├── manifest.json
├── number.py          # 定时分钟
├── select.py          # 工作模式
├── sensor.py          # 甲醛浓度、运行状态
├── strings.json
├── switch.py          # 电源、童锁
└── translations/
    ├── en.json
    └── zh-Hans.json
```

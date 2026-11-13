# 交接文档：剩余工作与推进估算

> **更新：2026-11-13（A2 完成交接点）。** 基线 = P1.5 + P2 + P3 + P4 + P5 创作页 +
> H7a–H7f（谱面/曲库/考核/自动伴奏/映射与预设）+ 启动整理 + 试弹体验修正 +
> **H9a 公开版过滤/打包 guardrails** + **H9b 前五批（减少动效/非颜色对错提示、
> 字号缩放、曲库扫描缓存、导航/设置/走带键盘可达、音轨/键位页/学习卡键盘可达）**
> + **P2-G G1 指导书结构升级与阶段 0 三节试点** + **G2 阶段 1–2 十二节**
> + **G3a 阶段 3–4 十六节** + **G3b1 阶段 5–6 十五节**
> + **G3b2 阶段 7–8 十一节** + **G4a 练习步骤勾选持久化**
> + **G4b 知识卡图示/谱例渲染** + **P2-H1 阶段 2 节奏训练补齐**
> + **P2-H2 剩余练习补齐（G/F、华尔兹、反向/平行、连奏/踏板/录音/弱起反复）**
> + **H7a-P2 长谱分页** + **H9b-P2 性能后续**
> + **H9c 英文界面第一切片 + P2-H8 四首入门曲**；
> 指导书 **57/57 全就绪**；学习路径 **74/74**，测试 **684 项通过**；
> 曲库 **32 个可跟随文件（21 曲 + 11 训练）+ 2 首制作中**；公开包 **146 个内容文件**。
>
> **2026-11-13 新阶段（A1–A3 已完成）：** 用户已确认仓库
> `git@github.com:qihangyang08-glitch/DIY-Music-KeyBoard.git`；A1 仓库/CI、
> A2 逐键校准（纯逻辑/固件/页面/多指验证/自动下发）与 A3 首启向导/帮助
> 已全部完成。随后做 GM 音色扩展与 20 首新曲。校准设计见
> [CALIBRATION_DESIGN.md](CALIBRATION_DESIGN.md)，批次与仓库见
> [ROADMAP_NEXT.md](ROADMAP_NEXT.md)。
>
> 本文只回答「还剩什么、按什么顺序、大概几次、怎么验收」，不重复设计细节。
> 设计细节以配套文档为准：
> [DESIGN_INDEX.md](DESIGN_INDEX.md)（总览与待做事项）、
> [TEACHING_CURRICULUM.md](TEACHING_CURRICULUM.md)（9 阶段内容）、
> [UI_DESIGN_V3.md](UI_DESIGN_V3.md)（§12 创作页、§19 P5/P6）、
> [CONTENT_PIPELINE.md](CONTENT_PIPELINE.md)（生产/校验）、
> [RELEASE_POLICY.md](RELEASE_POLICY.md)（私有/公开版）、
> [CALIBRATION_DESIGN.md](CALIBRATION_DESIGN.md)（逐键校准）。
> 下一阶段的优化/功能候选与分批建议见 [ROADMAP_NEXT.md](ROADMAP_NEXT.md)。

---

## 0. 快速接手（5 分钟）

1. 读 §1 基线 → **§1.1 新阶段任务** → §2.1 优先级 → §3.2 H7f 残留 / §3.4 H9。
2. 跑测试：`cd pc && python -m unittest discover -s tests -v`，应为 **684 通过**。
3. 启动真实应用：双击 `pc\run.cmd`（先关闭 PlatformIO 串口监视器；
   本机真机 COM5 + 0x5A/0x5C/0x5D）。
4. **A1 仓库/CI、A2 校准与 A3 首启向导/帮助已完成**；下一步从
   **B9 GM 音色扩展**开始，先读 [ROADMAP_NEXT.md](ROADMAP_NEXT.md) §6。
5. 选一个纵向切片或一批内容，先写测试；完成后同步 `DESIGN_INDEX`、
   `app/README`、测试计数，并跑全套回归。

---

## 1. 当前基线（新会话先确认这些）

| 项 | 状态 |
|---|---|
| 可运行代码 | `pc/app/`，Python 3.11 + PySide6；**公开仓库已初始化并推送** `main` + `v0.1.0`（`git@github.com:qihangyang08-glitch/DIY-Music-KeyBoard.git`）；私有曲/用户数据/日志/截图未进入历史 |
| 学习页路径 | **74/74 就绪**；阶段 0–8 全部就绪（0=8/8、1=5/5、2=7/7、3=10/10、4=6/6、5=10/10、6=8/8、7=11/11、8=9/9） |
| 创作页 | **H4 功能齐**：录音/叠录/循环/8 轨/音色/音量/声像/静音独奏/叠加/分区/混响/保存载入/钢琴卷帘/模板/导出 MIDI/回放/节拍器/预备拍 |
| 指导书 | **P2-G 已完成**：阶段 0–8 共 **57/57 节**正文可读（Lesson JSON、五段式课程页、每课练习绑定、课次引用显示标题）；练习步骤可勾选并持久化；知识卡的 `image`/`staff`/`roll` 内嵌渲染（4 小节谱例、图示、缺素材明确提示）；未对应训练的课次明确提示 |
| 谱面 | **H7a/H7b**：自绘高/低音谱表、调号、拍号、小节线、音符/符干/加线/临时记号、播放头与下一音高亮；多 part、精确拼写、连音线合并、反复/结尾展开 |
| 曲库 | **32 个可跟随文件（21 曲 + 11 训练）+ 2 首制作中**；磁盘派生；收藏/标签/最近/递归扫描/目录监视/图片与 PDF 仅显示 |
| 考核 | **H7d**：阶段 1（20 音首答 ≥80%）、阶段 2（60 BPM/16 拍全中/平均偏差 <60 ms）；可选，不影响阶段通关 |
| 启动 | 双击 `pc\run.cmd` 或 `python pc/app/main.py`；先关闭 PlatformIO 串口监视器；本机真机为 **COM5**（3 个 MPR121：0x5A/0x5C/0x5D） |
| 测试 | **684 项通过**：`cd pc && python -m unittest discover -s tests -v` |
| 公开版 | **H9a 已完成**：`python tools/build_public.py` 生成白名单压缩包；私有/用户数据/截图/日志被自动剔除 |
| 无障碍 | **H9b 前五批已完成**：×/✓ + 文字对错反馈、`减少动效`、字号 小/标准/大（`accessibility.json`）、导航/设置/走带/音轨/键位页/学习卡键盘可达 |
| 性能 | **H9b-P1/P2 已完成**：曲库解析缓存；硬件帧去抖、onset 扫描提前停止、字体 LRU、搜索 150 ms 防抖 |
| 下一步 | **A1、A2、A3 已完成**；接下来 **B9 GM 音色扩展 → B3 20 首新曲 → A4/A5/A7**。见 §1.1 与 [ROADMAP_NEXT.md](ROADMAP_NEXT.md) |
| 私有内容 | `mariage_fragment`（梦中的婚礼 · 片段）标 `visibility="private"`；本机可用，已在 `.gitignore` 与公开构建中剔除 |
| 工作树 | 已初始化 git，`origin` = 上述公开仓库；`main` + `v0.1.0` 已推送。交接前先跑全套测试，不留下临时 mockup/`.tmp` |
| 关键约定 | TDD / 纵向切片；未就绪内容只显示“制作中”；每次切片同步 `DESIGN_INDEX`、`app/README`、测试计数 |

### 1.1 新阶段任务（2026-11-13，A1 + A2 + A3 已完成）

**A1 仓库安全初始化**、**A2 切片 1–4**（纯逻辑/协议、固件 `CAL`/`T`/`Q`、
校准页面 + 多指验证、`calibration.json` 启动/连接自动下发）与 **A3
首启向导 + 第 7 个“帮助”入口**（四步向导、`onboarding.json`、帮助页、
F1/顶栏/设置入口）已完成，基线 **684 项测试**（+78）；ESP32-S3 编译通过，
COM5 真机冒烟通过，CI 全绿。公开仓库首提交 347 个文件、约 16 MB（含
vendor），`main` + `v0.1.0` 已推送。本轮实现 A1/A2/A3 并同步以下文档：

- 新增 [CALIBRATION_DESIGN.md](CALIBRATION_DESIGN.md)：逐键校准页的完整
  交互、固件协议、数据格式与验收。
- 更新 [ROADMAP_NEXT.md](ROADMAP_NEXT.md)：新优先级、批次、仓库安全
  初始化、音色/曲目扩展。
- 更新 [UI_DESIGN_V3.md](UI_DESIGN_V3.md)：§3.1 七个入口、§12.3 音色、
  §13.1 校准、§14 向导/帮助、§23 新阶段汇总。
- 更新 [DESIGN_INDEX.md](DESIGN_INDEX.md)：入口、计数、新阶段表。

**执行顺序（用户指定优先级）**：

1. **A1 仓库安全初始化（0.5–1 天）**：**已完成（2026-11-13）**。
   `.gitignore` 覆盖用户数据/日志/截图/构建产物/私有曲/第三方引脚图；
   公开包审计 146 个内容文件、无私有/用户数据；白名单提交 347 个文件
   （含 vendor），`main` + `v0.1.0` 已推送；CI 在 `windows-latest` 跑
   661 项 unittest 与 `pio run -e esp32-s3-devkitc-1`（只编译），
   `pc-tests` 与 `firmware-build` 均已通过。
   详见 [ROADMAP_NEXT.md](ROADMAP_NEXT.md) §4。
2. **A2 逐键校准页（4–6 天）**：**已完成（切片 1–4）**——纯逻辑 +
   `CAL`/`T` 协议 + 串口收发 + 固件 `c`/`T`/`Q` + 校准页面/多指验证 +
   `calibration.json` 启动/连接自动下发，54 项测试 + 真机冒烟。见下。
3. **A3 首启向导 + 侧边栏“帮助”（2–3 天）**：**已完成**——导航第 7 项、
   四步向导、`onboarding.json`、帮助页/键位图/故障排查，F1 与顶栏/设置
   入口；23 项新测试。见下。
4. **B9 GM 音色扩展（3–5 天）**：现有 7 个扩到 30+。
5. **B3 新增 20 首曲目（批次 4）**：公有领域优先，XML+MIDI 同源。

#### A2：逐键校准页（必须先做）

**切片 1–4 已完成（2026-11-13）**：新增 `app/core/calibration.py`
（`CalibrationSession` 状态机、曲线、建议/校验、`CalibrationProfile`
容错载入与原子写）、`app/ui/calibration_page.py`（自绘曲线、阈值点选、
应用/保存、32 格多指验证）；`SerialService` 新增 `calibrationFrame`
信号、`dispatch_line` 与 `send_line`；`Instrument` 新增
`begin_calibration()` / `end_calibration()`（校准期间吞掉音符事件、
锁定映射/音色/八度）。主窗口在启动/重连时读取 `calibration.json`
并自动下发 32 组阈值，收到 `OK T` 后显示已应用。固件 `src/main.cpp`
新增 `c`/`T`/`Q`、25 Hz `CAL` 流、36 通道阈值镜像；
`src/mpr121.*` 新增逐电极写入与 12 电极突发读取。两处口径已按实测修正：

- 校准流发送 `clamp(baseline - filtered, 0, 255)`（触摸为正值；
  `filtered - baseline` 实测约 -55，旧写法恒为 0）。
- `T` 线上按 **channel** 寻址，PC 用 `mapping/keymap.json` 把 key
  换算成 channel；固件没有 key 表，不能按 key 写。

用户的问题：小拇指按同一块铜箔时峰值低，统一阈值识别不到；多指齐按
时相邻电极耦合导致部分键“按了没识别”。MPR121 支持每电极独立阈值，
所以做成逐键校准。

流程（详见 [CALIBRATION_DESIGN.md](CALIBRATION_DESIGN.md)）：

1. 设备 → 校准 → 点「开始检测」；先松手采集 1.5 s 噪声底。
2. 实时监控全部 32 键；用户按下哪些键，就为哪些键各建一张
   `信号值-时间` 曲线；可一次按多个键，每键独立图。
3. 按下再松开，信号回落到释放线以下并保持 500 ms，自动停止检测，
   曲线冻结。
4. 用户在曲线上点选任意位置，取该点纵坐标作为该键阈值；也可拖动
   水平阈值线、用峰值 60% 建议值、±1/±5 微调。
5. 应用：把 32 组 touch/release 通过串口 `T` 命令写入三个 MPR121；
   保存到 `calibration.json`，下次连接自动重发。
6. 多指验证：按和弦，显示每键通过/未通过与余量；余量不足标黄。

固件（**切片 2 已完成**；原固件没有原始信号流）：

- `c` 切换 `CAL` 流，25 Hz，一行 32 个
  `clamp(baseline-filtered,0,255)`；离线模块写 `-1`；
- `T <channel> <touch> <release> ...` 写每通道阈值，`Q` 查询 32 组；
- MPR121 逐电极写 0x41/0x42；每模块两次突发读取（24 B + 12 B）；
- 阈值镜像：`m`/健康检查重初始化后自动重放，不丢本次会话校准；
- PC 端启动/连接自动重发 `calibration.json`
  （`MainWindow._apply_saved_calibration`）已完成。

校准期间不发声、不判定、不写学习记录；离开页面关闭 `CAL` 流并恢复
普通演奏。四个切片（纯逻辑 → 固件 → 页面 → 持久化/重连）已全部完成。

#### A3：首启向导 + 侧边栏“帮助”

**已完成（2026-11-13）**：`app/core/onboarding.py`（`onboarding.json`
容错载入/原子写）、`app/ui/onboarding.py`（四步向导）、
`app/ui/help_page.py`（7 页索引/键位图/故障排查/底部动作）；
导航 7 项、F1、`Ctrl+7`、顶栏 `?`、设置“怎么用”均进入帮助页；
`onboarding.json` 已加入 `.gitignore` 与公开包禁止名单。截图：
`pc/mockups/p11_help_page.png`、`p11_onboarding.png`。

- 导航从 6 项变 7 项：演奏 / 学习 / 曲谱 / 创作 / 设备 / 设置 / **帮助**
  （`?`，`Ctrl+7`）。
- 首启向导首次自动出现一次，可跳过；步骤：连接/试弹（无设备说明可用
  电脑键盘）→ 可选校准 → 页面地图（7 页各一句 + 关键按钮）→ 第一课
  （阶段 0 找到中央 C）。完成/跳过写 `onboarding.json`。
- 帮助页是功能索引：快速开始、7 个页面/主要按钮、键位图、故障排查；
  F1 / 顶栏“怎么用”/设置入口都进入该页，不再弹临时 `QMessageBox`。
- 底部「重新打开首启向导」「去校准」；不写产品宣传长文，每条 1–2 行。

#### B9：GM 音色扩展

- TimGM6mb 已含 137 个预设与 bank 128 的 8 个鼓组，不新增 SoundFont。
- 目标 30+：Alto/Tenor/Soprano/Baritone Sax、Clean/Overdrive/Distortion
  Electric Guitar、Flute/Recorder/Pan Flute、Violin/Cello/Contrabass、
  Trumpet/Trombone/French Horn、Vibraphone/Marimba/Taiko/Woodblock/
  Synth Drum 等；钢琴/键盘、吉他/贝斯、弦乐、管乐、合成/打击分类。
- 保留现有前 7 项顺序与索引；项目文件存 GM 编号，不存列表索引。
- 节拍器固定木鱼/打击类音色，切换主音色不得改掉节拍器。
- B9b 鼓组用 bank 128、专用通道 9；32 键映射为鼓垫并显示鼓件名。
- 音色缺失回退钢琴并提示，不崩溃。

#### B3：20 首新曲（批次 4）

- 优先公有领域/传统曲；每首 MusicXML + MIDI 同源、解析一致、
  默认 32 键可弹；超窗给移调/分区方案。
- 候选池和阶段分配见 [ROADMAP_NEXT.md](ROADMAP_NEXT.md) §7、
  [UI_DESIGN_V3.md](UI_DESIGN_V3.md) §23.5。
- 验收：逐首人工试弹、公开包只含可公开曲目、曲库可按阶段筛选。

**新阶段完成定义**：A1 有可回退仓库与 CI；A2 校准页真机可用、
重启仍生效；A3 首启/帮助可跳过可重开；B9 音色切换/节拍器/回退
测试通过；B3 每首同源可弹。每批跑全套测试并更新计数。

**已完成的功能边界**：

- **演奏/跟弹**：32 键演奏、光条、电脑键位、MusicXML/MIDI 解析、
  落键/播放头/下一键/自动跟随、跟弹与和弦判定。
- **映射（H7f）**：内置预设（含左右分区、白键 19 键）、内容/曲库自动套用
  与退出恢复、结构化 `MappingSpec`、可拖拽分区点（按曲目保存 + 重置）、
  黑键方位提示；曲库卡片显示「自动分区」。
- **学习**：9 阶段 **74/74**；阶段 1–2 可选考核；阶段 5 三首右手跟弹 +
  左手自动伴奏（小星星/欢乐颂/两只老虎）。
- **曲库**：**32 个可跟随文件（21 曲 + 11 训练）+ 2 首制作中**；收藏/标签/
  最近/递归扫描/目录监视/图片与 PDF 仅显示。
- **创作**：录音/叠录/循环/8 轨/混音/叠加/分区/混响/卷帘/模板/回放/
  节拍器/预备拍/MIDI 导出；阶段 7–8 共 20 个可练项目。
- **启动**：`pc/run.cmd`、`pc/requirements.txt`、`.vscode/tasks.json`、
  README “运行”一节、`main.py` 帮助文本。

**明确未做 / 下一轮候选**（详见 §2.1、§3.2、§3.4）：

- **H7 残留**：白键预设的“方向键零鼠标编辑”；结构化 `mapping` 目前只有
  「左右分区 · 8 小节」一处内容使用；项目级分区偏好仍用项目自己的
  `Track.split`，不写入 `score_prefs.json`。
- **H7e 残留**：不等待的独立伴奏模式、左右手互换、伴奏音量/音色、
  曲库打开时的伴奏声明、宽音域双人编配（用户真正弹两只手）。
- **H9**：无障碍/性能/打包/英文/公开版过滤/首次向导/真实校准。
- **2026-11-12 新阶段**：A1 仓库/CI 与 A2 逐键校准 **已完成**；
  待做 A3 首启向导+帮助、B9 GM 音色扩展、B3 20 首新曲；详见 §1.1。
- **其他**：五线谱高级排版（圆滑线/多声部/分页）、MusicXML 装饰音与极端
  volta、项目浏览器/重命名、按考核结果硬性解锁（产品上刻意不做）。
- **体验待确认**：黑键暗色强度、分区持久化 +「重置」的文案是否清楚。

**最近交接点（A3：首启向导 + 帮助页）文件**：

- 新增：`app/core/onboarding.py`（`OnboardingState` 容错载入/原子写）、
  `app/ui/onboarding.py`（四步向导）、`app/ui/help_page.py`（页面索引、
  键位图、功能键、故障排查、底部动作）、`tests/test_onboarding.py`（5 项）、
  `tests/test_help_page.py`（5 项）、`tests/test_onboarding_ui.py`（13 项）。
- 修改：`app/ui/main_window.py`（7 项导航、`Ctrl+7`、F1/顶栏 `?`/设置
  入口、首启/重开/跳转、`auto_onboarding`/`onboarding_path`）、
  `app/ui/keybindings.py`（`page_7`）、`app/ui/i18n_ui.py`（帮助/怎么用）、
  `app/main.py`（`--no-onboarding`、首启自动）、`app/core/release.py`
  （`calibration.json`/`onboarding.json` 禁止进入公开包）、`.gitignore`。
- 契约：首次启动自动出现一次；跳过/完成/去校准/打开阶段 0 都写
  `onboarding.json`，之后不再自动弹；帮助页底部可强制重开；帮助页是
  7 页索引 + 键位图 + 故障排查，每条 1–2 行；F1、顶栏 `?`、设置
  “怎么用”、`Ctrl+7` 都进入帮助页。
- 验收：**684 项测试通过**（Windows 与 offscreen）；截图
  `pc/mockups/p11_help_page.png`、`p11_onboarding.png`。
- 未做：英文帮助正文（界面 chrome 已部分英文化）；公开 README/许可属 H10。

**上一交接点（A1：公开仓库 + CI）文件**：

- 新增：`.gitignore`（用户数据/日志/截图/`dist`/`.pio`/`backup`/私有曲/
  第三方引脚图）、`.github/workflows/ci.yml`（`windows-latest`：661 项
  unittest + `pio run -e esp32-s3-devkitc-1`，不 upload）。
- 提交：`471a058`（347 个文件、64,082 行、约 16 MB，含 vendor）；
  tag `v0.1.0`；remote `origin`；`main` 与 tag 已推送。
- 排除：`mariage_fragment.*`、用户数据、`pc/mockups`、`pc/dist`、`.pio`、
  `backup`、`tools/*.txt`、`pc/prototype/logs`、
  `ESP32-S3_DevKitC-1_pinlayout_v1.1.jpg`。
- 验收：`git ls-files` 无私有/用户数据；公开包 **146 个内容文件**；
  CI 配置已进入首提交；最终 `pc-tests` / `firmware-build` **success**。
- **CI 首跑失败修复（最终全绿）**：
  1. 公开 checkout 没有 `mariage_fragment`，书库/测试不再假定其存在；
     缺失私有曲不生成 planned 卡/缺失警告，公开包审计仍拒绝该路径；
     新增 1 项库测试，全套 **661 项**。
  2. Windows Runner 临时目录可能返回 8.3 短路径（`RUNNER~1` vs
     `runneradmin`）；库测试改为比较 `resolve()` 后的路径。
  3. 合成页在不同字体/DPI 下出现 1 px 横向舍入溢出：禁用横向滚动条，
     测试允许 1 px 容差（更大仍视为真实溢出）。
  - 最终 `pc-tests` **success**、`firmware-build` **success**
    （commit `1ccc220`，661 项）。
- **未做**：公开 README/许可展示属 H10。

**上一交接点（A2 切片 4：自动下发/重连，A2 完成）文件**：

- 修改：`app/ui/main_window.py`（启动/每次连接读取同一个
  `calibration_path`，完整方案才发 `T ...`；`OK T`/`ERR T` 跟踪已应用；
  断开清 pending；坏文件只提示一次且不覆盖）、`app/ui/calibration_page.py`
  （保留已应用状态、自动下发后刷新、方案状态文案）、
  `tests/test_calibration_page.py`（+4：自动下发/坏文件/无方案/超时）。
- 契约：启动或重连自动下发；完整方案才发送；坏文件不发送、不覆盖、
  只提示一次；无方案不发送；收到 `OK T` 才标记已应用，断开后显示未应用。
- 验收：**660 项测试通过**；真机端到端 **PASS**：MainWindow 连接 COM5 后
  自动发 `T ...`（32 组 15/8，248 字符），收到 `OK T`，内部 `Q` 回读
  15/8；随后恢复默认 12/6。
- 未做：增益一致性比较（固件没有“查询当前增益”命令）、真机人工手感
  验收（小拇指/五键和弦）、A2 完成后的 A1/A3 批次。

**上一交接点（A2 切片 3：校准页面 + 多指验证）文件**：

- 新增：`app/ui/calibration_page.py`（自绘 `CurveWidget`、逐键 `CurveCard`、
  `VerifyStrip` 32 格）、`tests/test_calibration_page.py`（15 项）、
  `tests/test_instrument_calibration.py`（5 项）。
- 修改：`app/core/serial_service.py`（`send_line` 直写 + 连接态检查）、
  `app/core/instrument.py`（`begin_calibration`/`end_calibration`：吞掉
  note 事件、锁定映射/音色/八度、离开恢复）、`app/ui/main_window.py`
  （设备→校准子页、`calibrationFrame`/notice 接线、离开/关闭 `leave()`、
  断开冻结）、`app/core/calibration.py`（`default_path`）。
- 契约：无设备/不足 3 模块时开始禁用；开始发 `c`，自动停止/手动停止/
  离开发 `c` 关闭；校准期间无 note 事件、无判定、无学习记录、无鼠标弹琴；
  曲线点选/拖动/`←/→` 微调阈值；应用前逐键 `validate`；应用后 32 格
  多指验证（✓ / ! / ×）；坏 `calibration.json` 不应用，保存要求 32 键。
- 验收：**656 项测试通过**；字体缩放与既有 UI 回归通过；PC 端
  `SerialService` 真机 `c` 写入 + CAL 读取 **PASS**；截图
  `pc/mockups/p10_calibration_page.png`、`p10_calibration_verify.png`。
- 未做（自动下发/重连已由上一交接点补齐）：真机人工手感验收
  （小拇指 / 五键和弦）。

**上一交接点（A2 切片 2：固件 CAL/T/Q）文件**：

- 修改：`src/main.cpp`（`c` 切换 25 Hz `CAL` 流、`T` 行命令解析、`Q` 回读、
  36 通道阈值镜像、`initModule` 重放镜像、行/单字符命令分发）、
  `src/mpr121.h` / `src/mpr121.cpp`（`setElectrodeThreshold`、
  `readDeltas` 两次突发读取；`delta()` 修正为 `baseline - filtered`）。
- 契约：`CAL <millis> <32 values>`，模块 1/2 各 12 个、模块 3 前 8 个；
  离线模块 `-1`；`T` 按 channel 1..36 写入，`OK T` / `ERR T <ch>` /
  `ERR T 0`；`Q` 回 32 组 `T ...`；`release >= touch`、越界、重复通道、
  残缺三元组均拒绝；`m`/健康检查重初始化后自动重放镜像。
- 验收：ESP32-S3 编译 **SUCCESS**；COM5 真机冒烟 **PASS**：
  `CAL ON` + 5 帧 × 32 值、`Q` 初始全 12/6、`T 1 48 29` 后 `Q` 回读
  48/29、`ERR T 1`（release≥touch）、`ERR T 999`、`ERR T 0`、
  `CAL OFF`、恢复 `T 1 12 6`；PC 全套当时 **633 项通过**。
- 未做（切片 4）：`calibration.json` 启动/连接自动重发、重连恢复。

**上一交接点（A2 切片 1：校准纯逻辑与协议）文件**：

- 新增：`app/core/calibration.py`（`CalibrationFrame`、`CalibrationSession`、
  `KeyCurve`/`KeyThreshold`/`CalibrationProfile`、`parse_calibration_line`、
  `format_thresholds`、`parse_thresholds_line`、`parse_threshold_reply`、
  `load_keymap`）、`tests/test_calibration.py`（24 项）、
  `tests/test_serial_calibration.py`（3 项）。
- 修改：`app/core/serial_service.py`（`calibrationFrame` 信号、
  `dispatch_line` 统一分发 `CAL`/状态行/notice）。
- 契约：`CAL` 32 值、`-1` 离线、坏行进 notice；噪声底 1.5 s、按下重来；
  连续 2 帧越线建图、200 ms 预录；多键独立曲线；全部回落 500 ms 自动停止；
  首次触发后 30 s 硬上限；卡键 5 s 标记并阻止释放自动停止；
  建议阈值 `max(noise+8, hold*55%, 8)`、峰值 15% 余量；校验拒绝
  噪声+5 以下/峰值 90% 以上；`calibration.json` 缺键/坏文件不应用；
  `T` 按 channel 寻址（键 1 = 通道 12 由 keymap 换算）。
- 验收：当时 **633 项测试通过**；本次未上真机（固件 `CAL` 流尚未实现）。
- 未做（切片 4，切片 2–3 已由后续交接点补齐）：`calibration.json`
  启动/连接自动重发、重连恢复。

**上一交接点（H9c-i18n + P2-H8：英文界面与四首入门曲）文件**：

- 新增：`app/ui/i18n_ui.py`（中文源串 → 英文目录、`tr()`、整棵控件树翻译、
  未知串回退中文）；`tests/test_i18n.py`（7 项）。
- 修改：`app/core/accessibility.py`（`language` 字段，容错/原子写）、
  `app/ui/pages.py`（English chip 启用，语言信号与选中态）、
  `app/ui/main_window.py`（启动/换页应用语言；状态栏、映射、下一键走
  `tr()`）、`app/ui/perform_view.py`、`app/ui/light_bar.py`、
  `app/ui/score_view.py`（控件与自绘文字翻译）。
- 范围：**界面 chrome**（导航、页头/状态栏、设置、演奏控件、曲库与学习
  标题）可切英文；**57 节课程正文与曲名保持中文**（内容资产按设计不翻译）。
  设置里切换语言写 `accessibility.json`，**下次启动生效**（界面有提示）。
- 内容：新增《玛丽有只小羊羔》《老麦克唐纳》（阶段 0）与
  《友谊地久天长》《勃拉姆斯摇篮曲》（阶段 3），MusicXML + MIDI 同源。
- 验收：**606 项测试通过**；学习路径 **74/74**；公开包 **146 个内容文件**；
  截图 `pc/mockups/p9_english_perform.png`、`p9_english_settings.png`。
- 未做：完整英文目录（toast/长句/课程正文）；H9c 安装包。
- 已完成：真实校准（A2）、首启向导/帮助（A3）。

**上一交接点（H7a-P2：长谱分页）文件**：

- 修改：`app/ui/score_view.py`（`ScoreCanvas.page` / `page_count` /
  `set_page` / `pageChanged`；每页 2 个系统；跟弹播放头自动翻页；
  `ScoreView` 的 `‹ 2/3 ›` 控件，短谱自动隐藏/禁用）。
- 契约：40 小节长谱 5 个系统分 3 页；只有 1 页时控件隐藏；
  `set_follow_state` 落在哪一页就翻到哪一页；换谱回到第 1 页。
- 测试：`tests/test_score_sheet_ui.py` 新增 3 项；全套 **597 项通过**。
- 截图：`pc/mockups/p9_score_pagination.png`（第 2/3 页）。
- 未做：真实硬件帧率/长曲性能的人工基线；谱面分页目前固定 2 系统/页。

**上一交接点（H9b-P2：性能后续）文件**：

- 新增：`tests/test_instrument_perf.py`（3 项硬件帧信号测试）。
- 修改：`app/core/instrument.py`（同帧去抖）、`app/core/follow.py`
  （onset 扫描提前停止）、`app/ui/theme.py`（`font()` 64 项 LRU）、
  `app/ui/library_page.py`（搜索 150 ms 防抖）。
- 契约：按住琴键的 50 Hz 重复帧不再触发全窗刷新；onset 扫描在第一个
  不同 start 处停止；相同字号/字重回同一 `QFont`；输入框停止键入
  150 ms 后才重建曲库卡片，直接 `set_query()` 仍同步。
- 验收：**594 项测试通过**（+6）；公开包仍 **138 个内容文件**。
- 未做：真实硬件帧率与长曲性能的人工基线（谱面分页已由 H7a-P2 补上）。

**上一交接点（P2-H2：剩余练习补齐）文件**：

- 新增曲目：`five_finger_gf_8bars`（G/F 五指位置，8 小节，含 B♭4）、
  `contrary_parallel_8bars`（反向/平行双手，8 小节，两个声部）、
  `pickup_repeat_8bars`（第 4 拍弱起 + 4 小节反复段落，13 个演奏小节）。
- 新增项目：`resources/projects/stage6_record_review.json`（录音自评）。
- 修改：`app/core/curriculum.py`（阶段 1 加低音谱号训练；阶段 3 加
  G/F；阶段 4 加 3/4 华尔兹左手；阶段 5 加反向/平行与困难小节循环；
  阶段 6 加连奏/断奏/重音、延音踏板、弱起与反复、录音自评）、
  `app/core/project_task.py`（`stage6_record_review`）、
  `tools/score_writer.py`（可选反复记号）、
  `tools/make_remaining_exercises.py`、十节课的 `practice` 绑定。
- 契约：9 个新练习项全部指向可解析曲谱/项目；所有曲谱在默认
  F4–C7 窗口内可弹；反复谱的 MusicXML（反复记号）与 MIDI（演奏顺序）
  解析出完全相同的音符列表；录音自评用项目任务检查「≥8 个音 +
  覆盖 2 小节」。
- 验收：**588 项测试通过**；学习路径 **70/70**；公开包 **138 个内容文件**；
  截图 `pc/mockups/p2h2_stage6_practices.png`。
- 绑定：`音域映射与移调` 复用「五指位置 · C–G」，在演奏页用八度/移调
  控件完成；57/57 节全部有练习入口，不再显示「本课暂无对应训练」。

**上一交接点（P2-H1：阶段 2 节奏训练补齐）文件**：

- 新增训练：`rhythm_six_eight`（6/8 复拍子，4 小节，120 BPM）、
  `rhythm_syncopation_4_4`（切分节奏，4 小节，80 BPM）、
  `rhythm_triplets_4_4`（三连音，2 小节，60 BPM）。
- 修改：`app/core/rhythm.py`（`accent_beats` 自定义重拍、`meter` /
  `meter_label` 显示复合拍号）、`app/core/drill.py`（三条 spec 与注册）、
  `app/core/curriculum.py`（阶段 2 新增三项训练、通关文案七条）、
  `app/ui/drill_page.py`（节拍/小结显示改用 `meter_label`）、
  `resources/lessons/stage2_04.json` / `stage2_05.json`（绑定练习）。
- 契约：6/8 每小节 6 个八分单位、重拍在第 1/4 拍；切分型含弱拍 onset；
  三连音每拍 3 个 onset；节拍器强拍按 `accent_beats` 发声；阶段 2
  训练数由 4 增至 7，全部踩准一次才视为完成。
- 验收：**580 项测试通过**；学习路径 **61/61**；截图
  `pc/mockups/p2h_stage2_six_eight.png`。
- 未做：三连音只有纯节奏型，尚无对应曲目；G/F 换位、移调、3/4 左手、
  反向/平行、录音自评仍缺。

**上一交接点（P2-G G4b：知识卡图示/谱例渲染）文件**：

- 新增：`resources/images/five_finger_c.png`（五指位置 C 图示）。
- 修改：`app/core/lesson.py`（`KnowledgeCard.kind` 保留
  `text`/`image`/`staff`/`roll`）、`app/ui/learning_page.py`
  （`resolve_score_asset` / `resolve_image_asset`、`ScoreCanvas` 内嵌谱例、
  `excerpt_score(…, 4)`、缺素材回退）、`app/core/score.py`
  （`excerpt_score`）。
- 内容：阶段 0/1/2/4/5 共 5 节加入 `staff` 谱例（小星星、小步舞曲、
  欢乐颂双手）；阶段 3 第 1 节加入五指位置图示。
- 契约：`staff`/`roll` 从打包曲库解析并只显示前 4 小节，不启动播放、
  不显示下一音高亮；`image` 从 `resources/images` 解析；图示下方保留
  alt 文字并同步无障碍名称；缺素材显示「谱例/图示未找到 · 标题」，
  绝不显示原始路径。
- 验收：**575 项测试通过**；公开包 **131 个内容文件**；截图
  `pc/mockups/p2g_stage3_visual.png`、`p2g_stage0_score.png`。
- 未做：缺失训练、英文。

**上一交接点（P2-G G4a：练习步骤勾选持久化）文件**：

- 新增：`tests/test_guide_steps.py`（7 项）。
- 修改：`app/core/progress.py`（`guide_steps`、版本 6、容错载入、
  `guide_steps_for` / `set_guide_step`）、`app/ui/learning_page.py`
  （步骤 `QCheckBox`、`✓` 文字、`已勾选 N/M`）、`app/ui/theme.py`
  （`QCheckBox` 指标样式）。
- 契约：勾选立即持久化；重开恢复；每课独立；勾选不改变阶段通关。
- 验收：568 项测试通过；截图 `pc/mockups/p2g_stage0_steps.png`。
- 决策：**取消指导书的示范播放/示范音频**，示范区只保留文字要点；
  演奏页现有的曲谱示范播放（Space）不受影响。
- 未做：知识卡图片/谱面渲染、缺失训练、英文。

**上一交接点（P2-G G3b2：阶段 7–8 十一节正文，57/57 完成）文件**：

- 新增：`resources/lessons/stage7_01.json` ~ `stage7_06.json`、
  `stage8_01.json` ~ `stage8_05.json`；测试追加 1 项（净增）。
- 修改：`app/core/curriculum.py`（阶段 7 扩为 6 节、阶段 8 扩为 5 节）。
- 内容：阶段 7 六节（录音基础、叠录、循环与量化、音色与音量、结构、
  保存/导出）；阶段 8 五节（音色叠加、键盘分区、三轨编配、混音基础、
  导出与复盘）。全部课次绑定现有项目/训练。
- 验收：**57/57 节就绪**；561 项测试通过；公开包 **130 个内容文件**；
  截图 `pc/mockups/p2g_stage8_lesson.png`。
- 后续：示范播放按钮、图片/谱面渲染、练习勾选持久化、缺失训练、英文。

**更早交接点（P2-G G3b1：阶段 5–6 十五节正文）文件**：

- 新增：`resources/lessons/stage5_01.json` ~ `stage5_08.json`、
  `stage6_01.json` ~ `stage6_07.json`；测试追加 2 项。
- 修改：`app/core/curriculum.py`（阶段 5 扩为 8 节、阶段 6 扩为 7 节）。
- 内容：阶段 5 八节（分手复习、同音/八度、左手长音、左手和弦、分区、
  反向/平行、困难小节循环、完整双手）；阶段 6 七节（速度稳定、乐句、
  连奏/断奏/重音、延音踏板、弱起收尾反复、完整曲分段、录音自评）。
- 绑定：阶段 5 的反向/平行与循环、阶段 6 的连奏/踏板/结构/录音暂无
  对应训练，明确提示；阶段 6 **不引用私有《梦中的婚礼》**，并新增测试。
- 验收：560 项测试通过；公开包 **119 个内容文件**；截图
  `pc/mockups/p2g_stage5_lesson.png`。
- 未做：阶段 7–8 共 11 节（G3b2）；6/8、切分、3/4 左手、反向平行、
  录音自评等训练；示范播放按钮、图片/谱面渲染、练习勾选持久化。

**更早交接点（P2-G G3a：阶段 3–4 十六节正文）文件**：

- 新增：`resources/lessons/stage3_01.json` ~ `stage3_08.json`、
  `stage4_01.json` ~ `stage4_08.json`；测试追加 1 项。
- 修改：`app/core/curriculum.py`（阶段 3/4 的占位课次扩为各 8 节）。
- 内容：阶段 3 八节（五指位置 C、G/F、音阶、连奏与断奏、音程与跳进、
  乐句与呼吸、音域映射与移调、视奏与完整曲）；阶段 4 八节
  （低音谱号与左手位置、大三和弦、I–IV–V、根音+五度、分解和弦、
  3/4 华尔兹、4/4 进行曲、左手与旋律的配合）。
- 绑定：阶段 3 的 G/F 换位与移调、阶段 4 的 3/4 华尔兹暂无对应训练，
  其余课次均绑定现有训练或曲目。
- 验收：558 项测试通过；公开包 **104 个内容文件**；截图
  `pc/mockups/p2g_stage3_lesson.png`。
- 未做：阶段 5–8 共 26 节（G3b）；6/8、切分、3/4 左手等训练；示范播放
  按钮、图片/谱面渲染、练习勾选持久化。

**更早交接点（P2-G G2：阶段 1–2 十二节正文）文件**：

- 新增：`resources/lessons/stage1_01.json` ~ `stage1_06.json`、
  `stage2_01.json` ~ `stage2_06.json`；`tests/test_guide_content.py`
  追加 5 项。
- 修改：`app/core/curriculum.py`（阶段 1/2 的占位课次扩为 6 节；
  `lesson_ref_label` 把 `s1-l2` 等 ID 解析成课次/阶段标题）、
  `app/ui/learning_page.py`（先修/下一步显示标题；无对应训练的已就绪
  课次显示「本课暂无对应训练」，不再借用阶段首个练习）。
- 内容：阶段 1 六节（五线谱、高音谱号、音名与八度、低音谱号、临时记号
  与调号、音程与视奏）；阶段 2 六节（拍与时值、休止与附点、2/4·3/4·4/4、
  6/8 与弱起、切分与三连音、跟节拍器弹）。
- 验收：557 项测试通过；公开包 **88 个内容文件**；截图
  `pc/mockups/p2g_stage1_lesson.png`。
- 未做：低音谱号/6/8/切分仍无对应训练；示范播放按钮、图片/谱面渲染、
  练习勾选持久化留给 G3 或能力批次。

**更早交接点（P2-G G1：指导书结构升级 + 阶段 0 三节试点）文件**：

- 新增：`app/core/lesson.py`（`Guide` / `KnowledgeCard`、Lesson JSON
  容错载入、`overlay_lessons`）、`resources/lessons/stage0_01.json`
  ~ `stage0_03.json`、`tests/test_guide_content.py`（13 项）。
- 修改：`app/core/curriculum.py`（`Guide` 移入 `lesson.py`；启动时按
  `stageN_*.json` 覆盖同名占位卡）、`app/ui/learning_page.py`
  （`CourseView` 五段式：目标/知识/示范/练习/检查；每课用
  `guide.practice` 绑定 `PracticeItem`；未就绪保留占位；课次卡显示
  「打开」/「正文制作中」）、`app/core/release.py`
  （`resources/lessons/*.json` 按 `visibility`/`public_release` 剔除，
  坏文件按不可读剔除）、`tests/test_release.py`（3 项）。
- 内容：阶段 0 三节课已可读（光条、键位与延音、第一段旋律），
  每节 3 张知识卡、示范说明、3 步练习、3 条自检、常见错误，
  并分别绑定「找到中央 C」「延音与全部静音」「跟弹《小星星》第一句」。
- 契约：`status=ready` 需有目标、至少一张有正文的知识卡、练习步骤、
  自检；JSON 损坏/缺字段/未知状态回退 `planned`，界面不伪装完成。
- 验收：552 项测试通过；公开包 **76 个内容文件**（新增 3 节），
  私有内容仍剔除；截图 `pc/mockups/p2g_stage0_lesson.png`。
- 未做（G2/G3）：其余 54 节正文、示范播放按钮、知识卡图片/谱面渲染、
  练习步骤勾选持久化、英文/翻译。

**更早交接点（H9b-K2：音轨/键位页/学习卡键盘可达）文件**：

- 新增：`tests/test_keyboard_nav.py` 追加 11 项（音轨 4、键位页 3、
  学习卡/指导书 3、卡片焦点样式 1）。
- 修改：`app/ui/creation_page.py`（`TrackRow` 9 个控件
  `StrongFocus`；显式 `_focus_controls` 顺序，`←/→` 循环焦点，声像滑杆
  保留 `←/→` 调值、`↑/↓` 离焦；`eventFilter` 不依赖 Qt 内置按钮导航的
  边界行为）、`app/ui/keybindings_page.py`（所有工具/「改」/「清除」
  按钮可聚焦；`note_edit_buttons` / `function_edit_buttons` 映射；
  两个表标签可聚焦、`←/→` 循环、Enter/Space 切换；`move_chip_focus`）、
  `app/ui/learning_page.py`（`ClickFrame` 可聚焦 + Enter/Space 触发
  `clicked`；`StageCard.stage`；继续/返回/下一步/开始/考核/指导书按钮
  全部可聚焦）、`app/ui/main_window.py`（键位页 chip 行方向键接管）、
  `app/ui/theme.py`（`QFrame[card="true"]:focus` 琥珀描边）。
- 契约：Tab 可进入音轨控件；行内 `←/→` 循环；焦点按钮 Enter/Space 激活；
  键位页「改」可用键盘启动捕获（Esc 取消）；学习阶段卡/指导书卡
  Enter/Space 打开；卡片焦点环可见。
- 验收：536 项测试通过；全套回归通过。
- 未做：性能后续（硬件帧 50 Hz 节流、光条空闲计时、长谱裁剪、谱面分页、
  字体缓存、搜索防抖）。

**更早交接点（H9b-K1：键盘可达）文件**：

- 新增：`tests/test_keyboard_nav.py`（14 项：3 键位迁移 + 11 UI）。
- 修改：`app/ui/keybindings.py`（版本 2；`labels` 默认 `Ctrl+Tab`；v1 的
  `labels = Tab` 自动迁移）、`app/ui/main_window.py`（导航按钮
  `StrongFocus`、`_move_nav_focus`、焦点控件 Enter/Space 优先级、
  设置 chip 行内方向键）、`app/ui/pages.py`（设置/音色/设备控件可聚焦，
  `move_chip_focus`）、`app/ui/widgets.py`（`ToggleSwitch` 可聚焦 + 焦点环）、
  `app/ui/creation_page.py`（走带/工具按钮可聚焦）、`app/ui/theme.py`
  （`:focus` 琥珀描边）、`tests/test_compose_ui.py`（Tab → Ctrl+Tab）。
- 契约：`Tab`/`Shift+Tab` 焦点遍历；`Ctrl+Tab` 显示键帽/音名；
  `Enter`/`Space` 激活焦点控件；焦点在按钮上时 Space 不再播放/暂停。
- 验收：525 项测试通过；方向键在导航/设置 chip 行循环；新旧键位文件
  均正确；焦点样式存在。
- 未做（已由 H9b-K2 补齐）：TrackRow 音轨控件、键位设置页捕获按钮、
  学习页阶段卡。

**上一交接点（H9b-P1：曲库扫描缓存）文件**：

- 新增：`tests/test_library_perf.py`（11 项，全部基于操作计数，不含墙钟断言）。
- 修改：`app/core/library.py`：`ScoreParseCache`（OrderedDict LRU，
  默认上限 MAX_SCAN_FILES×2 = 10000；键 = 规范化绝对路径 + `st_mtime_ns` + `st_size` + `st_ino`；
  只缓存成功解析，坏文件每次重读，修好后立即生效）、
  `_RegistryBuilder._facts` 单次 stat + 缓存查询、`build_registry(parse_cache=...)`。
  文档字符串更新为“无持久索引；仅内存缓存，重启冷启动”。
- 验收：3 个文件首次 build 解析 3 次、第二次 0 次（hits/misses = 3/3）；
  改 1 个文件只重解析 1 个；坏文件不会命中旧缓存；LRU 上限与跨目录同 stem
  均有测试；曲库页二次刷新 0 次解析；513 文件顺序重扫第二次 0 次解析；
  默认缓存生产接线与坏文件重试均有测试。
- 未做（下一批性能候选）：硬件帧 `stateChanged` 50 Hz 节流、`FollowSession`
  onset 扫描、落键视图按可见时间窗裁剪、谱面分页、字体缓存、搜索防抖。

**更早交接点（H9b 第二批：字号缩放）文件**：

- 新增：`tests/test_theme.py`（4 项）、`tests/test_font_scale_ui.py`（12 项）。
- 修改：`app/ui/theme.py`（`Theme.font_scale`/`px()`/`font()`；
  `set_scaled_font` 记录设计字号，`refresh_scaled_fonts` 在换主题/改字号时
  重刷全部标签；18 个 QSS `font-size` 走 `px()`，全局 `QWidget` 规则不再设
  字号；比例 1.0 时 QSS 与旧版一致）、
  `app/core/accessibility.py`（`font_scale`、`normalize_font_scale`，
  0.8–1.3 钳制、bool/NaN/inf/超大整数/深嵌套回退默认）、
  `app/ui/pages.py`（设置 → 辅助功能 → 字号 小/标准/大）、
  `app/ui/main_window.py`（`_build_theme` 用 `dataclasses.replace` 注入比例；
  根部件基础字号 + 运行中重刷）、`light_bar.py`、`score_view.py`、
  `piano_roll.py`、`rhythm_view.py`、`drill_page.py`
  （自绘文字改用 `Theme.font`；谱号/调号/拍号仍按谱面几何）、
  `creation_page.py` / `learning_page.py` / `library_page.py` /
  `keybindings_page.py` / `perform_view.py`（104 个标签字体走主题并登记）。
- 验收：500 项测试通过；0.9/1.0/1.2 预设；运行中切换字号立即重排文字；
  20–46 px 的标题/成绩真正显示；谱面符号明确按几何缩放，不跟随字号；
  非预设值不勾选任何 chip；0.9 下调、所有自绘画布与谱面几何不变式均有测试。
- 已知限制：设置页字号 chips 仍是鼠标操作（键盘可达留给下一批）；
  工具提示/对话框字号由系统/应用字体控制。

**上一交接点（H9b 第一批：减少动效 + 非颜色反馈）文件**：

- 新增：`app/core/accessibility.py`（`AccessibilityPrefs`，容错载入/原子写）、
  `tests/test_accessibility.py`（4 项）、`tests/test_accessibility_ui.py`（4 项）。
- 修改：`app/ui/light_bar.py`（`flash_hit`、`feedback_marker`、×/✓ 绘制、
  减少动效时的静态呼吸/无淡出）、`app/ui/perform_view.py`
  （`set_accessibility`）、`app/ui/pages.py`（设置 → 辅助功能 →「减少动效」、
  非颜色提示说明）、`app/ui/main_window.py`（`accessibility_path`、命中/未中
  光条标记、偏好保存与启动恢复）。
- 验收：478 项测试通过；`accessibility.json` 损坏/缺失回退默认。

**上一交接点（H9a 公开版过滤）文件**：

- 新增：`app/core/release.py`（禁止路径、课程清单、白名单构建计划、
  包审计、归档与清单）、`tools/build_public.py`（构建脚本）、
  `tests/test_release.py`（14 项）。
- 产出：`pc/dist/public_content.zip`（73 个内容文件 + 2 个清单，未含私有/用户
  数据；`dist/` 是可再生成的构建产物）。
- 文档：`HANDOFF.md`、`DESIGN_INDEX.md`、`app/README.md`、`RELEASE_POLICY.md`。

**上一交接点（H7f + 试弹修正）文件**：

- 新增：`app/core/score_prefs.py`（按曲目的分区点偏好，容错载入/原子写/
  清除）、`tests/test_content_mapping_ui.py`（15 项）、
  `tests/test_mapping_spec.py`（9 项）、`tests/test_score_prefs.py`（7 项）、
  `tests/test_disabled_keys.py`（6 项）、`pc/run.cmd`、
  `pc/requirements.txt`、`.vscode/tasks.json`。
- 修改：`app/core/mapping.py`（`white19`、`disabled`、`MappingSpec`、
  `split_mapping`、`with_split_bar`）、`app/core/note_engine.py`
  （跳过禁用键、`is_black_key`）、`app/core/instrument.py`（内容映射/
  结构化 spec、拖拽覆盖与缓存）、`app/core/window.py`（禁用槽不可达）、
  `app/core/curriculum.py`（结构化声明、`mapping_for_score` /
  `mapping_for_refs` / `mapping_tag_for_refs`）、`app/ui/light_bar.py`
  （禁用槽/黑键绘制、握把、拖拽信号、提示）、`app/ui/perform_view.py`
  （分区提示 + 重置、自动跟随 tooltip、按 effective key 高亮预设）、
  `app/ui/library_page.py`（「自动分区」标签）、`app/ui/main_window.py`
  （套用/恢复/拖拽持久化/重置）、`app/ui/learning_page.py`
  （`PracticeTarget.mapping`）、`tests/test_content.py`、
  `tests/test_mapping.py`、`tests/test_window.py`、`tests/test_window_ui.py`、
  各 UI 测试 fixture（注入 `prefs_path`）、`app/main.py`（帮助文本）。
- 启动/说明：`app/README.md`（运行一节、映射/黑键说明）、`DESIGN_INDEX.md`、
  `TEACHING_CURRICULUM.md`、`CONTENT_SCHEMA.md` §6.1、`UI_DESIGN_V3.md`。

---

## 2. “推进”的粒度与总估算

本文把**一次推进**定义为与已完成切片同级的工作量：

- 一个功能纵向切片（纯逻辑 + UI + 测试 + 文档），或
- 一批 **8–12 项**内容资产（同源 MusicXML/MIDI + 课程接线 + 校验 + 文档）。

按这个粒度：

| 场景 | 范围 | 状态 / 剩余估次 |
|---|---|---:|
| **A. 走通现有 9 阶段路径** | P5 创作页 + 阶段 7–8 内容/接线，做到全部就绪 | **已完成（74/74）** |
| **B. 功能完整、可公开发布（MVP / 公开测试，内容非全量）** | H9 发布打磨 + 许可/QA（H10） | **约 9–16** |
| **C. 设计文档的全部工作** | B 剩余 + 约 135–137 项内容（45 曲 + 约 49 谱面训练 + 约 41 生成训练） | **约 23–36（中位约 29）** |

> 数量按 `curriculum.STAGES` 与 `TEACHING_CURRICULUM` 的训练/曲目 ID 派生；
> 一个练习覆盖多个 ID 时会合并，实际数字会随合并上下浮动。
> 表中的 B/C 是**扣除已完成的 A 与 H7a–H7f 后的剩余量**，不是原始总量。

### 工作包汇总

| ID | 工作包 | 估次 | 依赖 |
|---|---|---:|---|
| H1 | 录音/项目内核（音符事件、循环、量化、项目/轨道 JSON） | ~~1–2~~ 已完成 | — |
| H2 | 创作页 UI（走带、录音/叠录、轨道列表、保存/载入） | ~~1–2~~ 已完成 | H1 |
| H3 | 钢琴卷帘（画/擦/移/复制/改时值、循环区、撤销） | ~~1–2~~ 已完成 | H2 |
| H4 | 多轨混音/音色/分层/分区 + MIDI 导出 + 模板 | ~~1–2~~ 已完成 | H1–H3 |
| H5 | 阶段 7 内容与接线（6 训练 + 5 项目） | ~~2~~ 已完成 | H1–H4 |
| H6 | 阶段 8 内容与接线（6 训练 + 3 项目） | ~~2~~ 已完成 | H4 |
| H7a | 五线谱渲染（自绘） | ~~3–5~~ 已完成 | — |
| H7b | MusicXML 多 part/多声部/反复/连音线 | ~~2–3~~ 已完成 | — |
| H7c | 曲库增强（收藏/标签/最近/递归/监视/图片与 PDF 仅显示） | ~~2–3~~ 已完成 | — |
| H7d | 阶段 1–2 可选考核（80% 首答、60 BPM/<60 ms） | ~~1–2~~ 已完成 | — |
| H7e | 宽音域双手编配 + 左手自动伴奏 | ~~2–4~~ 已完成（3 首示范；残留见 §3.2） | H7b 可选 |
| H7f | 按曲目 split 映射、白键键位预设、拖拽分区 | ~~1–2~~ 已完成 | — |
| H8 | 阶段 0–6 剩余内容（粗估约 135 项；逐项见 §3.3） | 14–20 | 部分依赖 H7a |
| H9 | P6 发布打磨（无障碍/性能/打包/英文/公开过滤/向导/校准） | 7–12 | — |
| H10 | 许可核对、真机试弹、回归（贯穿每批） | 2–4 | 每批 |

剩余加总（A 与 H7a–H7f 已完成）：B ≈ H9（7–12）+ H10（2–4）= **9–16**；
C ≈ B + H8（14–20）= **23–36**。

### 2.1 剩余工作总览（按优先级）

| 优先级 | 工作 | 内容 | 估次 | 依据 |
|---:|---|---|---:|---|
| **P0** | 体验确认 | 黑键暗色强度；分区持久化 +「重置」文案；自动跟随提示是否足够 | 0–0.5 | 本轮试弹反馈 |
| **P1a** | ~~H9a 公开版过滤/打包 guardrails~~ | **已完成**：白名单清单、私有/用户数据/日志/缓存/截图剔除、包审计、`tools/build_public.py` | ~~1–2~~ | RELEASE_POLICY §6–7 |
| **P1b** | H9b 无障碍/性能 | **已完成**：×/✓ + 文字对错反馈、减少动效、字号缩放、曲库解析缓存、键盘可达、硬件帧去抖、onset 扫描、字体 LRU、搜索防抖、长谱分页 | 1 | UI §19 P6 |
| **P1c** | H9c 打包/i18n/向导/校准 | ~~界面字符串抽取~~ 第一切片已完成；剩余 Windows 安装包、完整英文目录、首启 ≤5 分钟、真实阈值校准 | 3–6 | UI §19、RELEASE_POLICY |
| **P1d** | A2 逐键校准页 | **已完成（切片 1–4）**：纯逻辑/协议 + 固件 + 页面/多指验证 + 自动下发/重连 | 4–6 | [CALIBRATION_DESIGN.md](CALIBRATION_DESIGN.md) |
| **P1e** | A3 首启向导 + 帮助页 | **已完成**：导航第 7 项、四步向导、`onboarding.json`、帮助页/键位图/故障排查、F1/顶栏/设置入口 | ~~2–3~~ | UI §14、§23.2 |
| **P1f** | B9 GM 音色扩展 | 7 → 30+，分类展示；节拍器固定打击音色 | 3–5 | ROADMAP §6 |
| **P1g** | A1 仓库 + CI | **已完成**：白名单首提交 347 文件、公开包审计、CI、`main` + `v0.1.0` 已推送 | ~~0.5–1~~ | ROADMAP §4 |
| **P2** | H8 内容批次 | 约 135 项（45 曲 + ~49 谱面训练 + ~41 生成训练）；8–12 项/次 | 14–20 | §3.3 |
| **P2-G** | ~~指导书内容~~ | **已完成（2026-11-10）**：57/57 节正文、五段式课程页、每课练习绑定、课次引用标题、公开版过滤；后续能力缺口见 §3.3.1 | ~~7–10~~ | §3.3.1、TEACHING §22B、UI §9.2–9.3 |
| **P2-G2** | 指导书能力补全 | ~~练习步骤勾选/持久化~~、~~知识卡图示/谱例渲染~~ 已完成；剩余缺失训练、英文；**指导书示范播放已取消** | 2–3 | §3.3.1 |
| **P3** | H7 残留 | 白键方向键编辑；结构化 mapping 扩用；项目级分区偏好；伴奏模式/左右手互换/音量；宽音域双人编配 | 3–6 | §3.2 |
| 每批 | H10 | 许可/来源、真机试弹、全套回归、文档计数 | 2–4 | §3.5 |

**推荐顺序（2026-11-12 起）**：**P1g 仓库安全初始化 → P1d 逐键校准 →
P1e 首启向导/帮助 → P1f GM 音色 → P2 内容（20 首新曲）→ P1c 安装包/
英文/无障碍**；P3 硬件升级视需要。能力与内容批次交替，避免长期只做
一边。详细批次见 [ROADMAP_NEXT.md](ROADMAP_NEXT.md) §2。

---

## 3. 工作包明细与验收

### 3.1 P5 创作页与阶段 7–8（A 场景）

参考：[UI_DESIGN_V3.md](UI_DESIGN_V3.md) §12、§19；[TEACHING_CURRICULUM.md](TEACHING_CURRICULUM.md) §13–14。

**H1 录音/项目内核**（**已完成**：`app/core/project.py`、
`app/core/recorder.py` + 8 项测试；走带/预备拍 UI 由 H2/H4 完成）

- 新增纯逻辑模块（建议 `app/core/project.py`、`app/core/recorder.py`）：
  - `RecordedNote(t, midi, duration, track)`；录音以 20 ms 引擎批次或时间戳
    记录，不录音频。
  - 走带：开始/停止、预备拍、循环区间；叠录把新事件并入当前轨道。
  - 量化：1/4、1/8、1/16，默认关闭；量化只改时间，不改音高/时长。
  - `Project`/`Track`：最多 8 轨，每轨 `program`、`volume`、`pan`、
    `mute`、`solo`；项目 JSON 保存/载入，版本字段。
- 验收：纯逻辑测试覆盖录音/循环/叠录合并/量化/JSON 往返；无 Qt 依赖。
- 参考数据边界：不做力度、不做音频录音、不做 VST。

**H2 创作页 UI**（1–2 次，**已完成**：`app/ui/creation_page.py`，
`tests/test_compose_ui.py` 18 项）

- 已做：走带（录音/叠录/停止）、4 小节循环、轨道列表（音色/音量）、保存/载入、
  导出 MIDI 入口、顶部红点与时长、32 键光条复用、离开/关闭前收尾录音。
- 验收已覆盖：UI 测试能录一条、循环叠一条、保存后重开项目仍在；鼠标点光条
  不发声；`Esc` 仍全部静音；`Space` 不误启动曲谱示范。
- 回放/预备拍/节拍器已在 H4 补齐；项目浏览器/重命名仍未做。

**H3 钢琴卷帘**（1–2 次，**已完成**：`app/core/editor.py`、
`app/ui/piano_roll.py`，`tests/test_editor.py` 10 项 +
`tests/test_piano_roll_ui.py` 10 项）

- 已做：音符块、播放头（静态 0 拍）、循环区、缩放；画/擦/移动/复制/改时值；
  撤销（每次手势一步）；起点/MIDI/最短时值钳制；切轨刷新。
- 无力度；点击/拖动只编辑，不发声；试听仍走 32 键输入。
- 验收已覆盖：编辑后的项目与模型/JSON 一致；不误判已载入曲谱。
- 回放时播放头已随位置移动（H4）。

**H4 混音/音色/分层/分区/导出**（**已完成**，项目浏览器除外）

- 已做：每轨 GM 音色、音量、静音/独奏；MIDI 导出（格式 1、每轨一条、
  program/CC7/CC10、静音剔除、独奏过滤）；现有解析器可原样读回。
  项目回放：拍→秒、通道 1–8、每轨音色/音量/声像、静音/独奏、循环；
  `Space`/播放按钮、卷帘播放头；无音符不启动。
- 已补：每轨声像滑杆（导出/回放同步）、4 个创作模板（钢琴独奏 / 旋律+伴奏 /
  左手贝斯+右手钢琴 / 弦乐铺底）、节拍器与 1 小节预备拍、音色叠加
  （一键双音色，试听通道 13，回放/导出独立声部）、键盘分区
  （低区贝斯/高区本轨音色，试听通道 11/12，光条红色分区线，叠加与分区互斥）。
- 剩余：项目浏览器/重命名（不在 H4 验收内）。
- 验收已覆盖：导出 MIDI 能被现有解析器重新读入；静音/独奏与导出混音一致；
  回放循环/停止释放；最多 8 轨。

**H5 阶段 7 内容**（2 次，**已完成**：6 训练 + 5 项目）

- 已做：6 条训练 `录一条旋律`、`叠录低音`、`量化开/关对比`、`循环 4 小节`、
  `预备拍 + 节拍器`、`导出 MIDI`；5 个项目 `三轨小作品`、
  `8 小节旋律 + 伴奏`、`16 小节 AABA`、`循环小曲`、`完整小曲录制 + 导出`。
- 创作页新增「量化 1/8」按钮（当前轨对齐，记录 `quantize_grid`）；
  录音时开启预备拍/节拍器会写入 `count_in_used` / `metronome_used`，
  成功导出写入 `exported`，供步骤检查。
- 验收规则新增：量化、预备拍/节拍器、导出、8/16 小节跨度与四段结构检查；
  模板不能解析时仍是「制作中」。
- 阶段 7 现为 **11/11 就绪**，学习路径 **55/55**；新增 16 项测试
  （项目/会话 4、创作页 2、阶段 7 规则 7、学习页流程 3）。
- 剩余：MIDI 示范文件（可选）。
- 每个训练/项目有项目 JSON（必要时 + MIDI 示范）、步骤说明、验收规则；
  学习页接通创作页并保留返回按钮。
- 验收：从学习页打开项目 → 完成步骤 → 结果写回 `learning.json`；
  内容未就绪不显示可练。

**H6 阶段 8 内容**（2 次，**已完成**）

- 已做：6 条训练 `双层音色`、`左右分区`、`三轨编配`、`音量与声像`、
  `混响空间`、`导出项目`；3 个项目 `钢琴 + 弦乐分层`、`左手贝斯 + 右手钢琴`、
  `三轨小曲`。模板在 `resources/projects/stage8_*.json`，验收规则在
  `app/core/project_task.py`（叠加/分区/音色数/音量层次/声像跨度/混响/已导出）。
- 混响：`Project.reverb` + 创作页「混响」滑杆（试听即时生效，离开页面归零），
  MIDI 导出写 CC91；`Project.exported` 在成功导出后置位，供「导出项目」验收。
- 阶段 8 现为 **9/9 就绪**；新增 19 项测试
  （阶段 8 规则/资产 11、项目模型 2、混响/导出 UI 3、CC91 1、学习页流程 2）。
- 剩余：MIDI 示范（可选）；阶段 7 的第二批已在 H5 完成。

### 3.2 能力缺口（B 场景）

- **H7a 五线谱渲染**（**已完成**：自绘方案）。
  - 选型：Qt `QPainter` 自绘，无第三方依赖；复用识谱题已有的谱表绘制，
    避免 Verovio 的包体/许可以及打包问题。免费、稳定、可测试。
  - 已做：`app/core/staff.py` 纯布局（谱表归属、音级步进、调号内/外
    临时记号、系统/小节/播放头）；`app/core/score.py` 读 MusicXML/MIDI
    调号（`key_fifths`）；`app/ui/score_view.py` 在「谱面」页绘制
    高/低音谱表、谱号、调号、拍号、小节线、指针、加线、符干、
    下一音高亮与播放头。
  - 覆盖：单音题已有独立谱表、4 小节视奏/整曲、左右手双谱表、播放头、
    临时记号与调号。未做：圆滑线、多声部自动排版、完整符号库、分页/滚动。
  - 测试：`tests/test_staff.py` 9 项 + `tests/test_score_sheet_ui.py` 2 项；
    截图 `pc/mockups/p5_score_sheet.png`。
  - 这是 D1-11/19/20、音程/调号训练与“谱面”页的前置；H7b 继续补
    MusicXML 多 part/反复与精确拼写。
- **H7b MusicXML 多 part/反复**（**已完成**）：
  - 多 part：解析所有 `<part>`（每个 part 从 beat 0 开始，合并到同一时间线）；
    `ScoreNote` 保留 MusicXML 的 `step/alter/octave`，谱表按精确拼写绘制，
    调号内音省略临时记号、调号外自然音画 ♮；`Score.key_fifths` 读
    MusicXML/MIDI 调号。
  - 连音线：`<tie>`/`<notations><tied>` 按编号合并为一条 `ScoreNote`，
    跨小节时值相加；休止/间隙、声部/ part、重复跳跃处不合并。
  - 反复：按 `<repeat direction="forward|backward" times>` 展开，支持
    `:||:` 同一小节双向记号、无前向记号（从 part 开头反复）、`times`
    （1…32 钳制）、第一/第二结尾（含 `number="2,3"`、`discontinue`）、
    嵌套反复与嵌套结尾；反复后小节从 1 连续重新编号。
  - 测试：`tests/test_score_structure.py` 27 项（连音线 10、反复 17）+
    `tests/test_staff.py` 9 项 + 谱面 UI 2 项；全套 **390 项通过**。
  - 未做：装饰音、跨反复边界的连音线（当前按音乐惯例在跳跃处断开）、
    复杂 volta 的极端写法。
- **H7c 曲库**（**已完成**）：
  - 收藏：卡右上角 ★，收藏视图；标签：卡片「标签」编辑，逗号分隔，
    最多 8 个，搜索会匹配标签；最近：成功打开可跟谱/图片后记录，
    保留 12 条。
  - 元数据：`LibraryMeta` 持久化到 `import_dir.parent/library_meta.json`
    （生产环境为 AppConfig 下的 `library_meta.json`），容错载入、原子写入；
    元数据不决定可跟性。
  - 递归扫描：导入目录按深度 8 / 5000 文件 / 1000 目录上限递归扫描；
    跳过隐藏项与符号链接；同一 stem 在不同子目录保持两张卡，不跨目录配对。
  - 目录监视：`QFileSystemWatcher` + 300 ms 防抖，导入目录新增/删除文件后
    自动刷新；打开页面时重新挂载。
  - 仅显示：导入 `.png/.jpg/.jpeg/.bmp/.webp/.pdf` 生成“仅显示”卡；
    图片可在「谱面」页查看，PDF 只提示“仅显示”，永不进入跟弹/解析。
  - 测试：曲库纯逻辑 38 项 + 曲库 UI 31 项；全套 **390 项通过**。
  - 未做：PDF 内嵌渲染（无 QtPdf）、OCR、按内容摘要恢复改名后的收藏。
- **H7d 考核模式**（**已完成**）：
  - 阶段 1：20 音（C4–G6 自然音 + 临时记号混合池），首答 ≥16/20（80%）
    通过；答错可重试，重试不计首答。
  - 阶段 2：4/4 · 4 小节 · 60 BPM；16 拍全部踩准、无漏拍/多按、平均
    绝对偏差 <60 ms 通过。
  - 考核完全可选：只写 `learning.json` 的 `exams` 段（最佳成绩 + 次数），
    不写普通练习结果、不改变阶段通关；中途退出不计一次考核。
  - 学习页阶段 1/2 显示「考核 · 可选，不影响普通练习」入口与最佳成绩；
    通过后可「重新考核」，成绩只保留更好的一次。
  - 测试：`tests/test_exam.py` 25 项 + `tests/test_exam_ui.py` 10 项；
    全套 **390 项通过**；截图 `pc/mockups/p5_exam_stage1.png`。
  - 审查修复：E6/G6 谱面裁切（按最高音动态压缩线距，同时修正八度训练）；
    整条键位和弦不能骗过首答；最后一拍后立即停止仍记录考核；平均偏差
    改为向下取整（59.5 ms 仍算 <60）；损坏 `learning.json` 的 `1e400` 与
    字符串布尔容错；`learning.json` 改为临时文件原子替换。
  - 未做：考核成绩导出/证书、按考核结果锁定后续阶段（产品上刻意不做）。
- **H7e 宽音域编配 + 左手伴奏**：
  - **已完成（2026-11-09）**：3 首右手跟弹 + 左手自动伴奏示范：
    《小星星 · 自动左手》（12 小节，D5-11）、《欢乐颂 · 自动左手》与
    《两只老虎 · 自动左手》（各 8 小节，阶段 5 曲目）。MusicXML 两个 part：
    P1 右手在默认映射内跟弹，P2 左手低于默认音域、由 FluidSynth 通道 10
    自动演奏，不进判定/命中数/窗口。练习按键即节拍：右手指到哪一拍，
    左手补到该拍并按时松开；`Space` 示范双手一起响。
    `PracticeItem.accompaniment` 声明 part，坏声明回退整谱。
    测试 `test_accompaniment.py` 5 + `test_accompaniment_follow.py` 8 +
    `test_accompaniment_ui.py` 4 + 内容 3 项；全套 **410 项通过**。
  - **剩余**：曲库直接打开时的伴奏声明（曲库无内容元数据，当前按整谱
    练习）；“伴奏不等待、保持节奏”的独立伴奏模式；左右手互换与可调
    伴奏音量/音色；宽音域双人编配（用户真正弹两只手）。
  - 验收：右手跟弹判定不受伴奏影响；换曲/退出恢复用户映射；学习页能打开
    并完成；纯逻辑 + UI 测试已覆盖。**首次真机连接与界面试弹已完成**
    （COM5 + 3 个 MPR121）；完整曲目跟弹、伴奏音量/音色仍待人工确认。
  - 未来内容若超出 32 键，标注 `unplayable` 或简化编配，不要偷偷移调。
- **H7f split 映射接入 + 预设增强**：
  - **已完成（2026-11-09）**：
    - 内容映射：`PracticeItem.mapping` 支持预设 key 或结构化
      `MappingSpec`（CONTENT_SCHEMA §6.1：base/steps/octave/transpose/
      split）。「左右分区 · 8 小节」用 `split_mapping(16, 48, 72)` 声明。
      学习页或曲库打开时套用，退出/换谱/换卡恢复；导入文件不继承内置声明；
      未知声明静默回退。练习中允许临时改映射，退出时丢弃。
    - 白键 19 键：`PRESETS` 新增 `white19`（C4–G6 白键 → 键 1–19，
      20–32 禁用）。NoteEngine 跳过禁用键；`bar_for_midi`、窗口规划、范围
      标签与光条都排除禁用槽；禁用槽画暗并显示“—”，按键不发声。
    - 拖拽分区点：光条琥珀线可拖动（1–31），实时套用；松手把用户选择保存到
      用户级 `score_prefs.json`（内置按 stem、导入按路径），再次打开自动
      恢复，换谱清除。红色项目分区线不受影响。
    - 试弹体验修正：琥珀线加粗并带握把；右栏映射卡显示「分区 16 · 拖动
      光条琥珀线调整」和「重置」；自动跟随开关补充 tooltip；曲库卡片显示
      「自动分区」；光条静息时黑键槽位用明显暗色渐变 + 顶部小点（不改变
      等宽 C 光条）。分区点按曲目保存是有意行为，点「重置」可回到内容
      默认分区并清除本曲目的保存值。内容映射生效时不再错误高亮旧预设按钮。
  - 测试：H7f 相关新增 **46 项**（映射/禁用键/结构化/拖拽/偏好/内容契约/
    黑键提示），全套 **456 项通过**。
  - 启动整理：`pc/run.cmd`、`pc/requirements.txt`、`.vscode/tasks.json`、
    README 的“运行”一节、`main.py` 帮助文本。
  - 剩余（不阻塞发布）：
    - 白键预设的“方向键零鼠标编辑”（方向键选槽 + Enter，零鼠标）。
    - 结构化 `MappingSpec` 目前只有「左右分区 · 8 小节」一处使用；
      后续内容可逐步改用结构化声明。
    - 项目级分区偏好：项目仍使用自己的 `Track.split`，不写入
      `score_prefs.json`；若需要“项目曲目联动分区”再单独立项。
    - 曲库导入文件的自动映射声明：当前只有内置曲目按 stem 反查；
      导入文件不继承、也没有自定义声明入口。

### 3.3 内容生产（C 场景）

参考：[TEACHING_CURRICULUM.md](TEACHING_CURRICULUM.md)、
[CONTENT_PIPELINE.md](CONTENT_PIPELINE.md) §5–§7。

剩余约 **135–137 项（粗估）**：

| 类别 | 目标 | 已就绪/已覆盖 | 剩余 |
|---|---:|---:|---:|
| 曲目 | 59 | 14 | 45 |
| 谱面训练 | 62 | 13 | 49 |
| 生成训练 | 54 | 11 项（约 13 个 ID；含阶段 7–8） | ~41 |
| 创作项目 | 8 | 8（阶段 7–8；另有 12 条生成训练） | 0 |
| 课程指导书（57 节课） | 57 | **57（阶段 0–8 全部）** | 0 |

- 按 8–12 项/次推进，约 **14–20 次**；优先补阶段 0–2 的生成训练与阶段 3–6
  的曲目/训练（阶段 0–2 生成训练约 29 项，阶段 3–6 约 95–97 项）。
- 数量为设计目标粗估；交接时以 `curriculum.STAGES` 实际就绪数和
  `TEACHING_CURRICULUM` 的 ID 为准，不为凑数硬做。
- 每批必须：MusicXML + MIDI 同源、`visibility/public_release`、人工试弹、
  `planned → ready`；`CONTENT_PIPELINE` §6 的自动校验不通过只能是 `encoded`。
- 新曲目优先 PD/传统旋律 + 本项目编配；外部教材只做选题参考，不打包正文。

#### 3.3.1 指导书内容（P2-G，2026-11-10 立项）

**口径**：内容单位按 `TEACHING_CURRICULUM` 的 **57 节课**（阶段 0–8 为
3/6/6/8/8/8/7/6/5），阶段页保留 3–8 张课次导航卡。现有 27 张阶段级
指导书卡（每阶段 3 张、每张 2 条要点）只是占位入口，**不算正文完成**。

| 阶段 | 内容 | 估次 | 依赖 |
|---|---|---:|---|
| **G1 结构升级** | ~~`guide` 内容模型、Lesson JSON 载入、五段式课程页、每课练习绑定、内容状态与公开版过滤；阶段 0 三节试点~~ **已完成 2026-11-10** | ~~1–2~~ | 无 |
| **G2 阶段 1–2** | ~~12 节可读正文（阶段 1/2 各六节）~~ **已完成 2026-11-10** | ~~2–3~~ | G1 |
| **G3a 阶段 3–4** | ~~16 节可读正文~~ **已完成 2026-11-10** | ~~2~~ | G1 |
| **G3b1 阶段 5–6** | ~~15 节可读正文（阶段 5 八节、阶段 6 七节）~~ **已完成 2026-11-10** | ~~2~~ | G1、P2 |
| **G3b2 阶段 7–8** | ~~11 节可读正文（阶段 7 六节、阶段 8 五节）~~ **已完成 2026-11-10** | ~~1–2~~ | G1、P2 |
| 合计 | 57 节 | **7–10** | — |

**当前状态（2026-11-10）**：**P2-G 已完成；57/57 节可读**，无占位课次。
全部阶段已通过五段式页面、练习绑定、课次引用标题与公开版过滤验收；
**P2-H2 后 57/57 节都有练习绑定**，不再有「本课暂无对应训练」的课次。
「音域映射与移调」绑定既有「五指位置 · C–G」，在演奏页通过八度/移调
控件完成，不单独做生成式训练。低音谱号、G/F、3/4 左手、反向/平行、
弱起/反复、录音自评、6/8、切分、三连音均已有训练。

**G4a 练习步骤勾选（已完成，2026-11-10）**

- `CourseView` 把 ready 课的步骤渲染为 `QCheckBox`；勾选后立即写入
  `learning.json` 的 `guide_steps`（版本 6，键 `阶段:课次 id`），
  重新打开/切换主题后恢复；勾选文字前加 `✓`，不只靠颜色。
- 页面显示「已勾选 N/M」；步骤勾选只做学习自查，不改变阶段通关。
- 容错：坏 `guide_steps` 忽略；读取不创建文件；每课独立。
- 7 项测试（`tests/test_guide_steps.py`）；全套 **568 项通过**。

**G4b 知识卡图示/谱例渲染（已完成，2026-11-10）**

- `KnowledgeCard.kind` 区分 `text` / `image` / `staff` / `roll`，不再把
  视觉块压成普通文字卡。
- `staff` / `roll`：按裸 id、文件名或 `resources/scores/...` 解析到打包
  曲谱，解析为 `Score` 后用 `ScoreCanvas` 内嵌绘制；只取前 4 小节
  （`excerpt_score`），静态显示，不启动播放或下一音高亮。
- `image`：按绝对路径、`resources/...` 或 `resources/images/...` 解析，
  等比缩放到卡片宽度；图示下方保留 alt 文字，并写入无障碍名称。
- 缺素材或坏谱例：显示「谱例未找到 / 谱例载入失败 / 图示未找到 · 标题」，
  不暴露原始路径，不崩溃。
- 内容：阶段 0/1/2/4/5 五节加入 `staff` 谱例，阶段 3 第 1 节加入
  五指位置图示；全部指向打包曲库/图示。
- 验收：575 项测试通过；公开包 131 个内容文件。

**后续能力缺口（不阻塞内容完成）**

- **指导书的示范播放/示范音频已取消（2026-11-10 产品决策）**；示范区
  只保留文字「示范要点」，不制作音频或自动演奏按钮。演奏页现有的曲谱
  示范播放（`Space`）不受影响。
- 57 节课全部有练习绑定；原缺口（低音谱号、G/F、3/4 左手、反向/平行、
  弱起/反复、录音自评、6/8、切分、三连音）已在 P2-H1/H2 补齐。
  `音域映射与移调` 没有独立生成式训练，改用既有五指位置练习 +
  演奏页八度/移调控件；如果以后要自动判定，需要新增可交互映射训练。
- 英文/翻译（`title_en`/`body_en`）未接入。

**G1 验收（已完成，2026-11-10）**

- `app/core/lesson.py`：`Guide` / `KnowledgeCard` + Lesson JSON 载入
  （`CONTENT_SCHEMA` §4 子集）；容错：坏 JSON/缺字段/未知状态回退
  `planned`，不崩溃。
- `Guide` 字段：`objectives`、`prereq`、`cards`、`demonstration`、`steps`、
  `mistakes`、`self_check`、`next_step`、`practice`、`readiness`、
  `visibility`、`public_release`、`source`；旧的三参数构造保持兼容。
- `CourseView` 按 UI §9.3 渲染 **目标 / 知识 / 示范 / 练习 / 检查**；
  `ready` 显示真实正文，`planned` 保留「正文、图示与可试听的谱例制作中」
  占位；每课用自己的 `practice` 绑定 `PracticeItem`，不再共用
  `stage.first_practice()`。
- 阶段卡显示「可读」或「正文制作中」，不把占位课伪装成完成。
- 公开版：`resources/lessons/*.json` 按 `visibility` / `public_release`
  纳入或剔除；`public_release != yes` 的课不得进包。
- 测试：载入容错、ready 门槛、阶段 0 三节试点、五段式 UI、练习绑定、
  公开版剔除；全套回归。
- 未做（留给 G2/G3）：可试听的示范播放按钮、知识卡图片/谱面渲染、
  练习步骤勾选持久化、57 节的完整正文、英文/翻译。

**Lesson JSON 约定**

- 遵循 `CONTENT_SCHEMA` §4：`id / stage / index / title / objectives /
  prerequisites / duration_min / blocks[] / check[] / next / status`。
- 扩展字段：`mistakes[]`、`practice`（绑定阶段内 `PracticeItem.name`）、
  `visibility`、`public_release`。
- `status = ready` 的门槛：有目标、至少一张有正文的知识卡、练习步骤、
  自检；缺一项即视为 `planned`，界面显示占位。

**写作与发布**

- 每节 800–1500 字；知识卡 100–300 字；示例必须能在 32 键上弹。
- 原创文字；外部教材只做选题参考，不复制段落。
- 每节入库前核对 `visibility/public_release`，公开构建跑
  `python tools/build_public.py`，失败即停止。

### 3.4 发布打磨（B/C 场景）

参考：[UI_DESIGN_V3.md](UI_DESIGN_V3.md) §19 P6、§20；
[RELEASE_POLICY.md](RELEASE_POLICY.md) §6–§7。

建议拆成三个纵向切片（可独立交接）：

**H9a 公开版过滤 + 打包 guardrails（已完成，2026-11-09）**

- 纯逻辑 `app/core/release.py`：
  - `forbidden_package_path`：`user-data/`、`learning.json`、`score_prefs.json`、
    `keybindings.json`、`library_meta.json`、日志、缓存、`mockups/`、`dist/`、
    `.pio/`、临时文件一律禁止。
  - `content_manifest`：从 `curriculum.STAGES` 派生全部条目与文件；私有或
    非法 `visibility` 即 `remove`，不依赖手工维护的排除表。
  - `plan_public_build`：扫描整个 `resources/` 生成白名单；私有课程资产、
    `visibility` 非 public 或 `public_release != "yes"` 的项目模板被剔除；
    缺谱/禁止文件泄漏进包则报错。
  - `audit_package`：对最终压缩包成员做二次审计（私有文件、禁止路径、
    `..`/绝对路径）。
  - `build_public_archive`：失败不写包；成功后原子替换；包内写
    `PUBLIC_CONTENT.md` 与 `public_exclusions.json`。
- 构建脚本 `pc/tools/build_public.py`（默认 `pc/dist/public_content.zip`）。
- 验收：已跑一次真实构建，**73 个内容文件**、无 `mariage_fragment`、无用户
  数据/日志/截图；`mariage_fragment.musicxml` 仍留在本机并可正常解析。
- 测试：`tests/test_release.py` 14 项；全套 **470 项通过**。
- 未做（留给 H9c）：完整 Windows 安装包的代码/依赖清单审计、公开仓库历史
  清理、按 `public_alternative` 自动替换内容（当前只有 remove 语义）。

**H9b 无障碍 + 性能（前五批已完成，2026-11-09/10；剩余 1–2 次）**

- **已完成：非颜色对错反馈 + 减少动效**
  - 光条按错：红色**虚线**框 + `×`；按对：琥珀**实线**框 + `✓`；顶栏同时写
    「命中 / 未中 · 应按 X」。颜色只是次要信息，形状/文字本身可区分。
  - 设置 → 辅助功能 →「减少动效」：关闭光条呼吸、光柱与松键淡出；跟弹判定、
    播放头与节拍器不受影响。偏好存用户配置目录的 `accessibility.json`
    （容错载入、原子写、启动恢复）。
  - 纯逻辑 `app/core/accessibility.py` + UI 接线；8 项测试，全套 **478 项通过**。
- **已完成：字号缩放（H9b 第二批）**
  - `Theme.font_scale` + `px()`/`font()` 作为唯一缩放载体：18 个 QSS
    `font-size`（全局 `QWidget` 规则不再设字号，避免覆盖 `setFont`）、
    自绘文字（光条/乐谱标签/卷帘/节奏块/识谱作答条）与全部 104 个
    `setFont` 标签同步缩放；谱号/调号/拍号仍按谱面几何，不跟随字号。
  - 标题层级修复：根部件持有 `Theme.font(12)` 基础字号，
    `set_scaled_font` 记录每个标签的设计字号，`refresh_scaled_fonts`
    在换主题/改字号时重刷，所以 20–46 px 的标题/成绩真正按比例显示，
    运行中切换字号也立即生效。
  - 设置 → 辅助功能 → 字号「小 0.9 / 标准 1.0 / 大 1.2」；偏好存
    `accessibility.json`，容错载入（bool/NaN/inf/超大整数/深嵌套回退
    默认）、数值钳制 0.8–1.3，启动恢复。非预设值不勾选任何 chip，
    不谎报当前比例；切换主题保留字号。
  - 审查修复：键位编辑器的紧凑 chip 由固定 22 px 改为可增高；
    覆盖 0.9 下调、半入舍入、所有自绘画布、谱面几何不变式。
  - 22 项测试（theme 4、prefs 6、UI 12）；全套 **500 项通过**。
- **已完成：曲库扫描缓存（H9b-P1）**
  - `ScoreParseCache`：内存 LRU（默认 MAX_SCAN_FILES×2 = 10000 项），键 =
    规范化绝对路径 + `st_mtime_ns` + `st_size` + `st_ino`；只缓存成功
    解析，坏文件每次重读、修好后立即生效；无持久索引，重启冷启动。
  - `build_registry(parse_cache=...)`；曲库页每次刷新仍重新 stat，
    文件变化（新增/删除/改写）在下次构建可见。
  - 11 项操作计数测试：二次构建 0 次解析（3 hits/3 misses）、改写 1 个
    文件只解析 1 个、坏文件不命中旧缓存、LRU 上限/跨目录同 stem、
    曲库页二次刷新 0 次解析；全套 **511 项通过**。
- **已完成：键盘可达（H9b-K1）**
  - **Tab 契约**：`Tab`/`Shift+Tab` 回归焦点遍历；“显示键帽/音名”移到
    `Ctrl+Tab`；键位文件版本 2，旧版（v1）里 `labels = Tab` 自动迁移为
    `Ctrl+Tab`。
  - **导航栏**：6 个导航按钮 `StrongFocus`；`↑/↓/Home/End` 移动焦点
    （循环），`Enter` / `Space` 进入页面；琥珀焦点描边。
  - **设置页**：主题/语言/字号 chip、减少动效开关、工具按钮全部可聚焦；
    chip 行内 `←/→` 移动并循环；`ToggleSwitch` 自绘焦点环。
  - **走带与设备/音色**：创作页走带/工具按钮、音色页程序 chip 与静音、
    设备页“打开校准页”可聚焦；`Enter`/`Space` 通过同一规则激活。
  - **事件优先级**：文本输入/键位捕获/识谱总结之后，焦点控件优先——
    `Enter` 调用 `click()`，`Space` 交还原生按钮（不再触发播放/暂停）；
    其余情况 `Space` 仍是示范播放/暂停。
  - 14 项测试（3 键位迁移 + 11 UI：Tab 遍历、方向键、Space/Enter、
    chips/toggle、走带、音色/设备、焦点样式）；全套 **525 项通过**。
- **已完成：音轨/键位页/学习卡键盘可达（H9b-K2）**
  - **音轨**：`TrackRow` 9 个控件全部 `StrongFocus`；行内 `←/→` 按显式
    顺序循环焦点，声像滑杆保留 `←/→` 调值、`↑/↓` 离焦；Enter/Space
    沿用全窗激活规则。
  - **键位页**：工具按钮与每行「改」「清除」可聚焦；「改」用 Enter/Space
    启动捕获、Esc 取消；两个表标签可聚焦、`←/→` 循环、Enter/Space 切换。
  - **学习页**：阶段卡与指导书卡 `ClickFrame` 可聚焦，Enter/Space 打开；
    继续/返回/下一步/开始/考核按钮全部可聚焦；卡片有琥珀焦点描边。
  - 11 项测试；全套 **536 项通过**。
- **已完成：性能后续（H9b-P2，2026-11-11）**
  - **硬件帧去抖**：`Instrument.set_hardware_frame` 只在连接状态、映射键、
    踏板或 MPR121 模块应答变化时发 `stateChanged`；按住琴键时 50 Hz
    重复帧不再刷新整个窗口。时间戳仍每帧更新，掉线检测不变。
  - **onset 扫描**：`FollowSession._onset_indices` 在遇到第一个不同
    onset 时停止（音符按 start 排序），不再为每个状态访问扫完整谱。
  - **字体缓存**：`ui.theme.font()` 用 64 项 LRU 缓存；自绘画布每帧
    复用同一 `QFont`，不再反复探测字体族。
  - **搜索防抖**：曲库输入框 150 ms 后才调用 `set_query`；直接调用
    `set_query()` 仍是同步的，筛选/清空/测试不受影响。
  - **已确认**：光条 `_tick` 在无按键/淡出/提示时停止计时器；落键视图
    已按可见时间窗裁剪音符。谱面仍一次画出全部系统。
  - 6 项测试（字体缓存 1、onset 扫描 1、硬件帧 3、搜索防抖 1）；
    全套 **594 项通过**。
- **剩余**：真实硬件帧率与长曲性能的人工基线。谱面分页已由 H7a-P2
  补上（每页 2 系统，跟弹自动翻页）。
- 验收：手动检查 + 性能基线；自动测试覆盖偏好持久化、反馈接线、字号路径、
  曲库解析计数与键盘导航。

**H9c 打包/i18n/向导/校准（3–6 次）**

- ~~英文/i18n 第一切片~~ **已完成（2026-11-11）**：导航/页头/设置/演奏
  控件/曲库与学习标题可切英文，偏好持久化、下次启动生效；课程正文与
  曲名按设计保持中文。剩余 toast/长句与更多界面文案的目录扩充。
- Windows 安装包（含依赖/SoundFont），干净机器可启动。
- 首次向导 ≤5 分钟：连接 → 找到中央 C → 延音/静音 → 第一段旋律。
- 校准/设备页：**2026-11-12 设计定稿**为逐键阈值工作页，见
  [CALIBRATION_DESIGN.md](CALIBRATION_DESIGN.md)；首启向导与侧边栏
  “帮助”见 UI §14、§23.2；代码尚未开始。
- 验收：全新机器安装 → 5 分钟内完成向导 → 真机可弹；校准后弱键/
  多指和弦可识别，重启仍生效。

### 3.5 贯穿性工作（每批）

- 启动/自检：双击 `pc\run.cmd`（先关闭 PlatformIO 串口监视器）；本机真机
  **COM5**，3 个 MPR121 模块 0x5A/0x5C/0x5D。串口被占用时应用会一直
  “等待设备”，不是固件故障。
- 许可/来源记录；公开版字段完整。
- 真机试弹（32 键 + 电脑键盘）；录音/分区等新交互必须真机验证。
  分区拖拽、白键 19 键、自动伴奏已做首次界面试弹；完整曲目跟弹仍建议
  每批人工确认。
- 回归：`cd pc && python -m unittest discover -s tests -v`（当前 684 项）；
  每批更新 `DESIGN_INDEX` 的“待做事项”、`app/README` 的内容清单与测试计数。
- 公开构建：改动内容后跑 `python tools/build_public.py`（当前 **146 个内容
  文件**）；失败即停止，
  不要手工删私有文件来“修绿”。
- 私有内容：处理时可先不区分公私，处理后立即标 `visibility`；
  私有内容不进入公开包，不阻塞当前工作。

---

## 4. 推荐顺序与已完成记录

1. ~~**H1 录音/项目内核**（纯逻辑 + 测试）~~ —— 已完成（8 项测试）。
2. ~~**H2 创作页 UI**（能录、能叠、能循环、能保存）~~ —— 已完成（18 项 UI 测试）。
3. ~~**H5 第一批**：`录一条旋律`、`叠录低音`、`循环 4 小节` 接入学习页~~
   —— 已完成（3 条项目端到端）；剩余 `三轨小作品` 与扩展内容。
4. ~~**H3 钢琴卷帘**（项目可编辑，导出前必需）~~ —— 已完成（20 项测试）。
5. ~~**H4 多轨/混音/分层/分区/MIDI 导出**~~ —— **已完成**：导出、静音/独奏、
   回放、声像、模板、节拍器/预备拍、音色叠加、键盘分区。
6. ~~**H5 第二批**：阶段 7 扩展到 6 训练 + 5 项目~~ —— **已完成**：
   量化按钮、预备拍/节拍器记录、导出标记、8/16 小节结构检查；
   阶段 7 11/11。
7. ~~**H6 阶段 8**：叠加/分区 + 3 个项目~~ —— **已完成**：6 训练 + 3 项目，
   混响滑杆/CC91/导出标记；阶段 8 9/9，学习路径 55/55。
8. ~~**H7a 五线谱渲染**~~ —— **已完成**：自绘谱表/调号/拍号/播放头，
   `app/core/staff.py` + `score_view.py`；390 项测试。
9. ~~**H7b MusicXML 多 part/反复**~~ —— **已完成**：多 part、精确拼写、
   调号、连音线合并、反复/结尾展开（含嵌套与 `:||:`）；390 项测试。
10. ~~**H7c 曲库增强**~~ —— **已完成**：收藏/标签/最近、递归扫描、
    目录监视、图片/PDF 仅显示；390 项测试。
11. ~~**H7d 可选考核**~~ —— **已完成**：阶段 1 二十音首答 ≥80%、阶段 2
    60 BPM 平均偏差 <60 ms；考核独立于普通练习；390 项测试。
12. ~~**H7e 右手跟弹 + 左手自动伴奏**~~ —— **已完成**：3 首示范
    （《小星星》《欢乐颂》《两只老虎》·自动左手），P1/P2 双 part，
    按键即节拍，通道 10 自动伴奏；阶段 5 8/8；410 项测试。
13. ~~**H7f 映射接入 + 预设增强**~~ —— **已完成**：内容/曲库自动套用映射；
    白键 19 键预设（20–32 禁用）；光条拖拽分区点并按曲目保存/重置；结构化
    `MappingSpec` 加载器；启动方式整理（run.cmd/requirements/tasks）；
    试弹体验修正（握把/提示/自动分区标签/黑键暗色）。456 项测试。
14. ~~**H9a 公开版过滤/打包 guardrails**~~ —— **已完成**：白名单构建计划、
    私有/用户数据/日志/缓存/截图剔除、压缩包二次审计、
    `tools/build_public.py`；真实构建 73 个内容文件、0 私有文件；
    新增 14 项测试，全套 470 项。

15. ~~**H9b 第一批：非颜色对错反馈 + 减少动效**~~ —— **已完成**：
    ×/✓ + 虚线/实线区别、顶栏文字、`accessibility.json` 持久化、
    设置页开关；新增 7 项测试，全套 478 项。

16. ~~**H9b 第二批：字号缩放**~~ —— **已完成**：`Theme.font_scale` +
    `px()`/`font()` 统一缩放 QSS 与自绘文字；设置页 小/标准/大；
    `accessibility.json` 持久化；新增 22 项测试，全套 500 项。

17. ~~**H9b-P1：曲库扫描缓存**~~ —— **已完成**：`ScoreParseCache`
    （LRU 10000，stat 键，只缓存成功解析）；`build_registry(parse_cache=...)`；
    二次构建 0 次解析；新增 11 项操作计数测试，全套 511 项。

18. ~~**H9b-K1：键盘可达（导航/设置/走带）**~~ —— **已完成**：
    Tab/Shift+Tab 焦点遍历、Ctrl+Tab 键帽、v1 迁移；导航方向键、设置 chip
    行内方向键、ToggleSwitch 焦点环、Space/Enter 优先级；新增 14 项测试，
    全套 525 项。

19. ~~**H9b-K2：键盘可达（音轨/键位页/学习卡）**~~ —— **已完成**：
    TrackRow 控件可聚焦 + 行内 `←/→` 循环（滑杆保留方向键调值）；
    键位页工具/捕获/清除按钮与表标签可聚焦、可键盘切换和捕获；学习页
    阶段卡/指导书卡 Enter/Space 打开、动作按钮可聚焦、卡片焦点描边；
    新增 11 项测试，全套 **536 项**。

20. ~~**P2-G G1：指导书结构升级 + 阶段 0 三节试点**~~ —— **已完成
    （2026-11-10）**：`app/core/lesson.py`（`Guide`/`KnowledgeCard`、
    Lesson JSON 容错载入、`overlay_lessons`）；`CourseView` 五段式
    （目标/知识/示范/练习/检查），每课绑定自己的 `practice`；未就绪保留
    占位；课次卡区分「打开 / 正文制作中」；公开版按
    `visibility/public_release` 剔除 Lesson JSON。阶段 0 三节正文入库，
    新增 16 项测试，全套 **552 项**；公开包 76 个内容文件。

21. ~~**P2-G G2：阶段 1–2 十二节正文**~~ —— **已完成（2026-11-10）**：
    阶段 1 六节、阶段 2 六节 Lesson JSON 入库；阶段 1/2 占位课次扩为 6 节；
    先修/下一步显示标题；无对应训练的课次明确提示；新增 5 项测试，
    全套 **557 项**；公开包 88 个内容文件；截图
    `pc/mockups/p2g_stage1_lesson.png`。

22. ~~**P2-G G3a：阶段 3–4 十六节正文**~~ —— **已完成（2026-11-10）**：
    阶段 3 八节（五指位置 G/F、音阶、连奏断奏、音程跳进、乐句、映射移调、
    视奏）与阶段 4 八节（低音谱号、三和弦、I–IV–V、空五度、分解和弦、
    3/4 华尔兹、4/4 进行曲、合手）入库；阶段 3/4 占位课次扩为各 8 节；
    新增 1 项测试，全套 **558 项**；公开包 104 个内容文件；截图
    `pc/mockups/p2g_stage3_lesson.png`。

23. ~~**P2-G G3b1：阶段 5–6 十五节正文**~~ —— **已完成（2026-11-10）**：
    阶段 5 八节、阶段 6 七节入库；阶段 5/6 占位课次扩为 8/7 节；阶段 6
    明确不引用私有曲目；新增 2 项测试，全套 **560 项**；公开包 119 个
    内容文件；截图 `pc/mockups/p2g_stage5_lesson.png`。

24. ~~**P2-G G3b2：阶段 7–8 十一节正文**~~ —— **已完成（2026-11-10）**：
    阶段 7 六节（录音/叠录/循环量化/音色音量/结构/保存导出）与阶段 8
    五节（叠加/分区/三轨/混音/导出复盘）入库；**57/57 节全部就绪**；
    全部课次绑定现有项目/训练；新增测试后全套 **561 项**；公开包
    130 个内容文件；截图 `pc/mockups/p2g_stage8_lesson.png`。

25. ~~**P2-G G4a：练习步骤勾选持久化**~~ —— **已完成（2026-11-10）**：
    `LearningProgress.guide_steps`（版本 6，容错载入）、步骤
    `QCheckBox`、`✓` 文字与「已勾选 N/M」；勾选立即持久化、重开恢复、
    每课独立、不改变阶段通关；新增 7 项测试，全套 **568 项**；
    截图 `pc/mockups/p2g_stage0_steps.png`。
    **同批决策：取消指导书的示范播放/示范音频**，只保留文字「示范要点」；
    演奏页曲谱示范播放不受影响。

26. ~~**P2-G G4b：知识卡图示/谱例渲染**~~ —— **已完成（2026-11-10）**：
    `KnowledgeCard.kind`、曲库/图片解析、`ScoreCanvas` 内嵌 4 小节谱例、
    缺素材提示；五节课加谱例、阶段 3 第 1 节加五指图示；新增 7 项测试，
    全套 **575 项**；公开包 **131 个内容文件**；截图
    `pc/mockups/p2g_stage3_visual.png`、`p2g_stage0_score.png`。

27. ~~**P2-H1：阶段 2 节奏训练补齐**~~ —— **已完成（2026-11-10）**：
    `RhythmSpec.accent_beats` / `meter_label`、6/8 复拍子、切分节奏、
    三连音三条训练；阶段 2 现有 7 条节奏训练，学习路径 **61/61**；
    新增 5 项测试，全套 **580 项**；截图 `pc/mockups/p2h_stage2_six_eight.png`。

28. ~~**P2-H2：剩余练习补齐**~~ —— **已完成（2026-11-10）**：
    G/F 五指位置、3/4 华尔兹左手、反向/平行、困难小节循环、
    连奏/断奏/重音、延音踏板、弱起与反复、录音自评、阶段 1 低音谱号
    共 9 个练习项；`音域映射与移调` 绑定既有五指位置练习；57/57 节课
    全部有练习入口；学习路径 **70/70**；新增 8 项测试，全套 **588 项**；
    公开包 **138 个内容文件**。

29. ~~**H9b-P2：性能后续**~~ —— **已完成（2026-11-11）**：
    硬件帧同帧去抖、onset 扫描提前停止、字体 LRU、曲库搜索 150 ms
    防抖；新增 6 项测试，全套 **594 项**。剩余谱面分页与人工性能基线。

30. ~~**H7a-P2：长谱分页**~~ —— **已完成（2026-11-11）**：
    `ScoreCanvas` 每页 2 个系统，`‹ 2/3 ›` 控件，跟弹播放头自动翻页；
    新增 3 项测试，全套 **597 项**；截图 `pc/mockups/p9_score_pagination.png`。

31. ~~**H9c-i18n 第一切片 + P2-H8 四首入门曲**~~ —— **已完成（2026-11-11）**：
    界面 chrome 英文化（导航/页头/设置/演奏/曲库/学习标题）、语言偏好
    持久化、下次启动生效；新增《玛丽有只小羊羔》《老麦克唐纳》
    《友谊地久天长》《勃拉姆斯摇篮曲》；学习路径 **74/74**；
    新增 9 项测试，全套 **606 项**；公开包 **146 个内容文件**；
    截图 `p9_english_perform.png`、`p9_english_settings.png`。

32. **2026-11-12 新阶段设计定稿（只改文档）** —— **A1 仓库安全初始化、
    A2 逐键校准页、A3 首启向导/帮助、B9 GM 音色扩展、B3 20 首新曲**。
    新增 [CALIBRATION_DESIGN.md](CALIBRATION_DESIGN.md)；更新
    [ROADMAP_NEXT.md](ROADMAP_NEXT.md)、[UI_DESIGN_V3.md](UI_DESIGN_V3.md)、
    [DESIGN_INDEX.md](DESIGN_INDEX.md)、本文。

33. **A2 切片 1：校准纯逻辑与协议** —— **已完成（2026-11-12）**：
    `app/core/calibration.py`（`CalibrationSession`/曲线/建议/校验/方案
    JSON）、`SerialService.calibrationFrame` 与 `dispatch_line`；
    新增 27 项测试，当时全套 **633 项**。信号方向改为 `baseline - filtered`，
    `T` 按 channel 寻址。

34. **A2 切片 2：固件 `CAL`/`T`/`Q`** —— **已完成（2026-11-12）**：
    `src/main.cpp` 新增 25 Hz CAL 流、T 行命令、Q 回读、36 通道镜像与
    重初始化重放；`src/mpr121.*` 新增逐电极写入与突发读取；
    ESP32-S3 编译 **SUCCESS**，COM5 真机冒烟 **PASS**。

35. **A2 切片 3：校准页面 + 多指验证** —— **已完成（2026-11-13）**：
    `app/ui/calibration_page.py`（曲线/阈值/应用/保存/32 格验证）、
    `SerialService.send_line`、`Instrument.begin/end_calibration`、
    主窗口导航/离开/关闭/断开接线；新增 23 项测试，当时全套 **656 项**；
    `SerialService` 真机写 `c` + 读 CAL **PASS**；截图
    `p10_calibration_page.png`、`p10_calibration_verify.png`。

36. **A2 切片 4：自动下发/重连** —— **已完成（2026-11-13）**：
    启动/每次连接读取 `calibration.json` 并下发完整 32 组阈值；
    `OK T`/`ERR T` 跟踪已应用，坏文件不发送、不覆盖、只提示一次；
    新增 4 项测试，全套 **660 项**；真机端到端 PASS（发送 15/8、
    内部 Q 回读 15/8、恢复 12/6）。**A2 完成。**

37. **A1 公开仓库 + CI** —— **已完成（2026-11-13）**：
    `.gitignore` 与 CI 工作流；白名单首提交 347 个文件（含 vendor，
    排除私有曲/用户数据/日志/截图/构建产物/第三方引脚图）；
    `main` + `v0.1.0` 已推送；CI `pc-tests` + `firmware-build` 全绿。
    **A1 完成。**

38. **A3 首启向导 + 帮助页** —— **已完成（2026-11-13）**：
    `OnboardingState`/`onboarding.json`、四步向导、第 7 个“帮助”入口、
    7 页索引/键位图/故障排查、F1/顶栏/设置/`Ctrl+7` 入口；新增 23 项
    测试，全套 **684 项**；截图 `p11_help_page.png`、`p11_onboarding.png`。
    **A3 完成。**

**下一项：B9 GM 音色扩展 → B3 20 首新曲 → A4/A5/A7。**
具体优先级与批次见 §2.1、[ROADMAP_NEXT.md](ROADMAP_NEXT.md)。

之后按 B 场景补齐 H9，再按 C 场景分批生产内容；
内容批次与能力批次交替，避免长期只做功能或只堆内容。

---

## 5. 交接检查清单

新会话开始前：

- [ ] 读本文 §1「最近交接点」、§2.1「剩余工作总览」、§3.2 H7f 残留、
  §3.4 H9 与 [DESIGN_INDEX.md](DESIGN_INDEX.md)「待做事项」。
- [ ] 跑 `cd pc && python -m unittest discover -s tests -v`，确认 684 项通过。
- [ ] 确认 `curriculum.STAGES` 的实际就绪数（不要相信文档里的硬编码）；
  当前应为阶段 0–8 全部 ready、合计 74/74。
- [ ] 启动一次真实应用：`pc\run.cmd`；先关闭 PlatformIO 串口监视器；
  本机应为 COM5 + 0x5A/0x5C/0x5D 三个模块。
- [ ] 明确本次只做一个纵向切片或一批内容；先写测试再实现。
- [ ] 新内容先确认音域/映射能在 32 键上弹；超出要标注或简化。
- [ ] 私有内容处理后立即标记；不进入公开包。
- [ ] 提交前先读 [ROADMAP_NEXT.md](ROADMAP_NEXT.md) §4：核对 `.gitignore`、
  私有内容隔离、白名单添加、公开包审计；不要直接 `git add .`。
- [ ] 校准页改动先读 [CALIBRATION_DESIGN.md](CALIBRATION_DESIGN.md)；
  固件 `CAL`/`T` 与 PC 解析必须成对测试。
- [ ] 工作树已初始化 git：改前跑测试留基线，改后更新测试计数；提交前
  `git status` 核对清单；不要留下临时 `mockups/_probe*.png`、`*.tmp`
  或后台进程。
- [ ] 每批结束更新：DESIGN_INDEX、app/README、测试计数、必要的 mockup。

完成定义：

- [ ] 纯逻辑测试 + UI 测试覆盖新行为；全套通过。
- [ ] 学习页只显示真实可练内容；未就绪仍是“制作中”。
- [ ] 真实数据（MusicXML/MIDI/项目 JSON）通过 `CONTENT_PIPELINE` §6 校验。
- [ ] 真机/电脑键盘各试一次；退出后恢复用户映射与状态。

---

## 6. 需要用户拍板的事

1. ~~**范围**~~ **已定（2026-11-12）**：下一阶段按
   **A1 仓库 → A2 校准 → A3 向导/帮助 → B9 音色 → B3 新曲** 推进；
   **A1/A2/A3 已完成（2026-11-13）**，下一步 B9。校准交互、固件协议、
   数据格式见 [CALIBRATION_DESIGN.md](CALIBRATION_DESIGN.md)。
   公开仓库已初始化并推送；私有内容未进入历史。
2. **体验确认**：黑键暗色强度是否合适；分区点按曲目持久化 +「重置」的
   行为/文案是否清楚；自动跟随的 tooltip/范围行是否足够。确认后再决定
   是否继续微调。
3. ~~**五线谱引擎**~~ —— 已定：Qt `QPainter` 自绘（H7a），无第三方依赖。
4. **公开发布时间**：公开仓库已初始化并推送（A1）
   `git@github.com:qihangyang08-glitch/DIY-Music-KeyBoard.git`；
   `main` + `v0.1.0` 已发布，CI 全绿。`mariage_fragment` 未进入历史。
5. **全量曲目许可**：59 首里现代编配/教材改编需逐项核对；不确定的按
   `public_release: unknown → remove` 处理。
6. **音频导出**：设计边界是不做 WAV/音频录音；若需要，单独立项，不阻塞主线。

---

## 7. 设计边界（不要越界）

- 不做力度、完整 DAW/VST、音频录音、云账号/社交/手机版。
- **校准页只做阈值**：展示按下过程的信号曲线用于选阈值，不做力度/
  velocity；不做自动 AI 调参；校准期间不发声、不判定。
- **不做指导书的示范音频/「听示范」播放按钮（2026-11-10 决策）**；
  指导书的「示范」只保留文字要点，不制作音频或自动演奏。演奏页已有的
  曲谱示范播放（`Space`）保留。
- 图片/PDF 只做“仅显示”，不进入跟弹/解析/判定，不作为核心练习。
- 鼠标不弹琴；创作页的点击/拖动只用于编辑。
- 光条配色/中文优先/固定力度是既定设计，不要为“更像钢琴”改回钢琴键盘。

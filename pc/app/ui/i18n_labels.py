"""English catalogue for visible labels, headings, tooltips and help (A5).

Same convention as ``i18n_messages``: ``{…}`` marks an f-string hole.
Curriculum content (stage and piece names, lesson prose loaded from JSON)
is data, not chrome, and is intentionally absent.
"""

LABELS: dict[str, str] = {
    # -- shell / navigation --------------------------------------------
    "KeyBorad · 32 键电子琴": "KeyBorad · 32-key instrument",
    "32 键电子琴": "32-key instrument",
    "等待设备": "Waiting for device",
    "等待设备 · 可电脑键盘弹":
        "Waiting for device · computer keyboard works",
    "电脑键盘 · 未连接设备": "Computer keyboard · no device",
    "电脑键盘": "Computer keyboard",
    "琴 + 电脑键盘": "Instrument + computer keyboard",
    "设备无心跳": "Device not responding",
    "设备在线 · 等待模块": "Device online · waiting for modules",
    "3 模块在线": "3 modules online",
    "{…}/3 模块在线": "{}/3 modules online",
    "0 模块": "0 modules",
    "{…} 模块": "{} modules",
    " ← 返回学习": " ← Back to Learn",
    "← 返回学习": "← Back to Learn",
    "切换映射预设（Ctrl+M）": "Change mapping preset (Ctrl+M)",
    "方案 · 裸铜": "Profile · bare copper",
    "回到学习页的当前阶段 / 指导书":
        "Back to the current stage / guide on the Learn page",
    "录音中": "Recording",
    "导航": "Navigation",
    "当前": "Current",
    "下一键": "Next",
    "最近": "Recent",
    "输入 · 无": "Input · none",
    "输入 · {…}": "Input · {}",
    "未命名": "Unnamed",
    "无音频": "No audio",
    "音频已关闭（--no-audio）": "Audio off (--no-audio)",
    "怎么用（F1）": "How to use (F1)",
    "演奏（Ctrl+1）": "Perform (Ctrl+1)",
    "学习（Ctrl+2）": "Learn (Ctrl+2)",
    "曲谱（Ctrl+3）": "Library (Ctrl+3)",
    "创作（Ctrl+4）": "Create (Ctrl+4)",
    "设备（Ctrl+5）": "Device (Ctrl+5)",
    "设置（Ctrl+6）": "Settings (Ctrl+6)",
    "帮助（Ctrl+7）": "Help (Ctrl+7)",
    "演奏": "Perform",
    "学习": "Learn",
    "曲谱": "Library",
    "创作": "Create",
    "设备": "Device",
    "设置": "Settings",
    "帮助": "Help",
    "鼓垫": "Drum pads",
    "超出音域": "out of range",
    "光条": "bar",
    "音": "notes",
    # -- perform --------------------------------------------------------
    "开启后按乐句（最多 4 小节）自动切换 32 键的八度窗口，让宽音域谱也能弹；关闭则保持当前映射与八度。":
        "When on, wide scores follow phrase by phrase (up to 4 bars), "
        "shifting the 32-key octave window; when off, the current mapping "
        "and octave stay fixed.",
    "无跟随 · 手动翻页": "No follow · manual page",
    "范围 {…}": "Range {}",
    "音色": "Sound",
    "钢琴 1": "Piano 1",
    "映射": "Mapping",
    "半音阶": "Chromatic",
    "C 大调": "C major",
    "A 小调": "A minor",
    "五声音阶": "Pentatonic",
    "左右分区": "Split",
    "白键 19 键": "White keys 19",
    "重置": "Reset",
    "清除本曲目保存的分区点，恢复内容默认的分区位置":
        "Clear this piece's saved split point and restore the default",
    "自动跟随乐谱": "Follow score",
    "走带": "Transport",
    "循环播放 A–B 小节范围": "Loop the A–B bar range",
    "循环": "Loop",
    "A–B 未设置": "A–B not set",
    "速度": "Speed",
    "节拍器": "Metronome",
    "跟弹时按拍发出木鱼声": "Woodblock click on each beat while following",
    "预备拍": "Count-in",
    "开始前先空一小节，只响拍子不计分":
        "Play one bar of clicks before scoring starts",
    "八度": "Octave",
    "移调": "Transpose",
    "● 录音": "● Record",
    "全部静音": "Mute all",
    "立刻停掉所有正在响的音（Esc）":
        "Stop every sounding note now (Esc)",
    "未校准 · 后续版本": "Uncalibrated · later version",
    "复位{…}": "Reset {}",
    "复位": "Reset",
    "复位八度": "Reset octave",
    "复位移调": "Reset transpose",
    "把循环起点设在当前小节": "Set the loop start at the current bar",
    "把循环终点设在当前小节": "Set the loop end at the current bar",
    "鼓垫 · 32 键": "Drum pads · 32 keys",
    "专用通道 9 · 不参与跟弹判定":
        "Channel 9 · not used for follow judging",
    "{…} 32 键鼓垫": "{} 32-key drum pads",
    "鼓垫模式": "Drum pad mode",
    "自动跟随 · {…}": "Auto follow · {}",
    "{…} · 音域适配": "{} · range adapted",
    "分区 {…} · 拖动光条琥珀线调整":
        "Split {} · drag the amber line on the light bar",
    "敲击发声 · 不参与判定": "Plays on hit · not judged",
    "自动跟随 · 整曲一个窗口": "Auto follow · one window for the piece",
    "自动跟随 · 等待可解析曲谱":
        "Auto follow · waiting for a parseable score",
    "跟弹 · 当前音域不够": "Follow · current range is too small",
    "跟弹 · 按对前进": "Follow · press the next key",
    "范围": "Range",
    "Chromatic · 半音阶 · 每个物理键一个半音":
        "Chromatic · one semitone per physical key",
    "C Major · C 大调音阶铺满 32 键（更宽的音域）":
        "C Major · C-major scale across all 32 keys (wider range)",
    "A Minor · A 自然小调音阶铺满 32 键":
        "A Minor · A-natural-minor scale across all 32 keys",
    "Pentatonic · C 大调五声音阶，适合即兴":
        "Pentatonic · C-major pentatonic, good for improvising",
    "Split 16/16 · 左手 1–16 低音区 C3–D#4，右手 17–32 高音区 C5–D#6":
        "Split 16/16 · left 1–16 C3–D#4, right 17–32 C5–D#6",
    "White keys C4–G6 · C4–G6 白键 · 键 1–19 可弹，20–32 禁用（适合识谱入门）":
        "White keys C4–G6 · keys 1–19 play, 20–32 disabled (note-reading)",
    # -- score view -----------------------------------------------------
    "五线谱": "Staff",
    "显示当前曲目、播放头、命中/未中与指法踏板标记":
        "Shows the score, playhead, hit/miss marks, fingering and pedal",
    "已解析成功。谱面渲染在后续版本；请用“落键”查看音符、播放头和下一键。":
        "Parsed successfully. Rendering arrives in a later version; use "
        "Keys to see notes, the playhead and the next key.",
    "落键视图 · 拖入 MusicXML / MIDI 或载入示例谱开始跟弹":
        "Keys view · drop a MusicXML / MIDI file or load a sample score",
    "重来": "Restart",
    "回到谱子开头，重新练习":
        "Back to the start of the score and practice again",
    "上一页谱面": "Previous page",
    "下一页谱面": "Next page",
    "标记": "Markings",
    "显示指法、踏板、连音线与奏法标记":
        "Show fingering, pedal, slurs and articulation marks",
    "示例谱 · 占位": "Sample score · placeholder",
    "谱面占位 · 拖入 PNG / JPG 查看图片":
        "Placeholder · drop a PNG / JPG to view an image",
    "{…} · 图片谱 · 不跟随": "{} · image score · no follow",
    "鼓垫模式 · 不参与判定": "Drum pad mode · not judged",
    "谱面": "Sheet",
    "落键": "Keys",
    "专注": "Focus",
    "图片谱不跟随 · 手动翻页":
        "Image scores do not follow · turn pages manually",
    "播放中 · 示例播放头": "Playing · sample playhead",
    "已暂停": "Paused",
    "下一键 {…} · 第 {…} 小节": "Next key {} · bar {}",
    "已完成 · 按“重来”或空格示范":
        "Finished · press Restart or Space for the demo",
    "命中": "Hits",
    "未中": "Misses",
    "示范播放中": "demo playing",
    "该文件": "this file",
    # -- light bar ------------------------------------------------------
    "延音": "Sustain",
    "八度−": "Octave−",
    "八度+": "Octave+",
    "延音：按住时松开的音继续响（Shift 同样有效）":
        "Sustain: notes keep ringing after release (Shift also works)",
    "八度 −：整体降一个八度（Ctrl+[）":
        "Octave −: shift everything down one octave (Ctrl+[)",
    "八度 +：整体升一个八度（Ctrl+]）":
        "Octave +: shift everything up one octave (Ctrl+])",
    "映射：循环音域映射预设（Ctrl+M）":
        "Mapping: cycle the range presets (Ctrl+M)",
    "分区 {…} · 拖动调整左右手音域（松手按曲目保存）":
        "Split {} · drag to set the hands' ranges (saved per piece)",
    "电脑键 {…}": "Computer key {}",
    "电脑键未绑定": "No computer key bound",
    "光条 {…} · 当前映射禁用此键 · {…}（按键不发声）":
        "Bar {} · disabled by the current mapping · {} (silent)",
    "光条 {…} · {…} · {…} · {…}（点击不发声）":
        "Bar {} · {} · {} · {} (click does not sound)",
    "左手": "Left hand",
    "右手": "Right hand",
    # -- key bindings ---------------------------------------------------
    "播放 / 暂停": "Play / pause",
    "延音（按住）": "Sustain (hold)",
    "显示 / 隐藏标签": "Show / hide labels",
    "帮助 / 怎么用": "Help / how to use",
    "页面：演奏": "Page: Perform",
    "页面：学习": "Page: Learn",
    "页面：曲谱": "Page: Library",
    "页面：创作": "Page: Create",
    "页面：设备": "Page: Device",
    "页面：设置": "Page: Settings",
    "页面：帮助": "Page: Help",
    "切换音域映射": "Change range mapping",
    "切换音色": "Change sound",
    "八度 −": "Octave −",
    "八度 +": "Octave +",
    "移调 −": "Transpose −",
    "移调 +": "Transpose +",
    "全屏": "Full screen",
    "光条 {…}": "Bar {}",
    "功能“{…}”": "Action “{}”",
    "光条 {…} 与光条 {…} 都绑定了 {…}":
        "Bars {} and {} both use {}",
    "光条 {…}（{…}）与功能“{…}”（{…}）冲突":
        "Bar {} ({}) conflicts with action “{}” ({})",
    "功能“{…}”与“{…}”都绑定了 {…}":
        "Actions “{}” and “{}” both use {}",
    # -- pages: device / sound / settings ------------------------------
    "当前只读状态。通道表、原始监视与重新初始化在后续版本。":
        "Read-only for now. The channel table, raw monitor and re-init "
        "arrive in a later version.",
    "模块 1 · 左侧 · 键 1–12": "Module 1 · left · keys 1–12",
    "模块 2 · 中间 · 键 13–24": "Module 2 · middle · keys 13–24",
    "模块 3 · 右侧 · 键 25–32 + 4 个功能键":
        "Module 3 · right · keys 25–32 + 4 function keys",
    "未连接": "Not connected",
    "通道表、原始监视、错误计数：后续版本":
        "Channel table, raw monitor, error counts: later version",
    "打开校准页": "Open calibration",
    "当前简版：GM 音色切换。混响、亮度、SoundFont 导入在后续版本。":
        "Current version: GM sound switching. Reverb, brightness and "
        "SoundFont import arrive later.",
    "搜索音色、英文名或 GM 编号": "Search sound, English name or GM number",
    "鼓组 · 专用通道 9": "Drum kits · channel 9",
    "鼓垫模式：32 键显示鼓件名，不参与跟弹/学习判定。":
        "Drum pad mode: the 32 keys show drum names and are not judged.",
    "静音": "Mute",
    "固定力度 100 · 不做按键力度（探针结论）":
        "Fixed velocity 100 · key velocity is not measured",
    "全部": "All",
    "主题、语言、辅助功能、键位与音色；更多设置在后续版本。":
        "Theme, language, accessibility, key bindings and sounds; more "
        "settings are coming later.",
    "主题": "Theme",
    "纸白（Studio）": "Paper (Studio)",
    "暗场（Stage）": "Dark (Stage)",
    "语言": "Language",
    "中文": "Chinese",
    "辅助功能": "Accessibility",
    "减少动效": "Reduce motion",
    "高对比度": "High contrast",
    "字号": "Text size",
    "小": "Small",
    "标准": "Normal",
    "大": "Large",
    "关闭光条上的呼吸、光柱与松键淡出；跟弹判定与播放头不受影响。":
        "Turn off breathing, columns and release fades on the light bar; "
        "follow judging and the playhead are unaffected.",
    "加深正文与次要文字、加强分隔线，所有文字对比度达到 WCAG AA；主题观感会更硬朗。":
        "Darken body and secondary text and strengthen dividers until all "
        "text reaches WCAG AA; the theme looks crisper.",
    "只缩放界面文字；光条与谱面几何不变":
        "Scales UI text only; the light bar and staff geometry do not change",
    "对错反馈不只靠颜色：× / ✓ 与文字同时显示。":
        "Feedback never relies on colour alone: × / ✓ and text appear together.",
    "高级（只读）": "Advanced (read-only)",
    "松开宽限 20 ms · 连奏关闭": "Release grace 20 ms · legato off",
    "固定力度 100": "Fixed velocity 100",
    "方案 · 裸铜 · 未校准（校准页制作中）":
        "Profile · bare copper · uncalibrated (calibration is being built)",
    "会话日志：后续版本接入": "Session log: coming in a later version",
    "工具": "Tools",
    "键位可在“键位设置”里全部改绑；字母默认留给音符。":
        "Every key can be rebound in Key bindings; letters are reserved for notes.",
    "Tab 聚焦，←/→ 移动，Enter/Space 选择":
        "Tab focuses, ←/→ moves, Enter/Space selects",
    "界面文字 {…}%": "UI text {}%",
    "键位设置": "Key bindings",
    "音色页": "Sounds",
    "音频 · {…}{…}": "Audio · {}{}",
    "在线": "Online",
    "离线": "Offline",
    "无心跳": "No heartbeat",
    # -- help -----------------------------------------------------------
    "按页面查找按钮说明；每条 1–2 行，照着做即可。":
        "Find each page's controls here; every line is one or two steps.",
    "看键位图": "View key map",
    "快速开始": "Quick start",
    "页面与按钮": "Pages and buttons",
    "故障排查": "Troubleshooting",
    "键位图": "Key map",
    "键帽可改；点击 设置 → 键位设置。光条号 1–32 与琴键对应。":
        "Keycaps are rebindable: Settings → Key bindings. Bars 1–32 map to "
        "the physical keys.",
    "功能键": "Function keys",
    "重新打开首启向导": "Reopen the first-run wizard",
    "去校准": "Go to calibration",
    "连接：插上 USB，应用自动识别 ESP32-S3；状态条显示 3 个模块在线。":
        "Connect: plug in USB; the app finds the ESP32-S3 and the status "
        "bar shows 3 modules online.",
    "发声：实体琴键与电脑键盘进入同一个 20 ms 引擎；顶栏有 48 kHz 即可出声。":
        "Sound: the physical keys and computer keyboard share one 20 ms "
        "engine; audio works when the header shows 48 kHz.",
    "电脑键盘：Z X C… / A S D… / Q W E… 三行；Ctrl+Tab 显示当前键帽。":
        "Computer keyboard: three rows Z X C… / A S D… / Q W E…; Ctrl+Tab "
        "shows the keycaps.",
    "中央 C：学习 → 阶段 0 →「找到中央 C」会把键位临时映射到 C4 起。":
        "Middle C: Learn → Stage 0 → “Find middle C” temporarily maps the "
        "keys from C4.",
    "没声音：看顶栏是否 48 kHz；先关闭 PlatformIO 串口监视器；--no-audio 会静音。":
        "No sound: check for 48 kHz in the header; close the PlatformIO "
        "serial monitor; --no-audio mutes the app.",
    "没设备：状态条显示「等待设备」；仍可用电脑键盘；确认 COM 口未被占用。":
        "No device: the status bar says Waiting for device; the computer "
        "keyboard still works; make sure the COM port is not in use.",
    "按键无反应：中文输入法下仍按物理位置；多键无冲时优先用实体琴。":
        "Keys do nothing: with a Chinese IME use physical positions; for "
        "many keys at once prefer the physical keyboard.",
    "谱面不跟随：确认曲目可跟弹（不是图片/PDF）；按 Space 开始示范。":
        "Score does not follow: confirm the piece is followable (not an "
        "image/PDF); press Space to start the demo.",
    "校准后仍丢键：设备 → 校准，用「多指验证」重按和弦；弱键单独调阈值。":
        "Still dropping keys after calibration: Device → Calibration, retry "
        "the chord with Multi-key check, and tune weak keys separately.",
    "按键卡住：Esc 全部静音并松开所有键；必要时重新插拔设备。":
        "Stuck key: press Esc to mute and release every key; replug the "
        "device if needed.",
    "Space 示范 / Esc 停止 / Ctrl+M 映射 / Ctrl+P 音色；Shift 延音，[ / ] 八度。":
        "Space demo / Esc stop / Ctrl+M mapping / Ctrl+P sound; Shift "
        "sustains, [ / ] change octave.",
    "阶段卡 → 指导书 → 去练习；点「返回学习」回到原阶段或课次。":
        "Stage card → guide → practice; “Back to Learn” returns to that "
        "stage or lesson.",
    "搜索、筛选、导入 MusicXML/MIDI/图片；★ 收藏；图片与 PDF 只显示。":
        "Search, filter and import MusicXML/MIDI/images; ★ favorites; "
        "images and PDFs are display-only.",
    "录音/叠录/循环、最多 8 轨、混音、节拍器、导出 MIDI。":
        "Record/overdub/loop, up to 8 tracks, mixing, metronome and MIDI "
        "export.",
    "3 个 MPR121 在线状态；「打开校准页」做逐键阈值；重新检测。":
        "Status of the 3 MPR121 modules; “Open calibration” sets per-key "
        "thresholds; re-detect.",
    "主题、语言、字号、减少动效；「键位设置」改音符键与功能键。":
        "Theme, language, text size and reduce motion; Key bindings edits "
        "note and function keys.",
    "本页：快速开始、页面按钮、键位图、故障排查、重开向导。":
        "This page: quick start, page controls, key map, troubleshooting "
        "and reopening the wizard.",
    "怎么用": "How to use",
    "光条 {…} · {…}": "Bar {} · {}",
    "光条 {…}": "Bar {}",
    # -- onboarding -----------------------------------------------------
    "连接与试弹": "Connect and try a key",
    "校准（可选）": "Calibration (optional)",
    "页面地图": "Page map",
    "第一课": "First lesson",
    "欢迎使用 KeyBorad": "Welcome to KeyBorad",
    "首次使用 · KeyBorad": "First run · KeyBorad",
    "跳过": "Skip",
    "上一步": "Back",
    "下一步": "Next",
    "电脑键盘：Z X C… / A S D… / Q W E… 三行，中文输入法下仍按物理位置。Ctrl+Tab 可显示键帽。":
        "Computer keyboard: three rows Z X C… / A S D… / Q W E…; with a "
        "Chinese IME use physical positions. Ctrl+Tab shows the keycaps.",
    "重新检测": "Detect again",
    "逐键阈值解决小拇指弱信号与多指齐按丢键；可以稍后从 设备 → 校准 进入。跳过不影响演奏。":
        "Per-key thresholds fix weak pinkies and dropped notes in chords; "
        "open Device → Calibration later. Skipping does not block playing.",
    "学习 → 阶段 0 →「找到中央 C」。弹 3 个音即可完成，之后可以继续学五线谱或直接演奏。":
        "Learn → Stage 0 → “Find middle C”. Play 3 notes to finish, then "
        "continue with the staff or just play.",
    "打开阶段 0": "Open stage 0",
    "第 {…} / {…} 步": "Step {} / {}",
    "已连接 · 3 个模块在线。可以按实体琴键试弹。":
        "Connected · 3 modules online. Try a physical key.",
    "已连接 · {…}/3 模块在线。可以先用电脑键盘。":
        "Connected · {}/3 modules online. You can use the computer keyboard.",
    "未检测到琴。你仍然可以用电脑键盘演奏：Z X C… / A S D… / Q W E…。":
        "No instrument detected. You can still play with the computer "
        "keyboard: Z X C… / A S D… / Q W E….",
    "已保存方案 · {…} · {…}": "Saved profile · {} · {}",
    "当前未校准。建议先做一次逐键校准；也可以先跳过。":
        "Not calibrated yet. A per-key calibration is recommended; you "
        "can also skip.",
    "完成": "Finish",
    # -- small canvases -------------------------------------------------
    "钢琴卷帘": "Piano roll",
    "显示当前音轨的音符与播放头；左键画、右键擦、拖动移动":
        "Shows the current track's notes and playhead; left-draw, "
        "right-erase, drag to move",
    "休": "Rest",
    "节奏型时间线": "Rhythm timeline",
    "显示小节、拍点、节奏块、休止与命中状态":
        "Shows bars, beats, rhythm blocks, rests and hits",
    "✓ 偏差 {…} ms": "✓ off by {} ms",
    "多按": "extra",
    "漏": "missed",
    "静音切换": "Mute",
    "按下后停止全部声音；再次按下恢复":
        "Stops all sound; press again to restore",
    "鼓垫模式 · 不参与判定": "Drum pad mode · not judged",
}

"""English catalogue for the Learn / Library / Create / Calibration pages.

Only chrome lives here. Stage names, piece titles, composers and lesson prose
come from content files and stay in their authored language.
"""

PAGES: dict[str, str] = {
    # -- learning overview ---------------------------------------------
    "可开始": "Ready",
    "部分就绪": "Partly ready",
    "制作中": "In progress",
    "✓ 已完成": "✓ Completed",
    "✓ 可练内容完成": "✓ Practice items done",
    "最佳 {…}/{…} · 未中 {…} · {…}%": "Best {}/{} · misses {} · {}%",
    "训练 {…}/{…}": "Drills {}/{}",
    "首答 {…}/{…}": "First try {}/{}",
    "连对 {…}": "Streak {}",
    "已练 {…}/{…} · 错误 {…}{…}": "Practised {}/{} · errors {}{}",
    "✓ 已完成 · 最佳 {…}/{…} · 未中 {…} · {…}%":
        "✓ Completed · best {}/{} · misses {} · {}%",
    "训练 {…} · 曲目 {…}/{…}": "Drills {} · pieces {}/{}",
    "可练内容完成 {…}/{…}": "Practice items done {}/{}",
    "阶段 {…} · {…}": "Stage {} · {}",
    "9 个阶段：基础 → 演奏 → 创作。先看全貌，再选一课。":
        "9 stages: basics → playing → creating. See the path, then pick a lesson.",
    "不学也可以直接演奏 / 创作":
        "You can also skip learning and play or create directly.",
    "继续": "Continue",
    "还没有学习记录 · 先弹出第一个音":
        "No learning record yet · play the first note",
    "开始": "Start",
    "可练习项目 {…}/{…} 已完成 · 只把已有谱面、训练生成器或可用项目模板的内容标为可练习；其余显示“制作中”，不伪装成可跟弹。":
        "{} of {} practice items done · only items with a score, drill "
        "generator or usable project template count as ready; the rest say "
        "In progress instead of pretending to be playable.",
    "← 学习路线": "← Learning path",
    "前置 · {…}": "Prerequisite · {}",
    "← 阶段 {…} · {…}": "← Stage {} · {}",
    "指导书 · 约 {…} 分钟": "Guide · about {} min",
    "已勾选 {…}/{…}": "Checked {}/{}",
    "这一课现在可以直接做节奏训练：先听 1 小节预备拍，再按任意键踩拍。完成后回到这一页，结果会写进本地学习档案。":
        "This lesson can be practised as rhythm now: listen to one bar of "
        "count-in, then press any key on the beat. Come back here when done; "
        "the result is saved to the local learning record.",
    "练习记录 · {…}": "Practice record · {}",
    "平均 {…}s": "average {}s",
    "平均 {…}ms": "average {}ms",
    "✓ 已完成 · 最佳 {…}/{…} · 错误 {…} · 准确率 {…}%{…}":
        "✓ Completed · best {}/{} · errors {} · accuracy {}%{}",
    "正确 {…}/{…} · 错误 {…} · {…}% · {…}":
        "Correct {}/{} · errors {} · {}% · {}",
    "阶段 {…}–{…}": "Stages {}–{}",
    "前置 · ": "Prerequisite · ",
    "指导书 · 点开看整页": "Guides · open a full lesson",
    "训练": "Drills",
    "内容制作中": "Content in progress",
    "曲目": "Pieces",
    "阶段 0–2 以训练代替完整曲目；训练即通关内容。":
        "Stages 0–2 use drills instead of full pieces; drills are the "
        "passing content.",
    "通关标准": "Pass criteria",
    "下一步 · {…}": "Next · {}",
    "开始训练": "Start drill",
    "未参加 · 随时可以试一次": "Not taken · try it any time",
    "重新考核": "Retake exam",
    "参加考核": "Take exam",
    "图示未找到 · {…}": "Figure not found · {}",
    "图示载入失败 · {…}": "Figure failed to load · {}",
    "谱例未找到 · {…}": "Example not found · {}",
    "谱例载入失败 · {…}": "Example failed to load · {}",
    "谱例没有音符 · {…}": "Example has no notes · {}",
    "目标": "Goals",
    "知识": "Knowledge",
    "这一课要做什么": "What this lesson covers",
    "要点": "Key points",
    "这一课现在可以直接做识谱训练：看谱 → 在光条上按下对应的音。完成后回到这一页，结果会写进本地学习档案。":
        "This lesson can be practised as note reading now: read the staff → "
        "press that note on the light bar. Come back here when done; the "
        "result is saved to the local learning record.",
    "正文、图示与可试听的谱例制作中。现在可以先去演奏页跟弹，练习时顶部的「返回学习」会回到这一页。":
        "Prose, figures and playable examples are in progress. You can "
        "follow a score on the Perform page now; “Back to Learn” returns here.",
    "考核 · 可选，不影响普通练习": "Exam · optional, does not block practice",
    "打开项目": "Open project",
    "去练习": "Practise",
    "先修": "Prerequisite",
    "示范": "Demonstration",
    "练习": "Practice",
    "常见错误": "Common mistakes",
    "检查": "Check",
    "下一步": "Next",
    "下一课 · {…}": "Next lesson · {}",
    "下一阶段 · {…}": "Next stage · {}",
    "本课暂无对应训练 · 可先去演奏页自由练习":
        "No drill for this lesson yet · practise freely on Perform",
    "这一阶段的练习内容制作中": "This stage's practice content is in progress",
    "约 {…} 分钟 · {…}": "About {} min · {}",
    "打开 →": "Open →",
    "正文制作中": "Prose in progress",
    "素材 · {…}": "Asset · {}",
    "本地学习档案": "Local learning record",
    "继续上次": "Continue last",
    "从这里开始": "Start here",
    # -- drill page -----------------------------------------------------
    "（键面 {…}）": "(key {})",
    "结果已写入本地学习档案。":
        "The result was saved to the local learning record.",
    " · 错按 {…} · {…}%": " · wrong {} · {}%",
    "五线谱单音题": "Staff single-note drill",
    "高音谱号上显示一个音，请在光条上按下它":
        "A note appears on the treble staff; press it on the light bar",
    "32 键作答光条": "32-key answer bar",
    "显示当前训练音域、键位与题目答案槽":
        "Shows the drill range, keys and answer slots",
    "← 学习": "← Learn",
    "音名闪卡": "Note-name flashcards",
    "识谱训练": "Note reading",
    "高音谱号 · {…}": "Treble clef · {}",
    "看谱 → 在光条上按下这个音":
        "Read the staff → press that note on the light bar",
    "训练音域 C4–G6 · 光条 1 = C4":
        "Drill range C4–G6 · bar 1 = C4",
    "只判音名与八度 · 错按可重试":
        "Judges note name and octave only · retry after a miss",
    "节奏训练": "Rhythm training",
    "按任意键踩拍 · 先听 1 小节预备":
        "Press any key on the beat · one bar of count-in first",
    "准备 · 按开始": "Ready · press Start",
    "重来": "Restart",
    "Enter / Space 开始或停止 · Esc 停止 / 返回":
        "Enter / Space starts or stops · Esc stops / goes back",
    "第 {…}/{…} 步": "Step {}/{}",
    "找到中央 C": "Find middle C",
    "按提示操作 · 做完这一步会自动进入下一步":
        "Follow the prompt · the next step starts automatically",
    "只判这一步的动作 · 按错可重试":
        "Only this step is judged · retry after a mistake",
    "训练完成": "Drill complete",
    "再练一次": "Practise again",
    "返回阶段": "Back to stage",
    "Enter / Space 再练一次 · Esc / Backspace 返回阶段":
        "Enter / Space practises again · Esc / Backspace goes back",
    "考核": "Exam",
    "停止": "Stop",
    "预备 · 听节拍": "Ready · listen to the beat",
    "已停止 · 按开始重来": "Stopped · press Start to retry",
    "完成": "Finish",
    "先按住 Shift（延音），再按 {…}。":
        "Hold Shift (sustain), then press {}.",
    "这是 {…}；这一步要按 {…}{…}":
        "This is {}; for this step press {}{}",
    "✓ {…} · ✗ {…} · 连对 {…}": "✓ {} · ✗ {} · streak {}",
    "按键 {…}": "Key {}",
    "题目 {…}": "Prompt {}",
    "这一项已记录；阶段里还有其他可练项目。":
        "This item is recorded; the stage has other practice items.",
    "首次答对 {…}/{…} · 错按 {…} · 准确率 {…}%\n平均反应 {…} · 最长连对 {…}":
        "First-try {} of {} · wrong {} · accuracy {}%\nAverage reaction "
        "{} · best streak {}",
    "考核{…} · {…}": "Exam {} · {}",
    "上手训练 · {…} {…}/{…} 步": "Starter drill · {} {}/{} steps",
    "节奏记录 · 踩准 {…}/{…} · 漏拍 {…} · 多按 {…}":
        "Rhythm record · on beat {}/{} · missed {} · extra {}",
    "训练记录 · 答对 {…}/{…}": "Drill record · correct {}/{}",
    "训练记录 · 已答 {…}/{…}": "Drill record · answered {}/{}",
    " · 错按 {…}": " · wrong {}",
    " · 平均 {…}s": " · average {}s",
    " · 连对 {…}": " · streak {}",
    "考核成绩": "Exam result",
    "再考一次": "Retake",
    "Enter / Space 再考一次 · Esc / Backspace 返回阶段":
        "Enter / Space retakes · Esc / Backspace goes back",
    "{…} BPM · {…} · {…} 小节": "{} BPM · {} · {} bars",
    "上手训练 · {…}": "Starter drill · {}",
    "准备 · 按开始 / Enter": "Ready · press Start / Enter",
    "预备 {…} · 听节拍": "Count-in {} · listen",
    "✓ 正确 · {…}{…}": "✓ Correct · {}{}",
    " · 光条 {…}": " · bar {}",
    "这是 {…}；正确是 {…}{…}{…}": "This is {}; the correct note is {}{}{}",
    "漏拍 {…} · 多按 {…} · 连对 {…}": "Missed {} · extra {} · streak {}",
    "第 {…}/{…} 题": "Question {}/{}",
    "光条 {…} = {…}": "Bar {} = {}",
    "本阶段已全部完成。": "This stage is complete.",
    "考核通过 ✓": "Exam passed ✓",
    "考核未通过": "Exam not passed",
    "{…} · {…}\n可随时重考；阶段通关仍按普通练习记录，考核不阻止普通练习完成。":
        "{} · {}\nYou can retake any time; stage progress still comes from "
        "regular practice, and the exam never blocks it.",
    "完成 {…}/{…} 步 · 错按 {…} · 一次做对 {…}/{…}":
        "Finished {}/{} steps · wrong {} · first-try {}/{}",
    "踩准 {…} · 漏拍 {…} · 多按 {…}": "On beat {} · missed {} · extra {}",
    "漏拍 {…} · 多按 {…} · 准确率 {…}% · 平均偏差 {…}\n最长连对 {…} · {…}":
        "Missed {} · extra {} · accuracy {}% · average offset {}\nBest "
        "streak {} · {}",
    "通过": "Passed",
    "未通过": "Not passed",
    "已完成": "Completed",
    "上手训练": "Starter drill",
    "踩准 {…}/{…} · 漏拍 {…} · 多按 {…}":
        "On beat {}/{} · missed {} · extra {}",
    "踩准 {…}/{…}": "On beat {}/{}",
    "本阶段可练内容已完成；其余训练仍显示“制作中”，不会被算作已学会。":
        "All practice content in this stage is done; other drills still say "
        "In progress and are not counted as learned.",
    "平均偏差 {…} · 最长连对 {…}\n{…} BPM · {…} · {…} 小节":
        "Average offset {} · best streak {}\n{} BPM · {} · {} bars",
    "首答 {…}/{…} · 错按 {…} · 平均反应 {…}":
        "First-try {}/{} · wrong {} · average reaction {}",
    "\n可随时重考；阶段通关仍按普通练习记录，考核不阻止普通练习完成。":
        "\nYou can retake any time; stage progress still comes from regular "
        "practice, and the exam never blocks it.",
    " · 上次 {…} ms": " · last {} ms",
    # -- creation -------------------------------------------------------
    "切换 GM 音色": "Change GM sound",
    "音量 −10%": "Volume −10%",
    "音量 +10%": "Volume +10%",
    "声像：左 ← C → 右": "Pan: left ← C → right",
    "叠": "Layer",
    "一键双音色 · 叠加第二音色":
        "Two sounds at once · add a second sound",
    "分": "Split",
    "键盘分区 · C4 以下/以上不同音色":
        "Keyboard split · different sounds below/above C4",
    "静音这条音轨（导出时剔除）":
        "Mute this track (excluded on export)",
    "独奏这条音轨（导出时只留独奏轨）":
        "Solo this track (export keeps only solo tracks)",
    "音轨 {…} · {…}": "Track {} · {}",
    "GM {…} · 点击切换": "GM {} · click to change",
    "{…} 音": "{} notes",
    "录音 · 编曲": "Record · arrange",
    "只录音符事件 · 最多 8 轨 · 不录音频 · 鼠标点光条不发声":
        "Note events only · up to 8 tracks · no audio recording · clicking "
        "the light bar is silent",
    "检查完成": "Check project",
    "按阶段 7 的验收规则检查当前项目":
        "Check the project against the stage 7 criteria",
    "学习项目 · {…}": "Study project · {}",
    "● 录音": "● Record",
    "从当前音轨开始录音（Ctrl+4 到达本页）":
        "Record on the current track (Ctrl+4 opens this page)",
    "✚ 叠录": "✚ Overdub",
    "把本次演奏并入当前音轨": "Add this performance to the current track",
    "■ 停止": "■ Stop",
    "▶ 播放": "▶ Play",
    "试听项目（Space）；播放时卷帘显示播放头":
        "Audition the project (Space); the roll shows the playhead",
    "↻ 循环": "↻ Loop",
    "循环 1–4 小节；录音中不可改":
        "Loop 1–4 bars; cannot change while recording",
    "♩ 节拍器": "♩ Metronome",
    "按项目速度开/关节拍器":
        "Turn the metronome on/off at the project tempo",
    "预备拍": "Count-in",
    "录音前先空一小节，只响节拍不记录":
        "One bar of clicks before recording, not captured",
    "保存": "Save",
    "载入": "Load",
    "导出 MIDI": "Export MIDI",
    "按 ● 录音开始 · 第一轨会自动建立":
        "Press ● Record to start · the first track is created",
    "模板": "Templates",
    "未命名项目": "Untitled project",
    "钢琴独奏": "Piano solo",
    "旋律 + 伴奏": "Melody + accompaniment",
    "左手贝斯 + 右手钢琴": "Left bass + right piano",
    "弦乐铺底": "String pad",
    "音轨": "Tracks",
    "混响": "Reverb",
    "项目混响：回放与 MIDI 导出同步":
        "Project reverb: applied to playback and MIDI export",
    "项目混响 0–100%": "Project reverb 0–100%",
    "＋ 新增音轨": "＋ Add track",
    "左键画 · 右键擦 · 拖动移动 · Ctrl+拖动复制 · 拖右缘改时值":
        "Left-draw · right-erase · drag to move · Ctrl+drag to copy · drag "
        "the right edge to change length",
    "缩小卷帘": "Zoom out",
    "放大卷帘": "Zoom in",
    "量化 1/8": "Quantise 1/8",
    "把当前轨音符起点对齐到 1/8 网格":
        "Snap the current track's note starts to a 1/8 grid",
    "撤销": "Undo",
    "撤销上一次音符编辑": "Undo the last note edit",
    "录音已停止 · 可继续叠录或保存":
        "Recording stopped · overdub again or save",
    "叠加中 · {…}（点击关闭）": "Layered · {} (click to turn off)",
    "分区中 · 低音 {…} / 高音 {…}": "Split · low {} / high {}",
    "键盘分区 · 低音区/高音区不同音色":
        "Keyboard split · different sounds for low/high",
    "从模板新建 · {…}": "New from template · {}",
    "还没有音轨 · 按 ● 录音会自动建第一轨":
        "No tracks yet · ● Record creates the first one",
    "⏸ 暂停": "⏸ Pause",
    "叠录中 · 新音符并入当前音轨":
        "Overdubbing · new notes join the current track",
    "录音中 · 松开按键结束一个音":
        "Recording · release a key to end the note",
    "开始叠录 · 音轨 {…}": "Overdub started · track {}",
    "开始录音 · 音轨 {…}": "Recording started · track {}",
    "循环 1–{…} 小节": "Loop bars 1–{}",
    # -- calibration ----------------------------------------------------
    "点曲线或拖动阈值线；←/→ 微调，Shift+←/→ ±5":
        "Click a curve or drag the threshold line; ←/→ fine-tunes, "
        "Shift+←/→ ±5",
    "峰值 {…}": "Peak {}",
    "阈值 {…}": "Threshold {}",
    "时间 →": "Time →",
    "按和弦：✓ 超过阈值，! 余量不足 15%，× 按了但未识别":
        "Press a chord: ✓ above threshold, ! less than 15% margin, × pressed "
        "but not detected",
    "键 {…} · {…}": "Key {} · {}",
    "释放 {…}": "Release {}",
    "设备校准": "Device calibration",
    "逐键阈值": "Per-key thresholds",
    "只调每个键的触键阈值，不做力度。校准期间不发声、不判定、不写学习记录。":
        "Only touch thresholds are tuned; velocity is not measured. "
        "Calibration is silent and writes no learning record.",
    "开始检测": "Start capture",
    "按下想校准的键，可以一次按多个；每个键一张曲线。松开并回落后自动结束。":
        "Press the keys to calibrate, several at once if you like; each key "
        "gets its own curve. Capture ends after release and settling.",
    "✓ 通过 · ! 余量不足 15% · × 按了未识别 · 按和弦验证":
        "✓ pass · ! less than 15% margin · × pressed but not detected · "
        "verify with a chord",
    "应用到设备": "Apply to device",
    "保存方案": "Save profile",
    "再测一次": "Capture again",
    "多指验证": "Multi-key check",
    "增益 —": "Gain —",
    "切换固件模拟增益（1.0x–4.0x）；改增益后需要重新校准":
        "Cycle the firmware gain (1.0x–4.0x); changing it requires a new "
        "calibration",
    "结束验证": "End check",
    "多指验证 · 通过 {…}/{…} · 按和弦":
        "Multi-key check · passed {}/{} · press a chord",
    "多指验证 · 先应用阈值":
        "Multi-key check · apply thresholds first",
    "增益 {…}": "Gain {}",
    "等待按键…": "Waiting for keys…",
    "峰值 60%": "Peak 60%",
    "稳定段一半": "Half of the stable span",
    "建议": "Suggested",
    "峰值 {…} · 噪声 {…} · 稳定段 {…}": "Peak {} · noise {} · stable {}",
    "未知": "Unknown",
    "已应用": "Applied",
    "未应用": "Not applied",
    "方案 · {…} · {…} · 增益 {…} · {…}":
        "Profile · {} · {} · gain {} · {}",
    "本次已应用": "Applied this session",
    "未校准": "Uncalibrated",
    "方案 · {…} · 增益 {…}": "Profile · {} · gain {}",
    "{…}/3 模块在线 · {…}": "{}/3 modules online · {}",
    "点「开始检测」；先松手采集噪声底":
        "Press Start capture; release the keys first to measure noise",
    "设备已断开；重新连接后点「再测一次」":
        "Device disconnected; reconnect and press Capture again",
    "还没有曲线。连接设备后点「开始检测」。":
        "No curves yet. Connect the device and press Start capture.",
    "校验：噪声 {…} + 5 ≤ {…} ≤ 峰值 {…} × 0.9 ✓":
        "Check: noise {} + 5 ≤ {} ≤ peak {} × 0.9 ✓",
    "本机校准": "Local calibration",
    "串口已连接": "Serial connected",
    "串口未连接": "Serial not connected",
    "多指验证：按和弦": "Multi-key check: press a chord",
    "请松手，正在采集噪声底…":
        "Release the keys; measuring the noise floor…",
    "已捕获 {…} 个键 · 松开后自动结束":
        "Captured {} keys · ends after release",
    "请按键…（可多键同时按）":
        "Press the keys… (several at once is fine)",
    "可能卡键": "Possible stuck key",
    "检测完成 · {…} 个键": "Capture complete · {} keys",
    "就绪": "Ready",
    "自动停止": "auto stop",
    " · 已应用": " · applied",
    " · 噪声 {…}": " · noise {}",
    " · 稳定段 {…}": " · stable {}",
    " · 可能卡键": " · possible stuck key",
    # -- library --------------------------------------------------------
    "可跟谱 {…} · 我的导入 {…} · 制作中 {…}":
        "Followable {} · imported {} · in progress {}",
    "已导入 {…} · 重复 {…} · 失败 {…}": "Imported {} · duplicates {} · failed {}",
    "收藏 / 取消收藏": "Favorite / unfavorite",
    "仅显示 · 不跟谱 · {…}": "Display only · no follow · {}",
    "未标注作曲": "Composer not listed",
    "课程规划": "Curriculum plan",
    "{…} · 内置样曲 · {…}": "{} · built-in sample · {}",
    "本地导入 · 仅显示 · 不跟谱 · 不上传":
        "Local import · display only · no follow · never uploaded",
    "本地导入 · 许可未核验 · 不上传":
        "Local import · license unverified · never uploaded",
    "许可 · {…}": "License · {}",
    "阶段 {…} {…}": "Stage {} {}",
    "曲谱库": "Library",
    "曲谱": "Library",
    "只把能解析的 MusicXML / MIDI 标为可跟随。导入只保存在本机，不上传。":
        "Only MusicXML / MIDI files that parse are marked followable. "
        "Imports stay on this machine.",
    "导入曲谱": "Import score",
    "查看制作中 →": "View in progress →",
    "查看制作中的曲目": "View pieces in progress",
    "筛选": "Filter",
    "搜索标题 / 作曲家 / 阶段": "Search title / composer / stage",
    "搜索曲谱": "Search scores",
    "刷新": "Refresh",
    "重新扫描曲谱文件夹": "Rescan the score folder",
    "刷新曲库": "Refresh library",
    "难度 · 全部": "Difficulty · all",
    "调性 · 全部": "Key · all",
    "类型 · 全部": "Type · all",
    "关闭": "Close",
    "· 解析失败 {…}": "· parse failed {}",
    "还没有可跟谱的曲目": "No followable pieces yet",
    "导入 MusicXML / MIDI，或切到「制作中」查看课程规划。":
        "Import MusicXML / MIDI, or switch to In progress to see the plan.",
    "新建歌单…": "New playlist…",
    "新建歌单": "New playlist",
    "歌单名称：": "Playlist name:",
    "曲谱标签": "Score tags",
    "标签（用逗号分隔，最多 8 个）：":
        "Tags (comma-separated, up to 8):",
    "曲谱 (*.musicxml *.mxl *.xml *.mid *.midi);;MusicXML (*.musicxml *.mxl *.xml);;MIDI (*.mid *.midi);;图片/PDF（仅显示） (*.png *.jpg *.jpeg *.bmp *.webp *.pdf);;所有文件 (*)":
        "Scores (*.musicxml *.mxl *.xml *.mid *.midi);;MusicXML "
        "(*.musicxml *.mxl *.xml);;MIDI (*.mid *.midi);;Images/PDF "
        "(display only) (*.png *.jpg *.jpeg *.bmp *.webp *.pdf);;All files (*)",
    "{…} · {…} 小节 · {…} s · {…} BPM · {…} 音 · {…}/{…}":
        "{} · {} bars · {} s · {} BPM · {} notes · {}/{}",
    "{…} · 打开时自动切换映射": "{} · switches the mapping when opened",
    "打开 ›": "Open ›",
    "标签": "Tags",
    "给这首曲谱加标签": "Tag this score",
    "歌单": "Playlists",
    "加入或移出歌单": "Add to or remove from a playlist",
    "移除": "Remove",
    "移除导入的{…}": "Remove imported {}",
    "只删除曲谱库里的副本，不影响源文件":
        "Deletes only the library copy; source files are untouched",
    "课程 · 未引用": "Course · not referenced",
    "课程 · 未用于课程": "Course · not used",
    "{…} 个音": "{} notes",
    "解析失败：{…}": "Parse failed: {}",
    "仅显示 · 不跟谱": "Display only · no follow",
    "阶段 {…} · {…}": "Stage {} · {}",
    "注意：{…}": "Note: {}",
    "筛选 · {…}": "Filter · {}",
    "在全部中搜索": "Search all",
    "没有匹配的曲目": "No matching pieces",
    "没有匹配「{…}」的曲目。试试更短的关键词，或清空搜索。":
        "No pieces match “{}”. Try a shorter keyword or clear the search.",
    "还没有收藏": "No favorites yet",
    "点曲谱卡右上角的 ☆ 收藏，之后会出现在这里。":
        "Press ☆ on a score card to favorite it; it will appear here.",
    "还没有最近打开": "Nothing opened recently",
    "打开一首可跟谱曲目后，这里会保留最近记录。":
        "Open a followable piece and it will be listed here.",
    "还没有导入": "Nothing imported yet",
    "MusicXML / MIDI 可跟随；图片/PDF 仅显示，只保存在本机。":
        "MusicXML / MIDI can be followed; images/PDFs are display-only and "
        "stay on this machine.",
    "没有制作中的曲目": "No pieces in progress",
    "所有课程曲目都已有可跟谱面。":
        "Every curriculum piece already has a followable score.",
    "歌单 · 全部": "Playlist · all",
    "已在曲库：{…}": "Already in the library: {}",
    "导入失败：{…} · {…}": "Import failed: {} · {}",
    "导入失败 · {…}：{…}": "Import failed · {}: {}",
    "已导入但无法解析：{…} · 请在「我的导入」移除":
        "Imported but could not parse: {} · remove it under Imported",
    "已导入 · {…}": "Imported · {}",
    "已在曲库 · {…}": "Already in the library · {}",
    "取消收藏": "Unfavorite",
    "收藏": "Favorite",
    "查看 ›": "View ›",
    "仅显示": "Display only",
    "失败：{…}": "Failed: {}",
    "只能移除导入的曲谱。": "Only imported scores can be removed.",
    "无法解析曲谱": "Could not parse the score",
    "未知原因": "Unknown reason",
    "可解析": "Parsable",
    "内置样曲": "Built-in sample",
    "本项目练习曲": "Project exercise",
    "公有领域": "Public domain",
    "本项目原创": "Original to this project",
    "可跟随": "Followable",
    "同源 MIDI 示例": "Matching MIDI",
    "曲库": "Library",
    "MusicXML · 可跟随": "MusicXML · Followable",
    "MusicXML · 可跟随\n{…}": "MusicXML · Followable\n{}",
    "{…} · 可跟随": "{} · Followable",
    "{…} · 可解析": "{} · Parsable",
    "{…} · 内置样曲 · {…}": "{} · built-in sample · {}",
    "{…} · 同源 MIDI 示例": "{} · matching MIDI",
    "课程 · {…}": "Course · {}",
    "{…} 个音": "{} notes",
    "{…} 小节": "{} bars",
    "{…} s": "{} s",
    "·  {…}": "·  {}",
    "{…}  {…}": "{}  {}",
    "已导入": "Imported",
    "已加入": "Added",
    "已移出": "Removed",
    "已收藏": "Favorited",
    "已取消收藏": "Unfavorited",
}

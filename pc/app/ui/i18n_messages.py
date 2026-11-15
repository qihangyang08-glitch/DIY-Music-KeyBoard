"""English catalogue for toasts, status messages and dialogs (A5).

Keys are the Chinese source string; a key containing ``{…}`` is a template
built from an f-string and the English value uses ``{}`` for the captured
values. Values interpolated into a message (song titles, device ports, file
names) stay as they are: they are data, not chrome.
"""

MESSAGES: dict[str, str] = {
    # -- calibration ----------------------------------------------------
    "已发送 32 组阈值，等待设备确认":
        "Sent 32 thresholds; waiting for the device to confirm",
    "校准方案已保存": "Calibration profile saved",
    "先结束本次检测再切换增益":
        "Stop this capture before changing gain",
    "串口未连接，无法切换增益": "Serial is not connected; cannot change gain",
    "先连接设备并确认 3 个模块在线":
        "Connect the device and confirm all 3 modules are online",
    "先应用阈值，再验证多指和弦":
        "Apply thresholds before testing a chord",
    "还没有采集到按键": "No keys captured yet",
    "串口未连接，阈值未发送":
        "Serial is not connected; thresholds were not sent",
    "还没有覆盖 32 个键；先继续校准或应用已有方案":
        "Not all 32 keys are covered; keep calibrating or apply an "
        "existing profile",
    "没有可写的校准文件路径": "No calibration file path to write",
    "阈值已应用到设备": "Thresholds applied to the device",
    "设备拒绝通道 {…} 的阈值":
        "The device rejected the threshold for channel {}",
    "串口未连接，无法开始校准":
        "Serial is not connected; cannot start calibration",
    "串口未连接，无法验证": "Serial is not connected; cannot verify",
    "键 {…}：{…}": "Key {}: {}",
    "增益已变化，已停止本次检测；请重新校准并应用":
        "Gain changed; this capture was stopped. Recalibrate and apply",
    "增益已变化，建议重新校准并重新应用":
        "Gain changed; recalibrate and apply again",
    "设备增益 {…} 与方案 {…} 不一致，建议重新校准":
        "Device gain {} does not match profile {}; recalibrate",
    "校准方案未应用 · 设备无应答":
        "Calibration profile not applied · the device did not reply",
    "设备未回报增益，已按方案应用；建议烧录新固件以校验增益":
        "The device did not report its gain, so the profile was applied "
        "anyway; flash the new firmware to check gain",
    "正在校验设备增益 · {…}…": "Checking device gain · {}…",
    "正在应用校准方案 · {…}…": "Applying calibration profile · {}…",
    "设备增益 {…} 与方案 {…} 不一致，未自动应用；请到校准页重新校准":
        "Device gain {} does not match profile {}; the profile was not "
        "applied. Recalibrate on the Calibration page",
    "方案 · 裸铜 · 多套方案在后续版本接入":
        "Profile · bare copper · multiple profiles are a later version",
    "模拟": "Simulated",
    "无": "None",
    # -- creation -------------------------------------------------------
    "已载入模板 · {…}": "Template loaded · {}",
    "已量化 {…} 个音 · 1/8": "Quantised {} notes · 1/8",
    "已撤销上一步音符编辑": "Undid the last note edit",
    "开始叠录 · 音轨 {…}": "Overdub started · track {}",
    "开始录音 · 音轨 {…}": "Recording started · track {}",
    "已新增 {…}": "Added {}",
    "开": "on",
    "关": "off",
    "音轨 {…} · 静音{…}": "Track {} · mute {}",
    "音轨 {…} · 独奏{…}": "Track {} · solo {}",
    "音轨 {…} · 音色叠加{…}": "Track {} · layer {}",
    "音轨 {…} · 键盘分区{…}": "Track {} · split {}",
    "音轨 {…} · 静音开": "Track {} · mute on",
    "音轨 {…} · 静音关": "Track {} · mute off",
    "音轨 {…} · 独奏开": "Track {} · solo on",
    "音轨 {…} · 独奏关": "Track {} · solo off",
    "音轨 {…} · 音色叠加开": "Track {} · layer on",
    "音轨 {…} · 音色叠加关": "Track {} · layer off",
    "音轨 {…} · 键盘分区开": "Track {} · split on",
    "音轨 {…} · 键盘分区关": "Track {} · split off",
    "循环 1–{…} 小节": "Loop bars 1–{}",
    "循环关": "Loop off",
    "已导出 MIDI · {…}": "MIDI exported · {}",
    "已保存 · {…}": "Saved · {}",
    "已载入 · {…}": "Loaded · {}",
    "学习项目中不能换模板 · 先返回学习页":
        "Cannot change the template in a study project · go back to Learn "
        "first",
    "这个模板还没做好 · 内容制作中":
        "This template is not ready · content in progress",
    "模板不可用 · 内容制作中": "Template unavailable · content in progress",
    "录音中不能量化 · 先按停止":
        "Cannot quantise while recording · stop first",
    "当前轨没有可量化的音符": "This track has no notes to quantise",
    "没有可撤销的编辑": "Nothing to undo",
    "混响 {…}%": "Reverb {}%",
    "先停止录音再回放": "Stop recording before playback",
    "已经在录音 · 先按停止": "Already recording · stop first",
    "已录制 {…} 个音": "Recorded {} notes",
    "本段没有录到音符": "No notes were recorded",
    "录音中不能新增音轨": "Cannot add a track while recording",
    "录音中不能改循环 · 先按停止":
        "Cannot change the loop while recording · stop first",
    "项目里还没有可导出的音符 · 先录一段或画一个音":
        "No notes to export · record a phrase or draw a note first",
    "还没有可载入的项目 · 先录一段并保存":
        "No saved project to load · record and save one first",
    "载入失败 · 文件不可读": "Load failed · the file is unreadable",
    "MIDI 导出失败：{…}": "MIDI export failed: {}",
    "保存失败：{…}": "Save failed: {}",
    # -- learning / library --------------------------------------------
    "这个练习还没做好 · 内容制作中":
        "This exercise is not ready · content in progress",
    "这个阶段还没有考核 · 内容制作中":
        "This stage has no exam yet · content in progress",
    "这个练习还没有可跟的谱 · 内容制作中":
        "This exercise has no followable score yet · content in progress",
    "这个项目模板还没做好 · 内容制作中":
        "This project template is not ready · content in progress",
    "项目模板不可用 · 内容制作中":
        "Project template unavailable · content in progress",
    "这个训练还没有生成器 · 内容制作中":
        "This drill has no generator yet · content in progress",
    "这个考核还没有生成器 · 内容制作中":
        "This exam has no generator yet · content in progress",
    "已加入": "Added to",
    "已移出": "Removed from",
    "{…}歌单「{…}」· {…}": "{} playlist “{}” · {}",
    "已加入歌单「{…}」· {…}": "Added to playlist “{}” · {}",
    "已移出歌单「{…}」· {…}": "Removed from playlist “{}” · {}",
    "已收藏 · {…}": "Added to favorites · {}",
    "已取消收藏 · {…}": "Removed from favorites · {}",
    "歌单名称为空或已达上限":
        "The playlist name is empty or the limit is reached",
    "标签已更新 · {…} · {…}": "Tags updated · {} · {}",
    "已清除标签 · {…}": "Tags cleared · {}",
    "已移除导入 · {…}": "Import removed · {}",
    "移除失败 · {…}": "Remove failed · {}",
    "曲库元数据保存失败：{…}": "Could not save library metadata: {}",
    "《{…}》仅显示 · 不进入跟弹判定":
        "“{}” is display-only · it is not used for follow",
    "《{…}》还在制作中 · 暂不可跟弹":
        "“{}” is still in progress · follow is unavailable",
    "解析失败 · {…}": "Parse failed · {}",
    "谱面载入失败：{…}": "Score load failed: {}",
    "谱面载入失败：无法解析文件（{…}）":
        "Score load failed: could not parse the file ({})",
    "移除导入": "Remove import",
    "删除导入的《{…}》？\n将删除本机副本 {…} 个文件，不影响源文件、内置曲目或当前练习。":
        "Remove the imported “{}”?\nThis deletes {} local copies. Source "
        "files, built-in pieces and the current practice are unaffected.",
    # -- perform / score / project -------------------------------------
    "仅显示 · {…}": "Display only · {}",
    "已载入 · {…}": "Loaded · {}",
    "谱面已不在 · 已刷新曲库":
        "The score is gone · the library was refreshed",
    "图片已不在 · 已刷新曲库":
        "The image is gone · the library was refreshed",
    "无法读取这张图片": "Could not read this image",
    "未找到内置示例谱 · 可拖入 MusicXML/MIDI":
        "Built-in sample score not found · drop a MusicXML/MIDI file",
    "图片/PDF 仅显示 · 不能进入跟弹":
        "Images/PDFs are display-only · they cannot be followed",
    "回到开头 · 重新练习": "Back to the start · practice again",
    "全部静音 · 所有正在响的音已停止":
        "All muted · every sounding note was stopped",
    "已恢复内容默认分区": "Restored the default split",
    "先点 A 和 B 设置循环范围": "Set A and B to define the loop range",
    "循环 {…}–{…} 小节 · 已开启": "Loop bars {}–{} · on",
    "这个范围没有音符，换一个小节":
        "There are no notes in this range; try another bar",
    "换窗口 · {…} · 第 {…}/{…} 段": "Window · {} · part {}/{}",
    "退出全屏": "Exit full screen",
    "全屏 · 按 F11 退出": "Full screen · press F11 to exit",
    "设备已连接 · {…}": "Device connected · {}",
    "设备断开 · {…}": "Device disconnected · {}",
    "已带入练习谱 · {…}{…} · 按 Space 听示范":
        "Practice score loaded · {}{} · press Space for the demo",
    "已打开项目 · {…}": "Project opened · {}",
    "分区点 · 键 {…} / {…} 之间 · 已按曲目保存":
        "Split point · between keys {} / {} · saved per piece",
    "循环起点 · 第 {…} 小节，再点 B 设终点":
        "Loop start · bar {}; click B to set the end",
    "映射 · {…} · {…}": "Mapping · {} · {}",
    "还差：{…}": "Still missing: {}",
    "录音请到创作页 · MIDI 导出在后续版本接入":
        "Record on the Create page · MIDI export is a later version",
    "图片谱不跟随 · 手动翻页":
        "Image scores do not follow · turn pages manually",
    "已载入图片谱": "Image score loaded",
    "正在解析 {…}…": "Parsing {}…",
    "暂不支持 {…}": "Not supported yet: {}",
    "项目播放中 · 空格暂停": "Project playing · Space pauses",
    "项目播放结束": "Project playback finished",
    "项目里还没有可播放的音符 · 先录一段或画一个音":
        "No notes to play · record a phrase or draw a note first",
    "项目播放已停止": "Project playback stopped",
    "播放中 · 示例播放头": "Playing · sample playhead",
    "已暂停": "Paused",
    "示范播放中 · 空格暂停": "Demo playing · Space pauses",
    "示范已暂停 · 轮到你按下一键":
        "Demo paused · press the next key yourself",
    "示范结束 · 按空格从头再听":
        "Demo finished · press Space to hear it again",
    # -- key bindings / dialogs ----------------------------------------
    "键位冲突": "Key conflict",
    "这个键已经绑定：": "This key is already bound:",
    "替换会清除上面的绑定。":
        "Replacing clears the bindings listed above.",
    "替换": "Replace",
    "取消": "Cancel",
    "恢复默认": "Restore defaults",
    "恢复三行顺序默认会覆盖当前所有键位，确定吗？":
        "Restoring the three-row defaults overwrites every current binding. "
        "Continue?",
    "已恢复：三行顺序默认键位。":
        "Restored: three-row default bindings.",
    "已导入：{…}": "Imported: {}",
    "已导出：{…}": "Exported: {}",
    "导入失败：{…}": "Import failed: {}",
    "导出失败：{…}": "Export failed: {}",
    "导入失败：文件格式不正确。": "Import failed: the file format is invalid.",
    "请再按一个字母 / 数字 / 符号键（单独的修饰键只能用于延音）。":
        "Press a letter, digit or symbol key (a modifier alone can only "
        "control sustain).",
    "音符键暂不支持 Ctrl / Alt / Win 组合；请重按，或 Esc 取消。":
        "Note keys do not support Ctrl / Alt / Win combinations; press "
        "again, or Esc to cancel.",
    "⚠ {…} 个冲突": "⚠ {} conflicts",
    "无冲突": "No conflicts",
    "请按下要绑定的键…（Esc 取消） · 目标：{…}":
        "Press the key to bind… (Esc cancels) · target: {}",
    "已清除光条 {…} 的电脑键；仍可用实体琴弹。":
        "Cleared the computer key for bar {}; the physical keyboard still "
        "plays it.",
    "已清除功能“{…}”的按键。": "Cleared the key for “{}”.",
    # -- shell ----------------------------------------------------------
    "语言将在下次启动生效 · Language changes on next start":
        "Language changes on next start",
    "已离开键位页；未保存这次改绑。":
        "Left the key-bindings page; this rebind was not saved.",
    "训练中锁定音域（C4–G6）": "Drills lock the range (C4–G6)",
    "鼓垫模式 · 不参与判定": "Drum pad mode · not judged",
    "固件协议 v{…} · 建议烧录新固件（自适应与 NVS）":
        "Firmware protocol v{} · flash the new firmware (adaptive + NVS)",
    "键 {…} 卡住 · 已自动释放":
        "Key {} stuck · released automatically",
}

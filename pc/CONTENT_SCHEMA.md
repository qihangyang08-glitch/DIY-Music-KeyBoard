# KeyBorad 内容与数据格式（设计稿）

> **状态：设计，2026-11-01。** 本文定义课程、曲目、键位、进度、项目与许可清单的
> 数据形状，供后续实现使用。字段名可按实现调整，但**语义与必填项不应丢失**。
>
> 配套：[UI_DESIGN_V3.md](UI_DESIGN_V3.md)、[TEACHING_CURRICULUM.md](TEACHING_CURRICULUM.md)、
> [CONTENT_PIPELINE.md](CONTENT_PIPELINE.md)、[RELEASE_POLICY.md](RELEASE_POLICY.md)、
> [RESOURCES.md](RESOURCES.md)。

---

## 1. 目录布局

```
pc/
  resources/                      # 只读，随安装包/版本发布
    curriculum/
      stages/                     # s0.json … s8.json
      lessons/                    # s0-l1.json …
      drills/                     # d0-01.json …
      pieces/                     # p3-01.json …
    scores/
      musicxml/                   # p3-01.musicxml / .mxl
      midi/                       # 示范/伴奏（可选）
      images/                     # 图片谱（可选）
    i18n/
      zh-CN.json
      en.json
    keymaps/
      default.json
      left-right.json
      white-keys.json
    licenses/
      manifest.json
      texts/                      # 许可全文（如需要）
  user-data/                      # 运行时写入（示例；实际用 %APPDATA%）
    progress.json
    keybindings.json
    projects/
    profiles/
```

- **内置内容只读**：升级覆盖；用户不能直接改；可复制到用户库再编辑。
- **用户数据可写**：进度、键位、项目、校准/演奏方案；可导入导出。
- **路径**：由 `QStandardPaths.AppConfigLocation` 决定（Windows 上是本地应用数据区，
  不等于 Roaming `%APPDATA%`）；便携模式可放程序目录 `user-data/`。
- **资源清单**：每个内置文件在 `licenses/manifest.json` 有记录；无记录不得打包。

---

## 2. ID 约定

> 所有内容类型（stage/lesson/drill/piece/project）都带
> `visibility / public_release / readiness`；示例中为简洁只在部分条目展开。


| 类型 | 格式 | 示例 |
|---|---|---|
| 阶段 | `s0` … `s8` | `s3` |
| 课程 | `s{stage}-l{n}` | `s3-l1` |
| 训练 | `d{stage}-{nn}` | `d3-04` |
| 曲目 | `p{stage}-{nn}` | `p3-01` |
| 项目 | `p7-01` / `p8-01` | `p8-03` |
| 内容块 | `{owner}-b{n}` | `s3-l1-b2` |
| 音轨 | `track-{n}` | `track-1` |
| 方案 | `kb-{slug}` | `kb-default` |

- ID 稳定；改名不改 ID；删除用 `deprecated: true`，不直接复用。
- 正文表格为便于阅读可能写作 `P3-01` / `D3-04`；机器数据统一小写 `p3-01` / `d3-04`。
- 进度以 ID 为键；内容升级不能丢用户进度。

---

## 3. 阶段 `stage`

```json
{
  "schema_version": 1,
  "id": "s3",
  "index": 3,
  "title": "右手旋律",
  "group": "演奏",
  "goal": "在 C 大调五指位置和 C 大调音阶内弹简单旋律，能看谱、跟提示、连贯。",
  "prerequisites": ["s1", "s2"],
  "estimated_days": "2-3 周",
  "lessons": ["s3-l1", "s3-l2", "s3-l3", "s3-l4", "s3-l5", "s3-l6", "s3-l7", "s3-l8"],
  "drills": ["d3-01", "...", "d3-18"],
  "pieces": ["p3-01", "...", "p3-15"],
  "assessment": {
    "summary": "任选 8 首右手曲，音准 ≥ 90%，速度 ≥ 70%。",
    "criteria": [
      {"metric": "note_accuracy", "min": 0.90},
      {"metric": "tempo_ratio", "min": 0.70},
      {"metric": "completion", "min": 1.0}
    ]
  },
  "next": "s4",
  "tags": ["右手", "旋律", "C大调"],
  "status": "planned"
}
```

必填：`id,index,title,group,goal,prerequisites,lessons,drills,pieces,assessment,next,status`。
`status`: `planned | drafting | review | ready | deprecated`。

---

## 4. 课程 `lesson`

```json
{
  "schema_version": 1,
  "id": "s3-l1",
  "stage": "s3",
  "index": 1,
  "title": "五指位置 C",
  "objectives": [
    "认识 1–5 指对应的 C–G",
    "在光条上找到 C4–G4",
    "用连奏弹 4 小节五指练习"
  ],
  "prerequisites": ["s0", "s1", "s2"],
  "duration_min": 15,
  "blocks": [
    {"id": "s3-l1-b1", "type": "text", "title": "五指位置是什么", "body": "……"},
    {"id": "s3-l1-b2", "type": "staff", "score": "scores/musicxml/s3-l1-fivefinger.musicxml",
     "caption": "C 五指位置：C4–G4", "alt": "五线谱：C4 到 G4 的五个音"},
    {"id": "s3-l1-b3", "type": "demo", "score": "s3-l1-fivefinger", "tempo": 60,
     "mapping": {"preset": "cmajor", "base": 60}, "caption": "听示范"},
    {"id": "s3-l1-b4", "type": "steps", "title": "练习步骤", "items": [
      "慢速 50%，右手 4 小节",
      "循环第 1–2 小节",
      "原速 80%，不停顿"
    ]}
  ],
  "drills": ["d3-01", "d3-02", "d3-03"],
  "pieces": [],
  "check": [
    {"question": "C4–G4 在光条上的位置？", "type": "self"},
    {"question": "连续弹 4 小节，音准 ≥ 90%", "type": "metric", "metric": "note_accuracy", "min": 0.90}
  ],
  "next": "s3-l2",
  "tags": ["五指", "C大调"],
  "status": "planned"
}
```

内容块类型：

| type | 字段 | 用途 |
|---|---|---|
| `text` | `title, body` | 知识卡 |
| `image` | `src, alt, caption` | 图示/照片 |
| `staff` | `score, caption, alt` | 五线谱片段 |
| `roll` | `score, caption, alt` | 落键片段 |
| `demo` | `caption`（`score/tempo` 可留作元数据） | 指导书的文字示范要点；**不播放音频/自动演奏**（2026-11-10 决策；演奏页曲谱示范不受影响） |
| `steps` | `title, items[]` | 练习步骤 |
| `compare` | `items[]` | 对错/版本对比 |
| `glossary` | `terms[]` | 术语卡 |
| `quiz` | `questions[]` | 识谱/节奏小测 |
| `checklist` | `items[]` | 自检清单 |

- `body` 支持简单 Markdown 子集（段落、粗体、列表）；不执行 HTML/脚本。
- 图片必须有 `alt`（无障碍）；音频优先由曲谱生成，不打包外部录音。
- **视觉块渲染（P2-G G4b，2026-11-10）**：`image` 按绝对路径、
  `resources/<src>` 或 `resources/images/<文件名>` 解析；`staff`/`roll`
  按裸 id、文件名或 `resources/scores/...` 解析，解析后只渲染**前 4 小节**，
  静态显示，不播放。缺素材时页面显示「谱例/图示未找到 · 标题」，
  不显示原始路径；`alt` 在图下以小字保留并写入无障碍名称。
- 所有文本默认 `zh-CN`；可选 `body_en`/`title_en`，英文不是必需。
- **运行时扩展（P2-G，2026-11-10）**：`mistakes[]`（常见错误）、
  `practice`（绑定阶段内 `PracticeItem.name`）、`visibility` /
  `public_release`（公开版过滤）。实现见 `app/core/lesson.py`。
- `status = ready` 的运行时门槛：有 `objectives`、至少一张有正文的知识卡、
  `steps`、`check`；缺一项回退为 `planned`，界面显示占位。

---

## 5. 训练 `drill`

```json
{
  "schema_version": 1,
  "id": "d3-04",
  "stage": "s3",
  "title": "C 大调音阶 1 八度",
  "kind": "exercise",
  "goal": "上下行连贯，手指不塌，速度 60–80。",
  "hands": "RH",
  "tempo": {"start": 60, "target": 80},
  "bars": 4,
  "concepts": ["音阶", "连奏", "五指"],
  "mapping": {
    "preset": "cmajor",
    "base": 60,
    "split": null,
    "octave": 0,
    "transpose": 0
  },
  "score": {
    "musicxml": "scores/musicxml/d3-04.musicxml",
    "midi": "scores/midi/d3-04.mid",
    "parseable": true
  },
  "next_key": "derived",
  "assessment": {"metric": "note_accuracy", "min": 0.9},
  "visibility": "public",
  "public_release": "allowed",
  "public_alternative": null,
  "readiness": "encoded",
  "tags": ["音阶", "右手"],
  "status": "planned"
}
```

- `kind`: `exercise | reading | rhythm | coordination | project`。
- 谱面训练（`exercise` / 部分 `reading`/`rhythm`）必须有 MusicXML + MIDI；
  生成式训练（点选/拍击）必须给 `generator` 规格（题型、音域、节奏、答案、判定），
  不需要 MusicXML，但仍然是结构化、可解析的内容。
- `reading`/`rhythm` 可没有 MusicXML，用生成题目；但仍需 `goal`/`assessment`。
- `hands`: `LH | RH | both`。
- `next_key`: `derived` 表示由谱面 + 映射自动算；也可给显式光条序列（用于特殊练习）。
- 训练不要求完整编曲；1–8 小节为主。

---

## 6. 曲目 `piece`

```json
{
  "schema_version": 1,
  "id": "p3-01",
  "stage": "s3",
  "title": "小星星",
  "title_en": "Twinkle, Twinkle, Little Star",
  "composer": "传统曲调",
  "source": {
    "type": "traditional",
    "url": "https://example.org/specific-source-page",
    "edition": "本项目简易编配",
    "format": "original",
    "conversion": "MuseScore 录入/编配，导出 MusicXML + MIDI",
    "verified_at": "2026-11-01"
  },
  "license": {
    "spdx": "LicenseRef-PublicDomain",
    "attribution": "旋律：传统/公有领域；编配：本项目",
    "url": null,
    "territory": "world"
  },
  "difficulty": 1,
  "key": "C major",
  "range": {"low": "C4", "high": "A4", "midi_low": 60, "midi_high": 69},
  "hands": "RH",
  "mapping": {
    "preset": "cmajor",
    "base": 60,
    "split": null,
    "octave": 0,
    "transpose": 0
  },
  "tempo": {"practice": 60, "target": 80},
  "duration_bars": 8,
  "concepts": ["四分/二分", "级进", "乐句"],
  "score": {
    "musicxml": "scores/musicxml/p3-01.musicxml",
    "midi": "scores/midi/p3-01.mid",
    "image": null,
    "follow": true,
    "parseable": true
  },
  "demo": {"midi": "scores/midi/p3-01-demo.mid", "instrument": "piano"},
  "visibility": "public",
  "public_release": "allowed",
  "public_alternative": null,
  "readiness": "encoded",
  "replacement_for": null,
  "teaching_notes": [
    "第 3 小节注意两个相同音的时值。",
    "先唱再弹；循环 1–2 小节。"
  ],
  "assessment": {
    "metrics": ["note_accuracy", "completion"],
    "pass": {"note_accuracy": 0.9, "tempo_ratio": 0.7}
  },
  "tags": ["儿歌", "右手", "C大调"],
  "status": "planned"
}
```

必填（核心谱面内容）：`id,stage,title,source,license,difficulty,key,range,hands,mapping,tempo,score,visibility,public_release,readiness`。

`score.musicxml` 与 `score.midi` 对核心曲目**必填**；`score.image` 只能补充，不能替代。
`score.parseable` 必须为 `true`，`score.follow` 必须为 `true`（图片谱为 `false` 且不得进入核心课程）。

- `license.spdx`: `LicenseRef-PublicDomain | CC0-1.0 | CC-BY-4.0 | CC-BY-SA-4.0 | CC-BY-NC-4.0 | LicenseRef-Original | PersonalUseOnly | Unknown | ...`
  （SPDX 标识符；`LicenseRef-Original` 表示本项目原创/编配）。
- 非原创必须给 `source.url` 与 `license.url`（若许可有页面）。
- `range` 用 MIDI 数值 + 音名；软硬件都检查。
- `mapping.split`: `null` 或 `{"bar": 16, "left": {...}, "right": {...}}`。
- `score` 可以是 MusicXML/MIDI/图片；图片谱必须 `follow: false`。
- `demo` 可以是 MIDI；不打包外部录音，除非许可明确。
- `next_key` 可由谱面 + 映射自动生成；若显式给出，作为覆盖。
- `status`: `planned | drafting | licensed | arranged | ready | deprecated`（编辑状态）。
- `readiness`: `planned | sourced | encoded | validated | ready | deprecated`（机器可读/可练状态）。
- `visibility`: `public | private`；`public_release`: `allowed | remove | replace | unknown`；
  `public_alternative`: 替换 ID 或 null；详见 [RELEASE_POLICY.md](RELEASE_POLICY.md)。
- `source.format`: `musicxml | midi | lilypond | pdf | omr | original`；
  `source.conversion`: 转写/导出方式（如 "MuseScore 导出"、"Audiveris OMR + 人工修正"）。
- 核心内容不得只有 PDF/图片；`score.image` 只做补充显示。
- `visibility`/`public_release` 缺失视为 `private` + `unknown`，公开构建拒绝。

### 5.1 生成式训练规格（无 MusicXML）

```json
{
  "schema_version": 1,
  "id": "d1-01",
  "stage": "s1",
  "title": "高音谱号线/间音名",
  "kind": "reading",
  "format": "generated",
  "generator": {
    "type": "note_naming",
    "clef": "treble",
    "range": {"low": "C4", "high": "C5"},
    "count": 10,
    "show": "staff",
    "answer": "bar_mapping"
  },
  "assessment": {"metric": "note_accuracy", "min": 0.8},
  "visibility": "public",
  "public_release": "allowed",
  "readiness": "ready"
}
```

- 生成式训练仍需要 `id/stage/title/kind/generator/assessment/visibility/public_release/readiness`。
- `generator` 定义题型、音域、数量、显示方式、答案来源；UI 与判定共用同一份规格。
- 不需要 MusicXML，但必须可复现、可判定、可统计。

### 6.1 映射 `mapping`

```json
{
  "preset": "custom",
  "base": 48,
  "steps": [0, 2, 4, 5, 7, 9, 11],
  "octave": 0,
  "transpose": 0,
  "split": {
    "bar": 16,
    "left":  {"preset": "custom", "base": 48, "steps": [0,2,4,5,7,9,11]},
    "right": {"preset": "custom", "base": 60, "steps": [0,2,4,5,7,9,11]}
  }
}
```

- 解析后必须得到 32 个 MIDI 音（可越界但标红/禁用）。
- `preset` 可为 `chromatic | cmajor | aminor | pentatonic | custom`。
- `steps` 为音阶半音模板；`base` 为键 1 的 MIDI。
- 左右手分区只改变音域/颜色，不改变光条顺序。
- 若曲目有 `mapping`，打开时自动套用；用户可临时改，但不写回内置曲目。
- **实现备注（2026-11-09，H7f）：** `PracticeItem.mapping` 现在接受预设
  key（如 `"split"`）或结构化 `MappingSpec`（`base/steps/octave/
  transpose/split`，容错钳制）。预设 key 套用时八度/移调归零；结构化
  spec 可用自己的偏移。退出练习时恢复用户的预设/八度/移调/自动跟随。
  曲库卡片按文件 stem 反查课程声明（`curriculum.mapping_for_score`），
  直接打开宽音域曲也会套用；导入文件不继承内置声明。用户拖拽的分区点
  保存在用户级 `score_prefs.json`，不写回内容文件。

### 6.2 下一键 `next_key`

```json
{
  "derived": false,
  "events": [
    {"bar": 1, "start_beat": 0.0, "midi": 60, "bar_index": 1, "hand": "RH"},
    {"bar": 2, "start_beat": 1.0, "midi": 62, "bar_index": 2, "hand": "RH"}
  ]
}
```

- `derived: true` 时由谱面/映射生成；显式时用于特殊练习（只练某几个键）。
- 每个事件有 `bar`（光条 1–32）、`start_beat`、`midi`、`hand`。
- 提示带/谱面高亮共用；不要两套数据。

---

## 7. 学习进度 `progress`

```json
{
  "schema_version": 1,
  "profile_id": "default",
  "created_at": "2026-11-01T10:00:00+08:00",
  "updated_at": "2026-11-01T10:30:00+08:00",
  "current": {"stage": "s3", "lesson": "s3-l2", "piece": "p3-04", "bar": 5},
  "stages": {
    "s3": {"status": "in_progress", "started_at": "...", "completed_at": null}
  },
  "lessons": {
    "s3-l1": {"status": "completed", "best": {"accuracy": 0.94}, "attempts": 3}
  },
  "drills": {
    "d3-04": {"status": "in_progress", "best_tempo": 72, "best_accuracy": 0.88}
  },
  "pieces": {
    "p3-01": {
      "status": "completed",
      "best": {"accuracy": 0.96, "tempo_ratio": 0.8, "completion": 1.0},
      "attempts": 5,
      "last_played": "2026-11-01T10:20:00+08:00",
      "practice_seconds": 640
    }
  },
  "daily": [
    {"date": "2026-11-01", "seconds": 900, "items": ["d3-04", "p3-01"]}
  ],
  "notes": [],
  "settings": {
    "strict_timing": false,
    "show_note_names": true,
    "auto_accompaniment": true
  }
}
```

- 状态：`not_started | in_progress | completed | skipped`。
- 只存本地；导出/导入 JSON；不存个人身份信息。
- 尝试记录可另存 `attempts/`，避免 progress 文件无限增长；保留最近 20 次/曲目。
- 内容升级以 ID 合并；缺失 ID 标 `deprecated`，进度保留。

---

## 8. 键位方案 `keybindings`

```json
{
  "schema_version": 1,
  "id": "kb-default",
  "name": "三行顺序",
  "layout": "three-row",
  "notes": {
    "1": "Z", "2": "X", "3": "C", "4": "V", "5": "B",
    "6": "N", "7": "M", "8": ",", "9": ".", "10": "/",
    "11": "A", "12": "S", "13": "D", "14": "F", "15": "G",
    "16": "H", "17": "J", "18": "K", "19": "L", "20": ";",
    "21": "'", "22": "Q", "23": "W", "24": "E", "25": "R",
    "26": "T", "27": "Y", "28": "U", "29": "I", "30": "O",
    "31": "P", "32": "["
  },
  "functions": {
    "play_pause": "Space",
    "panic": "Esc",
    "sustain_hold": "Shift",
    "toggle_labels": "Tab",
    "help": "F1",
    "page_perform": "Ctrl+1",
    "page_learn": "Ctrl+2",
    "page_scores": "Ctrl+3",
    "page_create": "Ctrl+4",
    "page_device": "Ctrl+5",
    "page_settings": "Ctrl+6",
    "record": "Ctrl+R",
    "loop": "Ctrl+L",
    "metronome": "Ctrl+T",
    "next_mapping": "Ctrl+M",
    "next_instrument": "Ctrl+P",
    "octave_down": "Ctrl+[",
    "octave_up": "Ctrl+]",
    "transpose_down": "Ctrl+-",
    "transpose_up": "Ctrl+=",
    "tempo_down": "Ctrl+Down",
    "tempo_up": "Ctrl+Up",
    "fullscreen": "F11"
  },
  "conflicts": [],
  "created_at": "2026-11-01",
  "notes": "物理键码；键帽显示随系统布局。"
}
```

- `notes` 的键是光条编号（字符串），值是物理键码/键帽标识；实现可存 scan code。
- `functions` 的值是单键或修饰键组合；按住型动作用 `_hold` 后缀。
- `conflicts` 由校验器生成；保存时为空或显式确认。
- 允许多套方案；`id` 稳定；导入时重命名冲突。
- 实体琴 4 个功能键的用途另存 `pad_functions`（1–4 → action）。

---

## 9. 创作项目 `project`

```json
{
  "schema_version": 1,
  "id": "proj-demo",
  "title": "我的第一首",
  "created_at": "2026-11-01T11:00:00+08:00",
  "tempo": 84,
  "time_signature": "4/4",
  "length_bars": 16,
  "loop": {"start": 1, "end": 8, "enabled": false},
  "tracks": [
    {
      "id": "track-1",
      "name": "右手旋律",
      "instrument": {"program": 0, "name": "Piano 1"},
      "volume": 0.8,
      "pan": 0.0,
      "reverb": 0.15,
      "chorus": 0.0,
      "mute": false,
      "solo": false,
      "layer": null,
      "notes": [
        {"start": 0.0, "duration": 1.0, "midi": 60, "velocity": 100}
      ]
    },
    {
      "id": "track-2",
      "name": "左手低音",
      "instrument": {"program": 32, "name": "Acoustic Bass"},
      "volume": 0.7,
      "pan": 0.0,
      "reverb": 0.1,
      "chorus": 0.0,
      "mute": false,
      "solo": false,
      "layer": null,
      "notes": []
    }
  ],
  "master": {"volume": 0.8, "reverb": 0.2, "chorus": 0.0},
  "mapping": {"preset": "cmajor", "base": 48, "octave": 0, "transpose": 0},
  "license": {"spdx": "LicenseRef-Original", "attribution": "本项目"},
  "visibility": "public",
  "public_release": "allowed",
  "public_alternative": null,
  "readiness": "encoded",
  "export": {"midi": "exports/proj-demo.mid", "json": "projects/proj-demo.json"}
}
```

- 音符时间单位：拍（quarter note = 1.0），或统一用 tick；文档选定一种，实现不变。
- 固定 velocity 100；不记录压力。
- `layer`: `null` 或 `{"program": 40, "volume": 0.4, "name": "Strings"}`。
- 分区（split）可作为 project 级设置：`split: {"bar": 16, "left": {...}, "right": {...}}`。
- 录音事件与手动编辑共用 `notes`；不需要区分来源，可加 `source: "recorded" | "edited"`。
- 导出 MIDI 时按 track 分轨；WAV 后续。

---

## 10. 许可清单 `licenses/manifest.json`

```json
{
  "schema_version": 1,
  "generated_at": "2026-11-01",
  "items": [
    {
      "content_id": "p3-01",
      "title": "小星星（右手）",
      "composer": "传统曲调",
      "source_url": "https://imslp.org/",
      "source_edition": "本项目简易编配",
      "license": "LicenseRef-PublicDomain",
      "license_url": null,
      "source_format": "original",
      "attribution": "旋律：传统/公有领域；编配：KeyBorad 项目",
      "modifications": "简化、移调、32 键编配、加左右手标注",
      "visibility": "public",
      "public_release": "allowed",
      "readiness": "ready",
      "territory": "world",
      "verified_by": "content-review",
      "verified_at": "2026-11-01"
    }
  ]
}
```

> 示例中的 `source_url` 只是占位；入库时必须写具体作品/版本页面，不能只写站点首页。

- 没有清单条目的内容，打包脚本应报错。
- `license` 用 SPDX 或 `LicenseRef-Original`。
- `modifications` 必须写；编配/简化/移调都算。
- `territory` 与 `source_edition` 用于版权解释。
- 许可全文放 `licenses/texts/`；关于页显示开源组件与致谢。
- 公开版的 `public_exclusions.json` 与构建剔除规则见 [RELEASE_POLICY.md](RELEASE_POLICY.md)；
  私有内容放 `resources/private/`，不得进入公开包。

---

## 11. 校验规则

### 11.1 内容

- [ ] `id` 唯一、稳定；`stage` 存在；引用存在。
- [ ] 每首曲目 `license` 有值；非原创有 `source_url`；清单有条目。
- [ ] 核心谱面曲目/训练有 `score.musicxml` + `score.midi`，`parseable=true`；
      只有 PDF/图片的内容不得标记为核心；`score.follow` 必须为 true。
- [ ] `visibility` / `public_release` 有值；公开构建不引用 private/remove 内容；
      replace 项有 `public_alternative`。
- [ ] `range.midi_low/high` 在 0–127；映射后每键可解析。
- [ ] `mapping.split.bar` 在 1–32；左右区不重叠、不越界。
- [ ] `tempo` 在 30–200；`duration_bars` > 0；`difficulty` 1–5。
- [ ] 音符时值 > 0；不重叠同一轨同一音（允许但标记）。
- [ ] `hands` 与谱面声部一致；左右手标注完整。
- [ ] `next_key` 可由谱面生成或显式有效；序列与谱面事件一致。
- [ ] MusicXML 可解析；调号/拍号/反复/跳房子正确；小节总时值正确。
- [ ] 生成式训练有 generator/answer/判定规格；不是只有一段说明文字。
- [ ] `readiness` 为 `validated`/`ready` 才能出现在核心学习路径；
      `planned`/`encoded` 只显示“制作中”。
- [ ] 曲目在 32 键上可弹；超范围有简化/移调说明。
- [ ] 文本中文；图片有 alt；不含歌词/版权不明素材。
- [ ] 示范音频由 MIDI/合成生成，或许可明确。

### 11.2 键位

- [ ] 32 个音符槽无重复、无缺失（允许显式未绑定并标记）。
- [ ] 功能动作无重复绑定；冲突列表为空或已确认。
- [ ] 不使用系统保留键；修饰键组合合法。
- [ ] 导入方案时检测冲突；不静默覆盖。
- [ ] 键位方案与内容/项目分开存储；升级不丢。

### 11.3 项目/进度

- [ ] 音轨数 ≤ 8；每轨音色有效；音量/声像范围。
- [ ] 音符时间在 `length_bars` 内；导出 MIDI 合法。
- [ ] 进度引用存在的 ID；缺失标 deprecated，不删除用户记录。
- [ ] 时间戳带时区；文件可迁移。

---

## 12. 版本与迁移

- 每个文件有 `schema_version`；不兼容变更升版本。
- 内容有 `content_version`（资源清单）；用户进度按 ID 合并。
- 迁移脚本：读旧版本 → 新字段默认值 → 备份 → 写新版本。
- 内置内容升级不覆盖用户导入/笔记；用户可复制内置曲目到"我的导入"再改。
- 项目/键位/进度导出带版本；导入时提示升级。

---

## 13. 示例：阶段 3 第 1 课 + 小星星

`lessons/s3-l1.json`（节选）：

```json
{
  "schema_version": 1,
  "id": "s3-l1",
  "stage": "s3",
  "index": 1,
  "title": "五指位置 C",
  "objectives": ["认识 C–G 五个音", "用连奏弹 4 小节"],
  "blocks": [
    {"id": "s3-l1-b1", "type": "text", "title": "五指位置", "body": "把手放在 C–G 五个音上……"},
    {"id": "s3-l1-b2", "type": "staff", "score": "s3-l1-fivefinger", "caption": "C4–G4"},
    {"id": "s3-l1-b3", "type": "demo", "score": "s3-l1-fivefinger", "tempo": 60,
     "mapping": {"preset": "cmajor", "base": 60}},
    {"id": "s3-l1-b4", "type": "steps", "title": "练习", "items": ["慢速 50%", "循环 1–2 小节", "原速 80%"]}
  ],
  "drills": ["d3-01", "d3-02"],
  "pieces": ["p3-01"],
  "next": "s3-l2"
}
```

`pieces/p3-01.json`（完整见 §6）：

- 音域 C4–A4，右手，C 大调，8 小节，难度 1。
- 映射 C 大调 base 60；光条 1–10 对应 C4–A4。
- 概念：四分/二分、级进、乐句。
- 许可：旋律传统/PD；编配本项目；清单记录。

---

## 14. 存储与隐私

- 只存本地；不上传；不需要账号。
- 学习进度、录音项目、键位、校准方案可导出 JSON；导出文件包含用户演奏数据
  （不含身份信息）。
- 日志默认不记录按键内容；如需诊断，用户主动开启，且可清理。
- 删除/重置：设置 → 数据 → 清除，二次确认；先备份。
- 曲谱导入的版权归用户；软件不重新分发用户导入内容。

---

## 15. 实现顺序建议

1. 先定 `mapping`/`piece`/`next_key`（谱面与提示的地基）。
2. 再做 `keybindings` + `InputHub`（零鼠标演奏）。
3. 再做 `progress` + `lesson`（学习页/练习页）。
4. 再做 `project`（创作）。
5. 最后补 `licenses` 清单与打包校验。

> 字段可以按实现调整；但**不要省略许可、映射、左右手、下一键、进度 ID**，
> 这几项一旦后期补，会牵连内容、UI 和用户数据。

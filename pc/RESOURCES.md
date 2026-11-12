# KeyBorad 教学内容资源与许可清单

> **用途**：为 [TEACHING_CURRICULUM.md](TEACHING_CURRICULUM.md) 提供可用的外部教程、
> 曲谱库、方法书、开源工具与许可说明。
>
> **状态**：2026-11-01 检索整理。链接、许可、可访问性会变化；**正式打包前逐项复核**。
> 本清单不是法律意见；涉及发行/商用时应请专业人士确认。
>
> **原则**：
> - **公开版**只用原创/编配、公共领域（PD）、CC0 或明确允许再分发的许可。
> - **私有版（你个人使用）**可以纳入你能合法访问的教材/曲谱/录音；但每个条目
>   记录来源、许可、`visibility`、`public_release`，将来公开版按清单剔除/替换。
> - **核心课程**必须能被软件解析：MusicXML/MIDI 或生成式 JSON 规格；
>   PDF/图片只能做补充显示，不作为主练习。
> - 详见 [RELEASE_POLICY.md](RELEASE_POLICY.md) 与 [CONTENT_PIPELINE.md](CONTENT_PIPELINE.md)。

---

## 1. 资源分级

| 级别 | 说明 | 私有版 | 公开版 | 格式要求 |
|---|---|---|---|---|
| **A. 原创/编配** | 本项目撰写、编配、绘制 | ✅ | ✅ | MusicXML/MIDI/JSON |
| **B. 公共领域 PD** | 作品/版本在目标地区进入公有领域 | ✅ | ✅ 核对后 | MusicXML/MIDI |
| **C. CC0** | 放弃版权，可自由使用 | ✅ | ✅（建议署名） | MusicXML/MIDI |
| **D. CC BY / CC BY-SA** | 需署名；SA 还要求衍生同许可 | ✅ | ⚠️ 按许可合规 | MusicXML/MIDI |
| **E. CC BY-NC** | 禁止商业使用 | ✅ 个人 | ❌ | 仅私有/链接 |
| **F. 版权保留/不明** | 现代教材、流行曲、扫描版、改编版 | ✅ 个人合法访问 | ❌ | 仅私有/链接；核心需转写 |
| **G. 订阅/DRM** | 按站点条款个人使用 | 按条款 | ❌ | 仅私有；不绕过限制 |

> **核心课程格式**：59 首曲目 + 62 条谱面训练 = MusicXML + MIDI；
> 54 条生成训练 = JSON 规格；8 个项目 = Project JSON + MIDI。
> PDF/图片只在"仅显示"位置；不能支撑跟谱/下一键/判定。

---

## 2. 乐理与识谱教程（外部参考）

| 资源 | 语言 | 许可/使用 | 适合 | 链接 |
|---|---|---|---|---|
| **Open Music Theory v2** | 英文 | **CC BY-SA 4.0**；可改编需署名+同许可 | 系统乐理；取基础章节作参考 | <https://viva.pressbooks.pub/openmusictheory/> |
| **musictheory.net** | 英文 | 免费课程/练习；版权保留 | 音符、音程、调号、和弦、练耳 | <https://www.musictheory.net/lessons> |
| **Musicca** | 简/繁中文等 | 免费；账号可选；版权保留 | 零基础互动练习、虚拟钢琴、节拍器 | <https://www.musicca.com/zh> |
| **Ableton Learning Music** | 英文 | 免费互动；版权保留 | 节奏/旋律/和声/结构的动手入门 | <https://learningmusic.ableton.com/> |
| **维基教科书《乐理与作曲》** | 中文 | **CC BY-SA**；可改编需署名+同许可 | 中文基础乐理/五线谱/简谱 | <https://zh.wikibooks.org/zh/樂理與作曲> |
| **Fundamentals of Music Theory**（Edinburgh） | 英文 | **CC BY-NC-SA**；禁止商业使用 | 五线谱/音阶/音程/节奏/和弦 | <https://open.umn.edu/opentextbooks/textbooks/1101> |
| **teoria.com** | 多语言 | 免费练习；版权保留 | 音程/调号/和弦/练耳 | <https://www.teoria.com/> |
| **Khan Academy – Music** | 英文 | 免费；版权保留 | 基础概念/音乐史 | <https://www.khanacademy.org/humanities/music> |

**用法建议**

- 内置课程的中文讲解由本项目重写，不整段复制 OMT/维基教科书。
- 若直接改编 CC BY-SA 内容，内置课程需标注来源、作者、许可，并以 CC BY-SA 分发该部分。
- CC BY-NC 内容（Edinburgh）**不进入发行包**；只作为“延伸阅读”链接。
- musictheory.net / Musicca / Ableton 的练习很好，但版权保留；只链接，不抓取题目/界面。

---

## 3. 公共领域曲谱库

| 资源 | 内容 | 许可/注意 | 适合 | 链接 |
|---|---|---|---|---|
| **IMSLP / Petrucci Music Library** | 大量古典乐谱扫描/排版 | 逐作品/版本/辖区判断；2026 年美国规则：1930 年及以前首次出版进入 PD；加拿大/欧盟不同 | 曲目来源、参考版本 | <https://imslp.org/> |
| **IMSLP 版权指南** | 版权说明 | 页面会更新；以当前页面为准 | 入库前核对 | <https://imslp.org/wiki/IMSLP:Copyright_Made_Simple> |
| **Mutopia Project** | LilyPond 排版、PDF/MIDI/源码 | **逐曲许可不同**：PD、CC BY、CC BY-SA、MutopiaBSD；必须看每首 | 干净排版、可编辑源 | <https://www.mutopiaproject.org/> |
| **OpenScore Lieder** | 19 世纪艺术歌曲，~1300 首 | **CC0**；GitHub 为 MuseScore 源，MusicXML 需转换/下载 | 进阶、和声分析 | <https://github.com/OpenScore/Lieder> |
| **OpenScore String Quartets** | ~200 首四重奏/~700 乐章 | **CC0**；GitHub 为 .mscx，MusicXML 于 fourscoreandmore/MuseScore | 进阶、多声部 | <https://github.com/OpenScore/StringQuartets> |
| **Musopen** | 录音/曲谱/教育材料 | **逐条许可**（多为 CC/PD）；录音与版本分别看 | 参考录音、曲目 | <https://musopen.org/> |
| **free-scores.com** | 大量用户上传 | 许可混杂；只作索引，逐曲核对 | 查找线索 | <https://www.free-scores.com/> |
| **8notes** | 免费/会员曲谱 | 许可混杂；部分改编有版权 | 查找线索 | <https://www.8notes.com/> |

### 3.1 IMSLP 使用要点

- IMSLP 是**仓库**，不是统一许可；每个文件有独立版权状态。
- 美国 2026 年：1930 年及以前首次出版的作品进入 PD；1931–1977 需看续期/来源；
  1978 后按作者终生+70 年。外国作品可能受 URAA 恢复影响。
- 加拿大/欧盟/中国规则不同；如果发行到多地区，按最严格地区处理或只做链接。
- 排版/编订/前言可能有单独的编辑版权；只用 PD 版本，或自己重新编配。
- 不把 IMSLP 扫描 PDF 直接打包；用 MusicXML 重新制作或引用链接。

### 3.2 Mutopia 使用要点

- 每首曲子的页面会写许可；不要假设全站 PD/CC0。
- 选 PD/CC0 最稳；CC BY 需署名；CC BY-SA 需同许可；MutopiaBSD 需保留声明。
- LilyPond 源码可转 MusicXML/MIDI；转换后仍受原许可约束。

### 3.3 OpenScore 使用要点

- Lieder/StringQuartets 为 CC0，可自由使用；仍建议在关于页致谢。
- 曲目偏进阶，适合阶段 6+、和声/多声部示例，不作为零基础主教材。
- GitHub 仓库多为 `.mscx`；MusicXML/MXL 通过 MuseScore 批量转换或
  <https://fourscoreandmore.org/openscore/> 获取。
- 引用：Gotham et al., OpenScore Lieder / String Quartet Corpus 论文（见仓库 CITATION）。

### 3.4 Musopen 使用要点

- 作品本身多为 PD，但**具体录音/版本/编配**可能另有许可；逐条看。
- 免费账号有下载限制；付费会员解锁无损；不要绕过限制批量抓取。
- 若只用 FluidSynth 生成示范，可不依赖 Musopen 录音；Musopen 作参考即可。

### 3.5 机器可读（MusicXML / MIDI）来源

> 核心课程必须能跟谱/下一键/判定，所以优先选**已有 MusicXML/MIDI**的源；
> PDF-only 只做参考/转写，不直接作为主练习。

| 来源 | 格式 | 许可/注意 | 适合 |
|---|---|---|---|
| **本项目编配** | MusicXML + MIDI | 原创/编配；可控 | 主教材/曲目库（首选） |
| **OpenScore Lieder** | `.mscx` → MusicXML/MXL；MuseScore 转换 | CC0；进阶 | 阶段 6+ 拓展/分析 |
| **OpenScore String Quartets** | `.mscx` → MusicXML/MXL | CC0；进阶 | 多声部/分析 |
| **MuseTrainer Library** | `.mxl`（MusicXML） | 候选；PD 作品，编配/站点条款需核验 | 入门曲目种子 |
| **schoolbandclass.com** | MusicXML/PDF | 候选；PD 作品，站点条款/编配需核验 | 大量入门/方法包 |
| **MuseScore 公共领域曲目** | MusicXML/MXL（免费账号） | 逐曲许可不同；需核验 | 曲目种子/参考 |
| **Pianovera** | MIDI（55 首，含入门） | 多来自 Mutopia；逐条核验 | 示范/选曲线索 |
| **Mutopia** | LilyPond/PDF/MIDI | **无原生 MusicXML**；转换/重录 | 参考/转写 |
| **IMSLP** | 多为 PDF 扫描 | 版权/版本逐项核对 | 参考/OMR/转写 |
| **CPDL** | PDF/MIDI/MusicXML | 合唱为主；逐曲许可 | 进阶/合唱 |
| **MusicXML.com 目录** | 链接到 MusicXML 站点 | 逐站许可 | 找源 |
| **W3C MusicXML tests** | `.musicxml` 测试文件 | 规范测试；非曲目 | 解析器回归 |

**选择顺序**

1. 本项目编配（100% 可控、可解析）。
2. OpenScore CC0 / 明确可用的 MusicXML 源。
3. MuseScore/MuseTrainer/schoolbandclass 候选（逐项核验许可/编配）。
4. Mutopia/IMSLP/PDF：参考或转写；不作为批量核心。
5. 图片/PDF：只显示，不进核心跟谱。

### 3.6 转换与校验工具

| 工具 | 用途 | 注意 |
|---|---|---|
| **MuseScore** | 录入/编配；导出 MusicXML/MIDI | `mscore -o out.musicxml in.mscz`；批量 `-j job.json` |
| **Audiveris** | PDF/图片 → MusicXML/MIDI（OMR） | AGPL-3.0；识别后必须人工修正；只处理可用来源 |
| **W3C MusicXML tests** | 解析器回归 | `w3c-cg/musicxml/tests`；取常用记号子集 |
| **xmllint / MuseScore 重开** | XML/结构校验 | 不替代音乐校验 |
| **本项目解析器** | 下一键/映射/判定 | 以 CONTENT_SCHEMA 为准 |
| **FluidSynth** | 示范/伴奏 | 固定 velocity；48 kHz |

> 具体命令/版本在实现时锁定；这里只说明路径。详见 [CONTENT_PIPELINE.md](CONTENT_PIPELINE.md)。

**数量判断（候选池）**

- 本项目编配：59 首曲目 + 62 条谱面训练（目标）。
- MuseTrainer：70+ 首入门 `.mxl`（候选，需核验）。
- schoolbandclass：11,500+ 首 PD 曲目（候选，需核验站点条款/编配）。
- OpenScore：CC0，进阶/多声部（数百首）。
- MuseScore 公共领域曲目：大量，逐曲核验。
- Pianovera：55 首 MIDI（多为 Mutopia，候选）。
- Beyer/Czerny/Hanon：PD，需选段重录。

> 候选池数量足够；但"能下载"不等于"能进核心课程"。
> 只有通过 MusicXML 解析、映射/音域、左右手、下一键/判定、试弹校验的内容才能 `ready`。
> 私有版可直接用更多源；公开版按 RELEASE_POLICY 剔除/替换。

---

## 4. 公共领域方法书与练习

| 作品 | 作者/年代 | 状态 | 用途 | 链接 |
|---|---|---|---|---|
| **Vorschule im Klavierspiel, Op.101** | Ferdinand Beyer (1803–1863) | PD（作品）；选 PD 版本 | 阶段 1–3 短练习/曲目 | <https://imslp.org/wiki/Vorschule_im_Klavierspiel,_Op.101_(Beyer,_Ferdinand)> |
| **Practical Method for Beginners, Op.599** | Carl Czerny (1791–1857) | PD | 阶段 3–5 五指/音阶/短练习 | <https://imslp.org/wiki/Category:Czerny,_Carl> |
| **The Virtuoso Pianist** | Charles-Louis Hanon (1819–1900) | PD | 阶段 3+ 手指练习；谨慎，不做“高抬指” | <https://imslp.org/wiki/The_Virtuoso_Pianist_(Hanon,_Charles-Louis)> |
| **Notebook for Anna Magdalena Bach** | J.S. Bach 家族/PD | PD | 小步舞曲、缪塞特等 | 在 IMSLP 搜索作品名 |
| **Album for the Young, Op.68** | Robert Schumann (1810–1856) | PD | 阶段 5–6 旋律/进行曲 | 在 IMSLP 搜索 Op.68 |
| **Album for the Young, Op.39** | P. Tchaikovsky (1840–1893) | PD | 阶段 5–6 甜梦/古老法国歌 | 在 IMSLP 搜索 Op.39 |

**注意**

- 作品 PD ≠ 某个现代版本/编订 PD；只选明确 PD 的版本，或自己编配。
- Hanon 的传统“高抬指”练习有争议；课程只取少量、慢速、放松，不做强度训练。
- Beyer/Czerny 的曲子对 32 键可能超范围；按 §20.3 编配规范简化/移调。
- 不整本打包方法书；核心只选短小条目并重录为 MusicXML；私有版可留参考 PDF。

### 4.1 选用清单（教材 / 练习 / 曲目）

| 名称 | 角色 | 原始格式 | 入库方式 | 计划数量 |
|---|---|---|---|---|
| **本项目课程/编配** | 主教材 + 曲目库 | Lesson JSON + MusicXML | 直接入库 | 57 课 / 59 曲 / 62 谱面训练 |
| **Beyer Op.101** | 练习种子 | PDF | 选段重录 MusicXML | 10–20 选段 |
| **Czerny Op.599** | 练习种子 | PDF | 选段重录 MusicXML | 10–20 选段 |
| **Hanon** | 手指练习 | PDF | 少量重录；谨慎 | 5–10 选段 |
| **OpenScore** | 拓展/进阶 | MSCX/MusicXML | 转换/校验 | 按阶段 6+ |
| **MuseTrainer** | 入门曲目种子 | MXL | 导入/校验（候选） | 70+ 可选 |
| **schoolbandclass** | 曲库候选 | MusicXML/PDF | 导入/校验（候选） | 11,500+ 可选 |
| **MuseScore 公共领域** | 曲目种子 | MSCZ/MusicXML | 逐曲核验/导出 | 按需 |
| **Pianovera** | MIDI 示范/线索 | MIDI | 逐条核验 | 55 可选 |
| **OMT / Musicca / 维基 / MOOC** | 理论参考 | HTML/PDF | 只链接/重写，不打包 | — |

> "计划数量"是设计目标；核心只收经过 MusicXML 解析、映射/音域、左右手、
> 下一键/判定、试弹校验的内容。PDF-only 的教材/曲目不直接作为主练习。

---

## 5. 入门曲目线索（仅索引；逐曲核对）

以下站点按难度整理 PD 曲目，可作为选题线索；**不要直接复制其排版/改编**：

| 站点 | 内容 | 注意 |
|---|---|---|
| **Artform / jamescarterpiano.com** | 按阅读难度整理的 easy/PD 曲目 | 站点编排/生成版本可能另有版权；只作索引 |
| **Clefsight** | 849 首 PD 曲目 + 简化版 | 生成版权的“简化版”需核对；只作索引 |
| **piano.org** | 曲目难度 | 来源/许可逐条看 |
| **free-scores.com** | 用户上传 | 许可混杂 |
| **8notes** | 免费/会员 | 许可混杂 |

### 5.1 推荐的公有领域入门曲目池

> 仅列作品/传统曲调；具体编配由本项目原创。现代改编版、流行曲、影视配乐不在内。

- **民歌/儿歌（传统/PD）**：小星星（Twinkle）、两只老虎（Frère Jacques）、
  玛丽有只小羊羔、伦敦桥、友谊地久天长、绿袖子、斯卡布罗集市、樱花、
  铃儿响叮当、很久以前。
- **古典主题（PD）**：贝多芬《欢乐颂》、莫扎特《小步舞曲》K.2、
  巴赫/佩措尔德《G 大调小步舞曲》、巴赫《缪塞特》、
  帕赫贝尔《卡农》主题、舒曼《旋律》《士兵进行曲》、
  柴可夫斯基《甜梦》《古老的法兰西歌曲》。
- **中文传统曲调（需逐版核对）**：茉莉花、送别（旋律 Ordway，PD；词李叔同，PD）。
  只做器乐编配；不采用现代流行歌曲/受版权保护的改编版。
- **不要用**：Suzuki、Thompson、Bartók《Mikrokosmos》、Kabalevsky 等现代教材；
  流行歌、影视配乐、动漫歌曲；版权不明的“简化版”。

---

## 6. 开源工具与组件许可

| 组件 | 用途 | 许可（需在实现时复核） | 链接 |
|---|---|---|---|
| **MuseScore** | 制谱、MusicXML/MIDI 转换 | GPL-3.0 | <https://musescore.org/> |
| **Verovio** | MusicXML/MEI → SVG 谱面 | LGPL-3.0 | <https://www.verovio.org/> |
| **music21** | 乐理/MusicXML 解析 | BSD-3-Clause（需复核） | <https://web.mit.edu/music21/> |
| **mido** | MIDI 读写 | MIT（需复核） | <https://mido.readthedocs.io/> |
| **LilyPond** | 排版/转换 | GPL-3.0 | <https://lilypond.org/> |
| **FluidSynth** | 音频合成 | LGPL-2.1+ | <https://www.fluidsynth.org/> |
| **TimGM6mb SoundFont** | 内置音色 | GPL-2.0（现有 vendor） | 现有 `pc/prototype/vendor/soundfont` |
| **PySide6 / Qt** | UI | LGPL-3.0 / GPL-3.0 / 商业 | <https://www.qt.io/qt-for-python> |
| **Noto Sans SC** | 中文字体（若打包） | OFL-1.1 | <https://fonts.google.com/noto> |
| **Lucide / 开源图标** | 图标 | ISC（需复核） | <https://lucide.dev/> |

**注意**

- LGPL 组件（Verovio、FluidSynth、Qt）动态链接/可替换性需按 LGPL 要求处理。
- GPL 组件（MuseScore、LilyPond、TimGM6mb）若分发组合需评估整体许可；
  现有项目已使用 TimGM6mb，需在关于页/许可清单中保留 GPL 声明。
- BSD/MIT 需保留版权声明。
- 字体若打包 Noto Sans SC（OFL）需保留许可；也可用系统字体避免打包。

---

## 7. 中文资源与版权

| 资源 | 内容 | 使用方式 |
|---|---|---|
| **维基教科书《乐理与作曲》** | 中文基础乐理/五线谱/简谱 | CC BY-SA；可改编需署名+同许可；只取概念，重写讲解 |
| **Musicca 中文** | 互动乐理/练习/工具 | 免费；版权保留；只链接，不抓取 |
| **中国大学 MOOC《音乐奥秘解码——轻松学乐理》** | 中央音乐学院；零基础乐理/五线谱 | 免费学习，证书付费；版权归课程方；**只做外部链接** |
| **中国大学 MOOC《拿谱就唱——视唱练耳轻松学》** | 中央音乐学院；读谱/视唱 | 同上 |
| **国家高等教育智慧教育平台** | 多门乐理课 | 只链接；逐课看许可 |
| **B 站/公众号教程** | 大量中文视频 | 版权保留；只链接；不下载/转录 |

> 内置课程的中文文字必须由本项目撰写；可以“参考”这些课程的知识结构，
> 但不能复制讲义、视频、图片、题目。引用概念/术语不受版权保护，表达受保护。

---

## 8. 许可决策矩阵（私有版 / 公开版）

| 来源 | 私有版（个人） | 公开版（分发） | 内置格式 | 备注 |
|---|---|---|---|---|
| 本项目原创/编配 | ✅ | ✅ | MusicXML + MIDI | 首选 |
| PD 作品 + 本项目编配 | ✅ | ✅ | MusicXML + MIDI | 核对辖区/版本 |
| PD 扫描/版本 | ✅ | ⚠️ 仅 PD 版本 | PDF 参考 → 转写 | 核心须 MusicXML |
| CC0 | ✅ | ✅（建议署名） | MusicXML/MIDI | OpenScore 等 |
| CC BY | ✅ | ✅ 署名 | MusicXML/MIDI | 保留许可 |
| CC BY-SA | ✅ | ✅ 署名+同许可 | MusicXML/MIDI | 衍生同许可 |
| CC BY-NC | ✅ 个人 | ❌ | 仅链接/私有 | 不进公开包 |
| 版权保留 | ✅ 个人合法使用 | ❌ | 仅私有/链接 | 标 remove/replace |
| 版权不明 | ✅ 个人谨慎 | ❌ | 仅私有 | 标 unknown/remove |
| 订阅/DRM | 按条款个人 | ❌ | 仅私有 | 不绕过限制/不再分发 |
| 外部链接 | ✅ | ✅ | 链接 | 不打包内容 |

**格式底线**

- 核心跟谱/判定内容：MusicXML + MIDI（或生成式 JSON 规格）。
- 图片/PDF：只做补充显示；**不能**作为主练习/判定谱。
- 私有版可以收个人用 PDF/曲谱，但若要跟谱，仍需转成 MusicXML/MIDI。

**私有版底线**

- 记录 `source_url + license + visibility + public_release + verified_at`。
- 私有文件放 `resources/private/`；不要提交到公开仓库。
- 不因为"个人用"就丢掉来源记录；将来公开版要靠它剔除/替换。

**公开版底线**

- 没有 `source_url + license + attribution + verified_at` 的内容，不进公开包。
- `public_release != allowed` 的内容必须移除/替换；见 [RELEASE_POLICY.md](RELEASE_POLICY.md)。
- 不把"免费下载"当成"可再分发"；免费≠PD。
- 不把歌词、封面、扫描页、课程视频打包。
- 不用现代流行歌/影视配乐做"教学简化版"。

---

## 9. 逐项核验清单

对每个准备内置的资源：

- [ ] 作品作者/生卒年/首次出版年已知。
- [ ] 目标发行地区的 PD 规则已核对（US/EU/CN）。
- [ ] 使用的是 PD 版本，或本项目重新编配；没有复制现代编订版。
- [ ] 许可类型明确（PD/CC0/CC BY/CC BY-SA/原创）。
- [ ] 需要署名/同许可的，已在关于页/清单中落实。
- [ ] 来源格式明确（MusicXML/MIDI/LilyPond/PDF/OMR）；PDF-only 只做参考，
      核心需转写为 MusicXML + MIDI。
- [ ] 没有歌词/图片/录音的额外版权风险；公开版尤其注意。
- [ ] 32 键编配、映射、左右手、音域可弹。
- [ ] MusicXML 可解析；调号/拍号/反复正确；MIDI 示范可播放。
- [ ] 下一键/左右手/映射/判定可在真实内容上跑通；`readiness=ready`。
- [ ] `visibility` / `public_release` / `public_alternative` 已记录；
      私有内容在 `resources/private/`，公开版有替代或移除。
- [ ] 示范音频由本项目生成或许可明确。
- [ ] 链接可访问；站点条款允许链接/引用。
- [ ] 已记录 `source_url, source_format, license, attribution, modifications,
      visibility, public_release, verified_by, verified_at`。
- [ ] 若不确定：私有版可标 `private`；公开版不内置，只做外部链接/替代。

---

## 10. 按阶段推荐资源

| 阶段 | 内置 | 外部延伸 |
|---|---|---|
| 0 上手 | 本项目向导/训练 | Musicca 中文、musictheory.net 入门 |
| 1 五线谱 | 本项目识谱训练（D1） | musictheory.net note/interval drills；Musicca 音符练习；维基教科书 |
| 2 节奏 | 本项目节奏训练（D2） | musictheory.net rhythm；Musicca 节奏；Ableton Learning Music |
| 3 右手 | 本项目曲目 P3 + Beyer/Czerny 选段编配 | MuseTrainer/schoolbandclass 候选（需核验）；Open Music Theory 基础 |
| 4 左手/和弦 | P4 + I–IV–V 训练 | Open Music Theory 和弦章节；Musicca 和弦 |
| 5 双手 | P5 + 编配 | OpenScore（CC0，进阶）；MuseScore 公共领域（逐曲核验） |
| 6 表现 | P6 + 录音 | Open Music Theory 乐句/曲式；Musopen 参考录音 |
| 7 录音/编曲 | 创作页项目 | MuseScore 教程；Ableton Learning Music 结构 |
| 8 多乐器 | 创作页项目 | OpenScore 多声部；混音基础（外部） |

---

## 11. 检索来源（2026-11-01）

以下为本次检索中使用的关键页面（用于核实，不构成对内容的再许可）：

- Open Music Theory v2：<https://viva.pressbooks.pub/openmusictheory/>
- Open Textbook Library 记录：<https://open.umn.edu/opentextbooks/textbooks/1254>
- musictheory.net：<https://www.musictheory.net/lessons>
- Musicca 中文：<https://www.musicca.com/zh>
- Ableton Learning Music：<https://learningmusic.ableton.com/>
- 维基教科书《乐理与作曲》：<https://zh.wikibooks.org/zh/樂理與作曲>
- IMSLP Beyer Op.101：<https://imslp.org/wiki/Vorschule_im_Klavierspiel,_Op.101_(Beyer,_Ferdinand)>
- IMSLP Czerny 分类：<https://imslp.org/wiki/Category:Czerny,_Carl>
- IMSLP Hanon：<https://imslp.org/wiki/The_Virtuoso_Pianist_(Hanon,_Charles-Louis)>
- IMSLP 版权指南：<https://imslp.org/wiki/IMSLP:Copyright_Made_Simple>
- Mutopia：<https://www.mutopiaproject.org/> / 许可说明：<https://www.mutopiaproject.org/legal.html>
- OpenScore Lieder：<https://github.com/OpenScore/Lieder>
- OpenScore Lieder 文档/下载：<https://fourscoreandmore.org/openscore/lieder/>
- OpenScore String Quartets：<https://github.com/OpenScore/StringQuartets>
- OpenScore 公共站点：<https://fourscoreandmore.org/openscore/>
- Musopen：<https://musopen.org/>
- 中国大学 MOOC《音乐奥秘解码——轻松学乐理》：<https://www.icourse163.org/course/detail.htm?cid=1003392004>
- 中国大学 MOOC《拿谱就唱——视唱练耳轻松学》：<https://www.icourse163.org/course/CCOM-1207553805>
- Verovio：<https://www.verovio.org/>
- MuseScore：<https://musescore.org/>
- music21：<https://web.mit.edu/music21/>
- mido：<https://mido.readthedocs.io/>
- FluidSynth：<https://www.fluidsynth.org/>
- LilyPond：<https://lilypond.org/>
- MusicXML 站点列表：<https://www.musicxml.com/music-in-musicxml/>
- MuseScore 命令行导出：<https://handbook.musescore.org/appendix/command-line-usage>
- Audiveris OMR（AGPL-3.0）：<https://audiveris.github.io/audiveris/>
- W3C MusicXML tests：<https://github.com/w3c-cg/musicxml/tree/main/tests>
- MuseTrainer Library（候选，需核验）：<https://musetrainer.github.io/>
- schoolbandclass（候选，需核验）：<https://schoolbandclass.com/library/>
- Pianovera MIDI（候选，需核验）：<https://pianovera.com/en/midi/>

> 检索结果中出现的第三方列表/博客只作线索；其内容与许可仍需逐项核对。

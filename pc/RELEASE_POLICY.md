# 私有版 / 公开版内容策略
## 个人使用可直接收，公开版按标记自动剔除或替换

> **状态：设计（2026-11-01）；H9a 过滤/打包 guardrails 已实现（2026-11-09）；
> 公开仓库已于 2026-11-13 初始化并推送（首提交按本策略排除私有/用户数据）。**
> 背景：2026-11-13 已建立公开 GitHub 仓库；设计目标不是限制本地使用，而是
> 把"能不能公开"标清楚，公开版时按清单删/换，不用回头翻遍资源。
> 已实现：`app/core/release.py` + `tools/build_public.py`（白名单构建、私有/
> 用户数据剔除、压缩包审计、`public_exclusions.json` 与 `PUBLIC_CONTENT.md`）；
> 完整安装包与 `public_alternative` 替换仍属 H9c。
>
> 配套：[CONTENT_PIPELINE.md](CONTENT_PIPELINE.md)、[CONTENT_SCHEMA.md](CONTENT_SCHEMA.md)、
> [RESOURCES.md](RESOURCES.md)。

---

## 1. 两种构建

| 构建 | 用途 | 内容范围 | 网络/账号 |
|---|---|---|---|
| **私有版 `private`** | 你个人使用 | 原版 + 个人可用的教材/曲谱/录音 | 不要求上传 |
| **公开版 `public`** | 将来公开分发 | 只含明确可再分发/已替换的内容 | 不需要账号 |

- **私有版**：按你的使用方式，可以直接纳入你能合法访问的教材、曲谱、录音；
  仍建议记录来源，方便以后标记/替换。
- **公开版**：只打包 `public_release: allowed` 的内容；`remove` 的不打包，
  `replace` 的用 `public_alternative` 替换。
- 两种构建共用同一套课程 ID/进度；公开版缺内容时显示"内容制作中"或替代曲目，
  不崩溃、不显示坏链接。

> 说明：这是内容标记与构建流程的设计，不是法律意见。个人使用也应遵守你所在地区
> 的法律/站点条款；公开分发时版权责任由发布者承担。

---

## 2. 内容字段（每个课程/曲目/训练/项目/图片/音频）

```json
{
  "content_id": "p3-01",
  "title": "小星星（右手）",
  "visibility": "public",
  "public_release": "allowed",
  "license": "LicenseRef-PublicDomain",
  "source_url": "https://example.org/source",
  "source_format": "musicxml",
  "readiness": "ready",
  "private_ok": true,
  "public_ok": true,
  "public_alternative": null,
  "removal_action": null,
  "attribution": "旋律：传统/公有领域；编配：本项目",
  "verified_at": "2026-11-01"
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `visibility` | `public` / `private` | 文件放在哪个目录；私有文件不进公开包 |
| `public_release` | `allowed` / `remove` / `replace` / `unknown` | 公开版动作 |
| `license` | SPDX / `LicenseRef-*` / `PersonalUseOnly` / `Unknown` | 许可标识 |
| `source_url` | URL / null | 具体作品/版本页面，不是站点首页 |
| `source_format` | `musicxml` / `midi` / `lilypond` / `pdf` / `omr` / `original` | 来源格式 |
| `readiness` | `planned` … `ready` | 是否能跟谱/判定；核心内容必须 `ready` |
| `private_ok` | true/false | 私有版是否可用 |
| `public_ok` | true/false | 公开版是否可用 |
| `public_alternative` | content_id / null | `replace` 时用哪个公开内容替代 |
| `removal_action` | `exclude` / `replace` / `hide_stage` / null | 公开版怎么处理 |
| `attribution` | 文本 | 署名/来源/修改说明 |
| `verified_at` | 日期 | 许可/来源核对时间 |

**规则**

- 任何非原创内容：`source_url + license + attribution + verified_at` 必填。
- 不确定能否公开：`public_release: unknown` → 公开版按 `remove` 处理。
- 私有内容即使 `public_release: allowed`，也要在公开包前复核；默认不信任未核验。
- `replace` 必须有 `public_alternative`；没有替代则 `remove`，课程页显示"此内容在公开版中不可用"。
- 公开版的图片/音频也要单独标记；不能只标曲谱。
- **当前具体项（2026-11-08）**：`mariage_fragment`（梦中的婚礼 · 片段）是
  `visibility: private`、`public_release: remove`；公开构建必须排除
  `mariage_fragment.musicxml` / `.mid` 与课程条目，私有版可保留。课程数据中
  该项已标 `PracticeItem.visibility = "private"`。
- **公开 checkout 不携带 private 文件（2026-11-13）**：书库/测试不得把
  缺失的 private 资产显示成 planned 卡或“资源缺失”警告；公开包审计仍按
  `content_manifest` 拒绝该路径，两者不能互相替代。

---

## 3. 目录与清单

```
pc/resources/
  public/                  # 公开版可用（原创/PD/CC0/已清理）
    curriculum/
    scores/
    images/
    audio/
  private/                 # 私有版可用；公开版不打包
    curriculum/
    scores/
    images/
    audio/
    notes/
  licenses/
    manifest.json          # 全部内容（含私有）的来源/许可
    public_exclusions.json # 公开版排除/替换清单
    texts/                 # 许可全文
```

- `private/` 必须在 `.gitignore` 中；将来建公开仓库时不要提交。
- `public/` 只放允许公开的文件；CI/构建脚本只打包这里。
- `manifest.json` 可以记录私有内容（本地），但 `public_exclusions.json` 只列
  公开版需要剔除/替换的 ID 和原因，不含私有文件内容。
- 如果将来把私有内容误提交到公开仓库：发布前需要从历史中移除（rewrite history），
  不能只删当前文件。

### 3.1 `public_exclusions.json` 示例

```json
{
  "schema_version": 1,
  "generated_at": "2026-11-01",
  "items": [
    {
      "content_id": "p9-01",
      "reason": "外部教材改编，仅个人使用",
      "action": "remove",
      "public_alternative": null
    },
    {
      "content_id": "p9-02",
      "reason": "现代作品，公开版不可分发",
      "action": "replace",
      "public_alternative": "p3-01"
    }
  ]
}
```

- `action: remove`：公开版删掉；若课程引用，显示占位/跳过。
- `action: replace`：用替代内容；课程/进度按 ID 映射。
- `action: hide_stage`：整个阶段不公开（例如阶段 8 的私有项目模板）。
- 公开构建失败条件：引用私有 ID、缺替代、许可缺失、私有文件出现在 public/。

---

## 4. 私有版：可以直接收，但要记录

- 个人使用的教材/曲谱/录音可以放 `private/`；不要求公开许可。
- 仍然建议记录：标题、来源、获取日期、格式、用途、是否可公开、替代方案。
- 这样将来做公开版时：
  - 不需要重新判断"这是哪来的"；
  - 直接按 `public_release` 批量剔除/替换；
  - 课程页不会出现"图裂/文件缺失"。
- 私有版不联网、不上传；用户数据/项目也只在本地。
- 私有内容如果要用于跟谱/下一键/判定，同样必须转成 MusicXML/MIDI；
  只有 PDF/图片的私有内容只能“仅显示”，不能作为主练习。

---

## 5. 公开版：只保留可公开内容

### 5.1 允许

- 本项目原创/编配（`LicenseRef-Original`）。
- 公共领域（`LicenseRef-PublicDomain`）作品 + 本项目编配；按发行地区核对。
- CC0。
- CC BY / CC BY-SA：按许可署名/同许可；保留许可全文与链接。
- 用户自己创作的内容（用户明确同意公开）。

### 5.2 不允许（公开版）

- 版权保留的教材、曲谱、改编、歌词、图片、录音。
- 仅限个人使用/订阅/DRM 的内容。
- 版权不明、来源不明的扫描/转录/编配。
- CC BY-NC（商业/公开分发）内容。
- 从 IMSLP 下载的现代编订版/非 PD 版本（即使作品 PD）。
- 现代流行歌、影视/动漫配乐、受版权保护的“简化版”。

### 5.3 公开替代策略

| 私有内容 | 公开替代 |
|---|---|
| 受版权保护的方法书条目 | 本项目原创训练，或 Beyer/Czerny/Hanon 的 PD 选段（重新录入） |
| 现代流行/影视曲 | 民歌/古典主题/本项目原创；或直接移除 |
| 付费/订阅曲谱 | OpenScore（CC0）、PD 曲目、本项目编配 |
| 外部录音 | FluidSynth 生成的示范/伴奏 |
| 版权不明图片 | 本项目绘制/无图；或换成 PD 图片 |
| 私有项目模板 | 公开模板（原创 MIDI/项目 JSON） |

- 替代内容也必须是 MusicXML/MIDI 可解析（见 CONTENT_PIPELINE）。
- 替代后要在 `public_exclusions.json` 记录映射，保证课程/进度不引用旧 ID。

---

## 6. 公开版清理清单

发布前逐项检查：

### 6.1 内容

- [ ] `public/` 中没有 `private/` 的文件/软链接。
- [ ] 所有公开曲目/训练/项目在 `manifest.json` 有许可/来源/署名。
- [ ] `public_exclusions.json` 覆盖所有 `public_release != allowed` 的内容。
- [ ] `replace` 项有有效替代；课程/进度引用已更新。
- [ ] 没有版权不明的 PDF/图片/录音/歌词。
- [ ] 没有外部教材的整段文字/题目/视频。
- [ ] 图片/音频/字体/图标各自有许可记录。

### 6.2 代码/构建

- [ ] 公开构建脚本只读取 `resources/public/`。
- [ ] 构建时扫描并拒绝私有路径/ID。
- [ ] 安装包里没有 `user-data/`、日志、缓存、`.pio`、测试截图。
- [ ] 没有把私有文件提交到公开仓库；如已提交，历史已清理。
- [ ] 关于页/许可页列出开源组件、字体、SoundFont、CC0/CC BY 署名。

### 6.3 文档/截图

- [ ] 截图/演示视频不包含私有曲目/教材内容。
- [ ] 设计文档/示例不引用私有文件路径。
- [ ] README/帮助中的“内置曲目”列表与公开版一致。
- [ ] 公开版说明中注明“部分内容因许可未包含/已替换”。

---

## 7. 构建流程（设计）

```
内容 JSON + 文件
   │
   ├─ private 构建：public/ + private/ → 私有包（个人）
   │
   └─ public 构建：
        1. 读 manifest / public_exclusions
        2. 只收 public_release=allowed 或 replace(有替代)
        3. 校验：无 private 路径/ID；许可完整；MusicXML 可解析
        4. 生成 PUBLIC_CONTENT.md（包含/替换/移除清单）
        5. 打包；关于页附许可
```

- 公开构建失败即停止，不做“先出包再补”。
- 私有构建可以警告（缺许可/来源），但不阻塞。

**当前实现（H9a）**：运行 `cd pc && python tools/build_public.py`。白名单由
`content_manifest`（课程 `visibility`）与整个 `resources/` 扫描共同派生；
私有课程资产、`visibility` 非 public 或 `public_release != "yes"` 的项目模板、
禁止路径（`user-data/`、`learning.json`、`score_prefs.json`、`keybindings.json`、
日志、缓存、`mockups/`、`dist/`、`.pio/`、临时文件）均被剔除。写包后会重新
打开压缩包做二次审计；任一问题退出非零且不留下压缩包。包内
`public_exclusions.json` 记录每条移除的原因与文件，`PUBLIC_CONTENT.md` 是
人类可读的包含/移除清单。`public_alternative` 替换语义尚未实现。

---

## 8. 现在要做的记录

即使现在不公开，也先把这些写进清单：

1. 每个非原创曲目/教材：来源 URL、版本/编配者、获取日期、格式、是否可公开。
2. 每个私有内容：`visibility: private`、`public_release: remove|replace`、
   替代 ID（若有）。
3. 每个公开内容：许可、署名、修改说明、可解析文件路径。
4. 课程页引用：私有内容被移除时怎么显示（跳过/占位/换曲）。
5. 截图/演示中是否出现私有内容。
6. 未来公开仓库的 `.gitignore`：`resources/private/`、`user-data/`、日志/缓存。

这样将来公开版只需要跑一次排除清单，而不是重新审一遍所有内容。

---

## 9. 验收

- [ ] 私有版能完整运行所有课程/曲目（含个人用内容）。
- [ ] 私有/公开字段在每个内容条目上都有值。
- [ ] `public` 构建不含任何 `private/` 文件；无私有 ID 引用。
- [ ] 公开版有完整许可/署名页；替代内容可跟随/可练习。
- [ ] 公开版缺失内容有明确占位/替代，不出现坏链接/空练习。
- [ ] 公开仓库（若建立）不含私有内容；历史已检查。

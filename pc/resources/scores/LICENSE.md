# Built-in sample / beginner scores

Every file in this folder is a deterministic, project-generated beginner
arrangement of a public-domain melody. They exercise the parser, piano-roll,
next-key, follow, auto-window and learning flows; they are not authoritative
editions.

| Stem | Title | Melody | Arrangement |
|---|---|---|---|
| `xiaoxingxing` | 小星星（片段） | traditional | `pc/tools/make_sample_score.py` |
| `two_tigers` | 两只老虎 | French traditional, public domain | `pc/tools/make_beginner_pieces.py` |
| `london_bridge` | 伦敦桥 | English traditional, public domain | `pc/tools/make_beginner_pieces.py` |
| `lightly_row` | 小蜜蜂 | German traditional, public domain | `pc/tools/make_beginner_pieces.py` |
| `ode_to_joy` | 欢乐颂 | Beethoven, public domain | `pc/tools/make_beginner_pieces.py` |
| `jingle_bells` | 铃儿响叮当（片段） | James Lord Pierpont, public domain | `pc/tools/make_beginner_pieces.py` |
| `canon_easy` | 卡农片段 · 简易版 | Pachelbel, public domain | `pc/tools/make_beginner_pieces.py` |
| `farewell` | 送别 | John P. Ordway, public domain | `pc/tools/make_beginner_pieces.py` |
| `ode_to_joy_both` | 欢乐颂 · 双手版 | Beethoven, public domain | `pc/tools/make_beginner_pieces.py` (two voices) |
| `scale_c_major_updown` | C 大调音阶上下行 | original exercise | `pc/tools/make_stage3_exercises.py` |
| `intervals_seconds_thirds` | 二度与三度音程 | original exercise | `pc/tools/make_stage3_exercises.py` |
| `legato_staccato` | 连奏与断奏对比 | original exercise | `pc/tools/make_stage3_exercises.py` |
| `chords_cfg` | C–F–G 和弦 | original exercise | `pc/tools/make_stage4_exercises.py` |
| `arpeggio_4_4` | 分解和弦 · 4/4 | original exercise | `pc/tools/make_stage4_exercises.py` |
| `split_hands_8bars` | 左右分区 · 8 小节 | original exercise | `pc/tools/make_stage5_exercises.py` |
| `ode_to_joy_both_slow` | 慢速合手 · 50% | Beethoven, public domain; original arrangement | `pc/tools/make_stage5_exercises.py` |
| `fixed_accompaniment` | 固定伴奏型 | Beethoven melody, public domain; original accompaniment | `pc/tools/make_stage5_exercises.py` |
| `twinkle_auto_accompaniment` | 小星星 · 自动左手 | French traditional, public domain; original accompaniment | `pc/tools/make_accompaniment_songs.py` (two parts: P1 melody, P2 auto accompaniment) |
| `ode_auto_accompaniment` | 欢乐颂 · 自动左手 | Beethoven, public domain; original accompaniment | `pc/tools/make_accompaniment_songs.py` (P1 melody, P2 auto accompaniment) |
| `two_tigers_auto_accompaniment` | 两只老虎 · 自动左手 | French traditional, public domain; original accompaniment | `pc/tools/make_accompaniment_songs.py` (P1 melody, P2 auto accompaniment) |
| `minuet_3_4` | 小步舞曲 | original exercise | `pc/tools/make_stage5_exercises.py` |
| `phrasing_8bars` | 乐句起落 | original exercise | `pc/tools/make_stage6_exercises.py` |
| `tempo_ladder_60` | 速度阶梯 60→100% | original exercise | `pc/tools/make_stage6_exercises.py` |
| `fur_elise_theme` | 致爱丽丝 · 主题 | Beethoven, public domain | `pc/tools/make_stage6_exercises.py` |
| `mariage_fragment` | 梦中的婚礼 · 片段 | **Copyrighted — private use only** | `pc/tools/make_stage6_exercises.py` |

Each stem has a `.musicxml` and a same-stem `.mid`. Both are generated from
the same note list, so note count, pitches, measure numbers and duration
agree.

- **License:** Public Domain for the melodies and these simple arrangements.
  The Stage 3 exercises (`scale_c_major_updown`, `intervals_seconds_thirds`,
  `legato_staccato`), Stage 4 exercises (`chords_cfg`, `arpeggio_4_4`), Stage 5
  `split_hands_8bars` / `minuet_3_4`, and Stage 6 `phrasing_8bars` /
  `tempo_ladder_60` are original exercises written for this project; they
  contain no third-party melody and may be redistributed with the project.
  `ode_to_joy_both_slow` / `fixed_accompaniment` use the public-domain 欢乐颂
  melody with original arrangements/accompaniment; the three
  `*_auto_accompaniment` files use public-domain melodies (小星星 / 欢乐颂 /
  两只老虎) with original left-hand parts.
  `fur_elise_theme` uses the public-domain Beethoven theme. **`mariage_fragment` is copyrighted private
  content: keep it out of public builds.**
- **Not content for public redistribution?** These are original simple
  arrangements of public-domain melodies; they may be redistributed. Replace
  them with licensed, validated arrangements as the curriculum grows.

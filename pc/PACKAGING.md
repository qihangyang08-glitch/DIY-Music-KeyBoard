# Windows 桌面版打包（A4）

> 2026-11-15。目标：不装 Python 的 Windows 机器也能双击运行，包含
> FluidSynth 与 TimGM6mb SoundFont。当前产物是**免安装 one-folder**，
> 还不是 MSI/EXE 安装器。

## 1. 构建

在 `pc/` 下：

```bat
python -m pip install -r requirements-dev.txt
python tools\build_app.py --clean
```

产物：

```
pc\dist\KeyBorad\
  KeyBorad.exe
  _internal\
    app\...              Python 模块与 PySide6
    resources\           曲谱/课程/项目/图片（公开内容）
    mapping\             keymap.json / csv（仓库根目录的共享表）
    prototype\vendor\    FluidSynth DLL + TimGM6mb.sf2
```

`python tools\build_app.py --output D:\build` 可改输出目录。构建约 1 分钟，
产物约 133 MB；`pc/dist/` 与 `pc/build/` 都在 `.gitignore` 中。

## 2. 打包了哪些东西

| 来源 | 目标 | 说明 |
|---|---|---|
| `app/main.py` + `app/` | `_internal/app` | PyInstaller 自动分析导入 |
| `resources/` | `_internal/resources` | 只含公开内容；`mariage_fragment` 仍被排除 |
| `mapping/` | `_internal/mapping` | 固件通道 ↔ 音符映射 |
| `prototype/vendor/fluidsynth-*/bin/*.dll` | `_internal/prototype/vendor/...` | 只带 DLL，不带 `fluidsynth.exe`、头文件、`.lib` |
| `prototype/vendor/soundfont/TimGM6mb.sf2` + `COPYING.txt` | `_internal/prototype/vendor/soundfont` | 许可文件随包 |
| 用户数据 | **不打包** | `learning.json`、`calibration.json`、`keybindings.json` 等 |

数据计划由 [`app/core/packaging.py`](app/core/packaging.py) 生成，测试见
[`tests/test_packaging.py`](tests/test_packaging.py)。`resources/` 先过
[`app/core/release.py`](app/core/release.py) 的公开白名单：本地
`mariage_fragment.*` 等私有文件不会进入包（本机实测 148 → 146 个资源文件）。
运行时路径由 [`app/core/paths.py`](app/core/paths.py) 统一解析：源码运行取
`pc/`，冻结后取 `sys._MEIPASS`（即 `_internal/`），两种布局一致。

## 3. 已验证 / 未验证

已验证（2026-11-15，本机）：

- PyInstaller 6.22.3 + Python 3.11 构建 **SUCCESS**。
- `dist\KeyBorad\KeyBorad.exe --no-serial --no-onboarding --screenshot ...`
  正常启动、加载内置曲谱、FluidSynth 报 48 kHz、渲染完整界面。
- 包内存在 `resources/`、`mapping/keymap.json`、
  `prototype/vendor/soundfont/TimGM6mb.sf2` 与 `libfluidsynth-3.dll`。
- 私有曲 `mariage_fragment.*` 未进入包；57 个课程 JSON 与全部公开曲谱在包内。

**未验证**（发布前必须做）：

- 干净 Windows 10/11 机器（无 Python、无 VC++ 运行库）双击启动。
- 杀毒软件误报（PyInstaller 常见；必要时代码签名）。
- 卸载：删除整个 `KeyBorad` 文件夹即可；用户数据在
  `%LOCALAPPDATA%` 下单独保留，不随程序删除。
- 多显示器/高 DPI、无音频设备、COM 口被占用时的启动表现。

## 4. 干净机器验收清单

1. 复制整个 `KeyBorad` 文件夹到目标机（U 盘即可）。
2. 双击 `KeyBorad.exe`；首次启动出现向导，可跳过。
3. 顶栏显示 `48 kHz`；断开网络仍能发声。
4. 学习 → 阶段 0 → 第一课可打开；曲库显示内置曲目。
5. 插上 ESP32-S3，设备页显示 3 个模块；校准页可开始检测。
6. 退出后重新启动，主题/语言/学习记录仍在。
7. 删除文件夹后无残留服务/驱动；用户数据目录可选手动清理。

## 5. 固件 OTA（C4，可选）

默认固件只走 USB 串口，不编入 Wi-Fi。需要无线升级时：

```bat
set PLATFORMIO_BUILD_FLAGS=-D KEYBORAD_ENABLE_OTA=1 -DKEYBORAD_WIFI_SSID=\"你的SSID\" -DKEYBORAD_WIFI_PASS=\"你的密码\"
pio run -e esp32-s3-devkitc-1 -t upload
```

之后设备启动会连接 Wi-Fi，串口打印 `OTA ready at <IP>`；用
Arduino IDE / `espota.py` 指向该 IP 升级。**默认发布固件不打开 OTA**，
避免把 Wi-Fi 凭据编进公开仓库；凭据只通过本机构建参数传入。

## 6. 后续（未做）

- MSI/Inno Setup 安装器、开始菜单/桌面快捷方式、卸载登记。
- 代码签名与自动更新检查（D3）。

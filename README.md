# Nikon Z 区域语言锁解锁 / Nikon Z Region Language Unlock

[简体中文](#简体中文) · [English](#english)

---

# 简体中文

部分地区的尼康微单把菜单语言限制为少数几种（例如美版 Z5 只有英/西/法/葡）。
这个限制**不是固件裁剪**：同一个固件全球通用，完整语言列表（31 种，含简体中文）
一直都在机身里，只是被一个配置标志屏蔽了。

本工具通过相机的**服务模式**接口把这个标志置 1 并提交，从而展开完整语言列表。

**不刷固件、不改哈希、不需要 K8、不需要重签。**

## 适用范围

| 机型 | 固件 | 状态 |
|---|---|---|
| Nikon Z5 | C 1.50 | ✅ 实机验证，重启后保持 |
| Nikon Z fc | C 1.81 | ✅ 实机验证，重启后保持 |
| Nikon Z6 / Z7 | C 3.80 | 上游项目验证（见致谢） |
| 其他 EXPEED 6 机型 | — | 未测试；**换版本前必须先只读确认** |

## 原理

配置块（约 131 KB）中偏移 16 的 1 个字节是语言列表开关：

| 值 | 效果 |
|---|---|
| `0x00` | 受限列表（地区默认） |
| `0x01` | 完整列表（含简体中文、繁体中文、日文等 31 种） |

写入后必须显式"提交"才会持久化；不提交则断电恢复。

完整协议与步骤见 [docs/NIKON-REGION-LANGUAGE-UNLOCK.md](docs/NIKON-REGION-LANGUAGE-UNLOCK.md)。

## 快速开始

### 1. 环境

- Windows，Python 3.10+
- 相机电量充足，USB 直连主板后置口
- 相机 USB 模式设为 **MTP/PTP**

```powershell
pip install pyusb libusb-package
```

### 2. 绑定驱动

用 [Zadig](https://zadig.akeo.ie/) 把相机绑定到 **WinUSB**：

1. 相机开机并连接 USB
2. Zadig → **Options → List All Devices**
3. 选择相机（VID `04B0`），目标驱动选 **WinUSB** → **Replace Driver**

完成后相机不再以"便携设备"出现，这是正常现象。

### 3. 使用

```powershell
python unlock.py info                  # 查看机型与固件版本（只读）
python unlock.py read --out backup.bin # 读出配置块（只读）
python unlock.py enable                # 暂存 flag=1，不提交
python unlock.py enable  --commit      # 暂存并提交
python unlock.py disable --commit      # 恢复受限列表
```

**推荐流程**：先 `enable`（不提交），退出后看相机语言菜单是否展开；确认无误再
`enable --commit`。

### 4. 验证

断电重启，语言列表应保持完整；选择简体中文，再重启确认不掉回。

## 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `cannot enter service mode (rc=0x200F)` | 相机休眠了 | 半按快门唤醒，确认屏幕亮着、在拍摄界面 |
| `rc=0x2006` 参数错误 | 命令参数个数不对 | 应为"命令 + 4 个参数"，见 `pkt_params` |
| `camera reports an open session` (`0x201E`) | 上次会话没关 | 拔插 USB 或断电重启 |
| `no Nikon camera found` | 没绑 WinUSB，或相机没开机 | 检查 Zadig 绑定和相机电源 |
| `No backend available` | 找不到 libusb | `pip install libusb-package`，或把 `libusb-1.0.dll` 放到脚本同目录 |

读配置时如果 `flag[16]` 已经是 `0x01`，说明这台机器已经解锁过了。

## 风险与回退

- 改动范围：配置块中 1 个字节 + 末尾计数器自增
- 未提交的写入在断电后自动丢弃
- 回退：`python unlock.py disable --commit`
- 读回的配置块被相机遮蔽了大部分字段，**不是完整可还原镜像**，请保留 `read` 的备份

## 恢复相机驱动

设备管理器 → 找到相机 → 卸载设备（**不要**勾选"删除驱动程序软件"）→ 拔插一次 USB。
Windows 会自动装回原驱动，语言解锁状态不受影响。

## 致谢

方法来自 [summershrimp/NikonUnlock](https://github.com/summershrimp/NikonUnlock)
（面向 Z6/Z7 的公开实现）。本仓库是独立实现与说明，与其无隶属关系。

固件容器格式参考 [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)。

## 许可

- 代码：MIT
- 文档：CC BY 4.0

## 免责声明

修改相机配置存在风险，可能导致菜单异常或设置丢失。本项目仅记录一次个人研究过程，
不提供任何保证。请在自有设备上操作并自行承担后果。

本仓库不包含任何尼康固件、密钥或受版权保护的资源，与尼康公司无任何关联。

---

# English

Some regional Nikon bodies restrict the menu language to a few options (for
example, a US-market Z5 offers only English, Spanish, French and Portuguese).
This is **not** a firmware trim: one global firmware ships for all regions, and
the full list (31 languages, including Simplified Chinese) is already present in
the camera. A single configuration flag hides it.

This tool sets that flag through the camera's **service mode** interface and
commits it, which exposes the full language list.

**No firmware flashing, no hash bypass, no K8, no re-signing.**

## Compatibility

| Camera | Firmware | Status |
|---|---|---|
| Nikon Z5 | C 1.50 | ✅ Verified on hardware, persists after reboot |
| Nikon Z fc | C 1.81 | ✅ Verified on hardware, persists after reboot |
| Nikon Z6 / Z7 | C 3.80 | Verified by the upstream project (see Credits) |
| Other EXPEED 6 bodies | — | Untested; **confirm read-only before writing** |

## How it works

In the configuration block (about 131 KB), the byte at offset 16 is the
language-list switch:

| Value | Effect |
|---|---|
| `0x00` | Restricted list (regional default) |
| `0x01` | Full list (31 languages, including Simplified and Traditional Chinese) |

A write becomes persistent only after an explicit "commit"; without it, a power
cycle discards the change.

Full protocol and step-by-step procedure:
[docs/NIKON-REGION-LANGUAGE-UNLOCK.md](docs/NIKON-REGION-LANGUAGE-UNLOCK.md).

## Quick start

### 1. Requirements

- Windows, Python 3.10+
- Charged battery; USB cable plugged directly into a rear motherboard port
- Camera USB mode set to **MTP/PTP**

```powershell
pip install pyusb libusb-package
```

### 2. Bind the driver

Use [Zadig](https://zadig.akeo.ie/) to bind the camera to **WinUSB**:

1. Turn the camera on and connect USB
2. Zadig → **Options → List All Devices**
3. Select the camera (VID `04B0`), choose **WinUSB** → **Replace Driver**

The camera disappears from "Portable Devices" afterwards. That is expected.

### 3. Usage

```powershell
python unlock.py info                  # model and firmware (read-only)
python unlock.py read --out backup.bin # dump the configuration block (read-only)
python unlock.py enable                # stage flag=1, do not commit
python unlock.py enable  --commit      # stage and commit
python unlock.py disable --commit      # restore the restricted list
```

**Recommended flow**: run `enable` without `--commit`, exit, and check whether
the camera's language menu now shows the full list. Only then commit.

### 4. Verify

Power the camera off and on. The full list should persist. Select Simplified
Chinese and reboot again to confirm it sticks.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `cannot enter service mode (rc=0x200F)` | Camera is asleep | Half-press the shutter; make sure the screen is on and the camera is in shooting mode |
| `rc=0x2006` parameter error | Wrong parameter count | Must be "command + 4 arguments", see `pkt_params` |
| `camera reports an open session` (`0x201E`) | Previous session was not closed | Replug USB or power-cycle the camera |
| `no Nikon camera found` | Not bound to WinUSB, or camera off | Check the Zadig binding and camera power |
| `No backend available` | libusb not found | `pip install libusb-package`, or drop `libusb-1.0.dll` next to the script |

If `flag[16]` already reads `0x01`, the camera has been unlocked before.

## Risks and rollback

- Scope of change: one byte in the configuration block plus a trailing counter
- Uncommitted writes are discarded on power loss
- Rollback: `python unlock.py disable --commit`
- The block read back from the camera is **masked** and is **not** a full
  restorable image; keep the `read` backup anyway

## Restoring the camera driver

Device Manager → the camera → Uninstall device (**do not** tick "Delete the
driver software") → unplug and replug once. Windows reinstalls the original
driver; the language unlock is unaffected.

## Credits

Method from [summershrimp/NikonUnlock](https://github.com/summershrimp/NikonUnlock),
a public implementation for the Z6/Z7. This repository is an independent
implementation and write-up, not affiliated with it.

Firmware container format reference:
[WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool).

## License

- Code: MIT
- Documentation: CC BY 4.0

## Disclaimer

Modifying camera configuration carries risk, including menu malfunction or lost
settings. This project documents one personal research effort and provides no
warranty. Use it on your own hardware and at your own risk.

This repository contains no Nikon firmware, keys, or copyrighted assets, and is
not affiliated with Nikon Corporation.

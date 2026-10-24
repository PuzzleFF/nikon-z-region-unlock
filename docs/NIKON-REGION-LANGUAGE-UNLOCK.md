# 尼康 Z 系列区域语言锁：原理与解锁方法
# Nikon Z Region Language Lock: How It Works and How to Unlock It

[简体中文](#简体中文) · [English](#english)

---

# 简体中文

**适用** Nikon Z5 / Z fc（EXPEED 6），固件 C 1.50 / C 1.81 实测
**更新** 2026-10-24
**性质** 修改相机持久配置，不涉及固件刷写

## 摘要

部分地区的尼康机身把菜单语言限制为少数几种（例如美版 Z5 只有英/西/法/葡）。这个限制不是固件裁剪——同一个固件文件全球通用，完整语言列表（31 种，含简体中文）一直都在机身里，只是被一个配置标志屏蔽了。

通过相机的**服务模式**接口把该标志置 1 并提交，即可展开完整语言列表。全程只写入 **1 个字节**，不重签固件、不改哈希、不需要 K8。

方法来自开源项目 [summershrimp/NikonUnlock](https://github.com/summershrimp/NikonUnlock)（原用于 Z6/Z7），本文在 Z5 与 Z fc 上复现并验证。

## 一、原理

固件里的语言名池包含 31 种语言（`Čeština` … `中文(简体)` … `فارسی`），但菜单只显示配置允许的子集。该配置位于一个约 128 KB 的"配置块"中，**偏移 16 的 1 个字节**是开关：

| 值 | 效果 |
|---|---|
| `0x00` | 受限列表（地区默认） |
| `0x01` | 完整列表 |

写入后需要一次"提交"才会持久化；不提交的话，断电即恢复。

## 二、协议

走标准 PTP 容器，外层操作码是尼康私有的三个：

| 操作码 | 参数 | 作用 |
|---|---|---|
| `0x94FD` | `[cmd, a1, a2, a3]` | 发送内部命令（无数据） |
| `0x94FE` | 同上 + 1 字节数据 | 发送内部命令并写入数据 |
| `0x94FF` | 同上 | 发送内部命令并读回数据 |

内部命令（注意：命令 + 4 个参数）：

| 命令 | 参数 | 作用 |
|---|---|---|
| `0xF001` | — | 进入服务模式 |
| `0xF02D` | `(0, 0x1FFFC)` | 读配置块（实际返回 131,068 字节） |
| `0xF02E` | `(16, 1)` + 值 | 写偏移 16 的 1 字节 |
| `0xF030` | — | 提交 |
| `0xF002` | — | 退出服务模式 |

写入时配置块末尾 `0x1FFF8` 的 u32 会自增 1，属正常同步行为。

## 三、操作步骤

### 1. 准备

- Windows + Python 3.10+
- 相机电量充足，USB 直连主板后置口
- USB 模式设为 **MTP/PTP**
- 用 [Zadig](https://zadig.akeo.ie/) 把相机绑定到 **WinUSB**（可逆）

> 也可以完全走 WPD 不换驱动，但需要另一套传输层实现；本文的脚本用 libusb/WinUSB。

### 2. 只读确认

先确认相机支持这套协议、且配置块布局符合预期：

```python
enter = send(0x94FD, [0xF001, 0, 0, 0, 0])
data  = read(0x94FF, [0xF02D, 0, 0x1FFFC, 0, 0])
assert len(data) == 131068
print(data[16])          # 期望 0x00
```

### 3. 暂存（不提交）

```
write(0x94FE, [0xF02E, 16, 1, 0, 0], b"\x01")   # 相机应返回 params[1] == 1
read 后确认 data[16] == 0x01
```

此时**不要**发 `0xF030`。退出服务模式，检查相机菜单的语言列表是否展开——展开说明布局正确。

### 4. 提交

同一会话内重复写入并提交：

```
write(0x94FE, [0xF02E, 16, 1, 0, 0], b"\x01")
commit(0x94FD, [0xF030, 0, 0, 0, 0])
read 确认 data[16] == 0x01
退出服务模式
```

### 5. 验证

- 关机再开机
- 语言列表应保持完整
- 选择简体中文，再重启一次，确认菜单为中文且不掉回

## 四、实测结果

| 机型 | 固件 | 配置块大小 | `flag[16]` 初值 | 结果 |
|---|---|---|---|---|
| Z 5 | C 1.50 | 131,068 | `0x00` | ✅ 重启后保持，中文稳定 |
| Z fc | C 1.81 | 131,068 | `0x00` | ✅ 重启后保持，中文稳定 |

两机的配置块头部不同（`10 0f a4 0f` vs `10 0f b4 1c`），但偏移 16 的含义一致。

## 五、风险与回退

| 项 | 说明 |
|---|---|
| 改动范围 | 1 字节 + 末尾计数器 |
| 持久化 | 需显式提交；不提交则断电恢复 |
| 备份 | 读回的配置块**被相机遮蔽**了大部分字段，不是完整可还原镜像 |
| 回退 | 把偏移 16 写回 `0x00` 再提交 |
| 最坏情况 | 配置异常导致菜单故障；理论可回退，但没有完整镜像 |

**建议流程**：只读 → 暂存 → 看界面 → 再提交。每一步都可停在断电恢复的状态。

## 六、适用范围

已验证：Z5 C1.50、Z fc C1.81。
同代（EXPEED 6）的 Z6/Z7 由上游项目验证；Z30/Z50 未测试，但协议形态很可能相同。

不同固件版本的配置块布局可能变化，**换版本必须先只读确认偏移 16 的语义**。

## 七、参考与致谢

- [summershrimp/NikonUnlock](https://github.com/summershrimp/NikonUnlock) —— 方法来源，Z6/Z7 的公开实现
- Nikon 固件容器格式参考：[WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)

本文不包含任何尼康固件、密钥或受版权保护的资源。

## 八、免责声明

修改相机配置存在风险，可能导致菜单异常或设置丢失。本文仅记录一次个人研究过程，不构成任何保证。请在自有设备上操作，并自行承担后果；不建议用于商业用途或批量修改他人设备。

---

# English

**Applies to** Nikon Z5 / Z fc (EXPEED 6), tested on firmware C 1.50 / C 1.81
**Updated** 2026-10-24
**Nature** Modifies persistent camera configuration; no firmware is flashed

## Abstract

Some regional Nikon bodies restrict the menu language to a few options (for
example, a US-market Z5 offers only English, Spanish, French and Portuguese).
This is not a firmware trim: one global firmware ships for all regions, and the
full list (31 languages, including Simplified Chinese) is already present in
the camera. A single configuration flag hides it.

Setting that flag to 1 through the camera's **service mode** interface and
committing it exposes the full list. The whole change is **one byte**, with no
re-signing, no hash bypass and no K8.

The method comes from the open-source project
[summershrimp/NikonUnlock](https://github.com/summershrimp/NikonUnlock)
(written for the Z6/Z7); this document reproduces and verifies it on the Z5 and
Z fc.

## 1. How it works

The firmware contains a pool of 31 language names (`Čeština` … `中文(简体)` …
`فارسی`), but the menu only shows the subset the configuration allows. That
configuration lives in a "configuration block" of about 128 KB, and the byte at
**offset 16** is the switch:

| Value | Effect |
|---|---|
| `0x00` | Restricted list (regional default) |
| `0x01` | Full list |

A write becomes persistent only after a "commit"; without it, a power cycle
restores the previous state.

## 2. Protocol

Standard PTP containers carrying three Nikon-private outer opcodes:

| Opcode | Parameters | Purpose |
|---|---|---|
| `0x94FD` | `[cmd, a1, a2, a3]` | Send an internal command (no data) |
| `0x94FE` | same + 1 byte | Send an internal command with data |
| `0x94FF` | same | Send an internal command and read data back |

Internal commands (note: command + 4 arguments):

| Command | Parameters | Purpose |
|---|---|---|
| `0xF001` | — | Enter service mode |
| `0xF02D` | `(0, 0x1FFFC)` | Read the configuration block (131,068 bytes in practice) |
| `0xF02E` | `(16, 1)` + value | Write the byte at offset 16 |
| `0xF030` | — | Commit |
| `0xF002` | — | Leave service mode |

The u32 at `0x1FFF8` at the end of the block increments by one on each write;
that is normal synchronisation behaviour.

## 3. Procedure

### 1. Preparation

- Windows + Python 3.10+
- Charged battery, USB cable plugged directly into a rear motherboard port
- USB mode set to **MTP/PTP**
- Bind the camera to **WinUSB** with [Zadig](https://zadig.akeo.ie/) (reversible)

> A pure-WPD transport also works without changing the driver, but it needs a
> different implementation; the scripts here use libusb/WinUSB.

### 2. Read-only confirmation

Confirm the camera supports the protocol and the block layout matches:

```python
enter = send(0x94FD, [0xF001, 0, 0, 0, 0])
data  = read(0x94FF, [0xF02D, 0, 0x1FFFC, 0, 0])
assert len(data) == 131068
print(data[16])          # expect 0x00
```

### 3. Stage (do not commit)

```
write(0x94FE, [0xF02E, 16, 1, 0, 0], b"\x01")   # camera should return params[1] == 1
read back and confirm data[16] == 0x01
```

Do **not** send `0xF030` yet. Leave service mode and check whether the camera's
language menu now shows the full list; if it does, the layout is correct.

### 4. Commit

Repeat the write and commit within one session:

```
write(0x94FE, [0xF02E, 16, 1, 0, 0], b"\x01")
commit(0x94FD, [0xF030, 0, 0, 0, 0])
read back and confirm data[16] == 0x01
leave service mode
```

### 5. Verify

- Power the camera off and on
- The full list should persist
- Select Simplified Chinese, reboot again, and confirm the menu stays Chinese

## 4. Measured results

| Camera | Firmware | Block size | Initial `flag[16]` | Result |
|---|---|---|---|---|
| Z 5 | C 1.50 | 131,068 | `0x00` | ✅ Persists after reboot, Chinese stable |
| Z fc | C 1.81 | 131,068 | `0x00` | ✅ Persists after reboot, Chinese stable |

The two bodies have different block headers (`10 0f a4 0f` vs `10 0f b4 1c`),
but offset 16 means the same thing.

## 5. Risks and rollback

| Item | Notes |
|---|---|
| Scope | One byte plus the trailing counter |
| Persistence | Requires an explicit commit; otherwise a power cycle reverts |
| Backup | The block read back is **masked** by the camera and is not a full restorable image |
| Rollback | Write `0x00` at offset 16 and commit again |
| Worst case | Configuration corruption causing menu faults; rollback should work but there is no full image |

**Recommended flow**: read-only → stage → look at the menu → then commit. Every
step can stop in a state that a power cycle recovers.

## 6. Scope

Verified: Z5 C1.50, Z fc C1.81.
The same generation Z6/Z7 were verified by the upstream project; Z30/Z50 are
untested but likely use the same protocol.

Configuration layouts can change between firmware versions. **Always confirm the
meaning of offset 16 read-only before writing on a new version.**

## 7. References and credits

- [summershrimp/NikonUnlock](https://github.com/summershrimp/NikonUnlock) — the
  method's origin and a public implementation for the Z6/Z7
- Nikon firmware container format:
  [WonderLantern/nikon-fw-key-tool](https://github.com/WonderLantern/nikon-fw-key-tool)

This document contains no Nikon firmware, keys, or copyrighted assets.

## 8. Disclaimer

Modifying camera configuration carries risk, including menu malfunction or lost
settings. This document records one personal research effort and provides no
warranty. Use it on your own hardware at your own risk; it is not intended for
commercial use or for modifying devices you do not own.

#!/usr/bin/env python3
"""Unlock the full language list on Nikon Z-series bodies (EXPEED 6).

Writes ONE byte in the camera's configuration block and commits it.
No firmware is modified, no signature is bypassed.

尼康 Z 系列（EXPEED 6）完整语言列表解锁。

只写入相机配置块中的 1 个字节并提交，不修改固件、不绕过签名。

Tested on / 已验证: Nikon Z5 C 1.50, Nikon Z fc C 1.81.
Method from / 方法来源: https://github.com/summershrimp/NikonUnlock (Z6/Z7).

Requires / 依赖: Python 3.10+, pyusb, libusb, and the camera bound to
WinUSB (Zadig). / 以及用 Zadig 把相机绑定到 WinUSB。

Usage / 用法:
    python unlock.py info                 # model / firmware 机型与固件
    python unlock.py read  --out cfg.bin  # read config 读配置块
    python unlock.py enable               # stage flag=1, no commit 暂存不提交
    python unlock.py enable  --commit     # stage and commit 暂存并提交
    python unlock.py disable --commit     # restore flag=0 恢复受限列表

Read README.md before running. Modifying camera configuration is at your own
risk. / 运行前请阅读 README.md，修改相机配置风险自负。
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

try:
    import usb.core
    import usb.util
    import usb.backend.libusb1
except ImportError:
    sys.exit("pyusb is missing / 缺少 pyusb: pip install pyusb libusb-package")

NIKON_VID = 0x04B0
ITEM8_SIZE = 0x1FFFC
FLAG_OFFSET = 16


def backend():
    # Look for a libusb bundled by libusb-package (or dropped next to the
    # script) without importing that package, whose import can pull in
    # optional dependencies that are not always present.
    dll = {"win32": "libusb-1.0.dll", "darwin": "libusb-1.0.dylib"}.get(
        sys.platform, "libusb-1.0.so")
    here = pathlib.Path(__file__).resolve().parent
    for entry in [str(here), *sys.path]:
        for cand in (pathlib.Path(entry) / "libusb_package" / dll,
                     pathlib.Path(entry) / dll):
            if cand.is_file():
                return usb.backend.libusb1.get_backend(
                    find_library=lambda _, p=str(cand): p)
    return usb.backend.libusb1.get_backend()


def pkt_params(cmd, *args):
    if len(args) > 4:
        raise ValueError("at most four arguments / 最多 4 个参数")
    return [cmd, *args, *([0] * (4 - len(args)))]


class Camera:
    def __init__(self, dev, ep_out, ep_in):
        self.dev, self.ep_out, self.ep_in = dev, ep_out, ep_in
        self.tid = 1

    # -- transport -------------------------------------------------------
    def drain(self, rounds=8):
        for _ in range(rounds):
            try:
                self.dev.read(self.ep_in, 512, 200)
            except Exception:
                return

    def _read(self, timeout=6000):
        buf = self.dev.read(self.ep_in, 512, timeout)
        total = struct.unpack_from("<I", buf, 0)[0]
        while len(buf) < total:
            buf += self.dev.read(self.ep_in, 512, timeout)
        return buf[:total]

    def command(self, code, params=(), data=None):
        tid = self.tid
        self.tid += 1
        head = struct.pack("<IHHI", 12 + 4 * len(params), 1, code, tid)
        head += b"".join(struct.pack("<I", p) for p in params)
        self.dev.write(self.ep_out, head, 6000)
        if data is not None:
            dpkt = struct.pack("<IHHI", 12 + len(data), 2, code, tid) + data
            self.dev.write(self.ep_out, dpkt, 6000)
        payload = b""
        while True:
            pkt = self._read()
            length, ptype, rcode, _ = struct.unpack_from("<IHHI", pkt, 0)
            if ptype == 2:
                payload += pkt[12:]
                continue
            if ptype == 3:
                n = (length - 12) // 4
                return rcode, (list(struct.unpack_from(f"<{n}I", pkt, 12)) if n else []), payload
            return 0x2000, [], payload

    # -- session ---------------------------------------------------------
    def open_session(self):
        rc, _, _ = self.command(0x1002, [1])
        if rc == 0x201E:
            raise RuntimeError(
                "camera reports an open session / 相机会话未关闭; unplug/replug or power-cycle it")
        if rc != 0x2001:
            raise RuntimeError(f"OpenSession failed / 打开会话失败: 0x{rc:04X}")

    def close_session(self):
        try:
            self.command(0x1003)
        except Exception:
            pass


def find_camera(pid=None):
    be = backend()
    devs = [d for d in usb.core.find(find_all=True, backend=be)
            if d.idVendor == NIKON_VID and (pid is None or d.idProduct == pid)]
    for dev in devs:
        try:
            cfg = dev.get_active_configuration()
            intf = next((i for i in cfg if i.bInterfaceClass == 6), cfg[(0, 0)])
            usb.util.claim_interface(dev, intf.bInterfaceNumber)
            ep_out = ep_in = None
            for ep in intf:
                bulk = (ep.bmAttributes & 3) == 2
                if bulk and ep.bEndpointAddress & 0x80 and ep_in is None:
                    ep_in = ep.bEndpointAddress
                elif bulk and not ep.bEndpointAddress & 0x80 and ep_out is None:
                    ep_out = ep.bEndpointAddress
            if ep_out and ep_in:
                return dev, ep_out, ep_in
        except Exception:
            continue
    return None, None, None


def device_info(cam):
    rc, _, data = cam.command(0x1001)
    if rc != 0x2001 or len(data) < 12:
        return {}
    pos = 0

    def take(n):
        nonlocal pos
        v = data[pos:pos + n]
        pos += n
        return v

    def string():
        n = take(1)[0]
        return take(n * 2).decode("utf-16-le", "rstrip") if n else ""

    take(8)
    string()
    take(2)
    for _ in range(5):
        n = struct.unpack("<I", take(4))[0]
        take(n * 2)
    return dict(zip(("manufacturer", "model", "version", "serial"),
                    (string() for _ in range(4))))


def enter_service(cam):
    rc, p, _ = cam.command(0x94FD, pkt_params(0xF001))
    if rc != 0x2001 or not p or p[0] != 0x2001:
        raise RuntimeError(f"cannot enter service mode / 无法进入服务模式 (rc=0x{rc:04X}, {p})")


def exit_service(cam):
    try:
        cam.command(0x94FD, pkt_params(0xF002))
    except Exception:
        pass


def read_config(cam):
    rc, p, data = cam.command(0x94FF, pkt_params(0xF02D, 0, ITEM8_SIZE))
    if rc != 0x2001 or not p or p[0] != 0x2001:
        raise RuntimeError(f"config read failed / 读配置失败 (rc=0x{rc:04X}, {p})")
    if len(data) < FLAG_OFFSET + 1:
        raise RuntimeError(f"short config read / 读取长度不足: {len(data)} bytes")
    return data


def write_flag(cam, value):
    rc, p, _ = cam.command(0x94FE, pkt_params(0xF02E, FLAG_OFFSET, 1),
                           bytes([value]))
    if rc != 0x2001 or len(p) < 2 or p[1] != 1:
        raise RuntimeError(f"write not acknowledged / 写入未被确认 (rc=0x{rc:04X}, {p})")


def commit(cam):
    rc, p, _ = cam.command(0x94FD, pkt_params(0xF030))
    if rc != 0x2001 or (p and p[0] != 0x2001):
        raise RuntimeError(f"commit failed / 提交失败 (rc=0x{rc:04X}, {p})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("info", "read", "enable", "disable"))
    ap.add_argument("--out", default="config-backup.bin")
    ap.add_argument("--commit", action="store_true",
                    help="actually persist the change / 真正写入持久配置")
    ap.add_argument("--pid", type=lambda x: int(x, 0), default=None,
                    help="select camera by USB product id / 按 PID 选择相机, e.g. 0x0448")
    args = ap.parse_args()

    dev, ep_out, ep_in = find_camera(args.pid)
    if dev is None:
        sys.exit("no Nikon camera found / 未找到相机; is it bound to WinUSB?")

    cam = Camera(dev, ep_out, ep_in)
    cam.drain()
    cam.open_session()
    try:
        ident = device_info(cam)
        print(f"{ident.get('model','?')}  firmware {ident.get('version','?')}  "
              f"serial {ident.get('serial','?')}")

        if args.action == "info":
            return 0

        enter_service(cam)
        try:
            before = read_config(cam)
            print(f"config block: {len(before)} bytes, flag[16]=0x{before[FLAG_OFFSET]:02X}")

            if args.action == "read":
                pathlib.Path(args.out).write_bytes(before)
                print(f"saved to {args.out}")
                return 0

            target = 1 if args.action == "enable" else 0
            write_flag(cam, target)
            staged = read_config(cam)
            if staged[FLAG_OFFSET] != target:
                sys.exit("readback mismatch after write; nothing committed")
            print(f"staged flag[16]=0x{staged[FLAG_OFFSET]:02X}")

            if not args.commit:
                print("\nNOT committed. Power-cycle to discard. "
                      "Re-run with --commit to persist.")
                return 0

            commit(cam)
            after = read_config(cam)
            if after[FLAG_OFFSET] != target:
                sys.exit("post-commit readback mismatch")
            print("\nCOMMITTED. Power the camera off and on, then check the "
                  "language menu.")
        finally:
            exit_service(cam)
    finally:
        cam.close_session()
    return 0


if __name__ == "__main__":
    sys.exit(main())

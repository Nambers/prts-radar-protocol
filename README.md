# prts-radar-protocol

PRTS 雷达设备（广播名 `PRTSxxxx` / `DEPRTSxxxx`，RealMega RM1200）的 BLE 接口文档和调试控制台。
**非官方**，见下方[声明](#声明--disclaimer)。

- [`PROTOCOL.md`](PROTOCOL.md)：接口文档
- [`client/`](client/)：控制台

## 启动控制台

### 纯前端

在线版：https://ikuyo.dev/prts-radar-protocol/

```bash
cd client/web && pnpm install && pnpm dev:webble     # 打开 http://localhost:5173
```

### 带后端

Linux 上浏览器连不上这台设备，用这个：

```bash
pip install -r client/server/requirements.txt
(cd client/web && pnpm install && pnpm build)
python -m uvicorn app:app --app-dir client/server --port 8787     # 打开 http://127.0.0.1:8787
```

设备同一时间只接受一条连接。

## 声明 / Disclaimer

- 本项目是互操作性研究，**与厂商、鹰角网络（Hypergryph）无关联，未获授权，非官方**。
- 不含任何厂商产物：没有 APK、固件、反编译代码、密钥，也没有厂商的美术、logo、字体。
- 商标归各自权利人所有。
- **无担保。** 这些工具会对真实硬件写入，只在你自己的设备上用。部分命令不可逆。
- 如果你是相关权利人，认为本项目侵犯了你的权益，请提 issue 联系，核实后会尽快修改或下架。

Interoperability research. **Not affiliated with, endorsed by, or authorized by** the manufacturer
or Hypergryph. Contains no vendor artifacts. Trademarks belong to their respective owners.
**No warranty** — these tools write to real hardware; use them only on devices you own.
If you are a rights holder and believe this project infringes your rights, please open an issue;
it will be amended or taken down promptly once verified.

## 许可

[MIT](LICENSE)

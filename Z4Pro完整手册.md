# Quant Terminal · Z4Pro 完整手册

一份走完：**部署 → 手机远程访问 → 做成手机 App → 日常运维**。
所有参数已按 Z4Pro 写死，不用再判断架构。

---

## 〇、你的机型结论（已核实）

| 项目 | 结论 |
| --- | --- |
| CPU | 标准版 N97 / 性能版 i3-N305（新款 Z4Pro+ 为 N150 / N355） |
| 架构 | **x86_64**，构建选 `linux/amd64` |
| AVX2 | **全系支持** → **不需要 legacy-cpu** ✅ |
| 内存 | 8GB / 16GB，够用 |
| Docker | 官方支持 |

> 老款 Z4（J4125）才需要 `legacy-cpu`，你这款免了。

---

## 一、电脑上构建镜像

极空间面板**不支持从源码构建**，所以先在电脑上打成一个 tar 再导入。
**全程不用开 SSH**（开了会失去官方售后）。

1. 装好 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 并启动
2. 解压 `QuantTerminal-定制版.zip`
3. 运行专用脚本：

| 系统 | 操作 |
| --- | --- |
| Windows | 双击 **`zspace/build-z4pro.bat`** |
| macOS / Linux | 终端执行 `bash zspace/build-z4pro.sh` |

> ⚠️ Windows 上脚本文件名**必须用英文** `build-z4pro.bat`。
> 中文文件名的 .bat 在 CMD 下容易因编码问题报「不是内部或外部命令」。

脚本**不问任何问题**（架构和依赖已写死），直接开跑。
等 **15~40 分钟**，得到 **`quant-terminal.tar`**（约 2~3GB）。

---

## 二、导入并部署到极空间

**① 传 tar** → 上传到极空间任意文件夹（如 `Docker/`）

**② 导入镜像**
Docker → **镜像** → **本地镜像** → **导入镜像** → **从极空间导入** → 选 tar
（3~10 分钟，完成后列表出现 `quant-terminal:latest`）

**③ 建数据目录**
文件管理 → `Docker` → 新建 `quant-terminal` → 里面再建 `data`

**④ 改配置**
打开 `zspace/docker-compose.yml`，改**两处**：

- `请替换成极空间真实路径/data` → 真实路径
  别猜：面板里有「查询路径」按钮，进 `Docker/quant-terminal/data` 复制，形如
  `/tmp/zfsv3/sata11/XXXXXX/data/Docker/quant-terminal/data`
- `AUTH_PASSWORD=请改成你自己的密码` → 你自己的密码（≥6 位）

可选：填 `TICKFLOW_API_KEY=` 解锁实时行情；填 `AI_API_KEY=`（DeepSeek）启用 AI 策略生成。

改完把这个 yml 上传到 `Docker/quant-terminal/`。

**⑤ 部署**
Docker → **Compose** → **新增项目**
→ 项目名 `quant-terminal`
→ 存储位置选 `Docker/quant-terminal`
→ 添加方式选**从本地导入** → 勾 `docker-compose.yml` → 确定 → 部署

状态变**「运行中」**即成功。打开 **`http://极空间内网IP:3018`**。

---

## 三、首次使用清单

1. 用你设的 `AUTH_PASSWORD` 登录
2. **设置 → 凭据与能力 → 重新检测**
3. **设置 → 立即跑盘后管道**（第一次拉历史日 K，几分钟）
4. **自选**加票 → **策略**点卡片扫全 A 股 → **回测**看净值
5. **监控中心**配规则，盘中弹窗 + 飞书推送

免费档当日数据**盘后 1~2 小时**更新，正常。

---

## 四、手机远程访问（不在家也能用）

极空间限制 3000 以下端口外部访问，**3018 刚好在限制之外** ✅，无需改端口。

| 方案 | 成本 | 速度 | 依赖 |
| --- | --- | --- | --- |
| **① 官方远程** | 免费 | 约 6MB/s | 手机装极空间 App |
| **② Tailscale** | 免费 | **打洞成功跑满上行** | 手机装 Tailscale App |
| ③ 节点小宝 | 免费5GB/月 | 中 | 浏览器直开 |
| ④ 云服务器 | ¥60~100/月 | 稳定 | 无 |

**建议：今天先用 ①，顺手了配 ②。** 两者不冲突可并存。

### 方案 ① 官方远程（零配置）

Docker → 找到 `Quant_Terminal` 容器 → 点「**远程访问 / 快捷方式**」
→ 添加（端口 3018）→ 手机装**极空间 App** 同账号登录 → 点开即用。

不用公网 IP、不用端口映射。
⚠️ 限制：只能在极空间 App 内打开，无法用 Safari 访问。

### 方案 ② Tailscale（长期最优）

装好后手机在任何地方访问 `http://192.168.x.x:3018` 都跟在家一样，
**点对点直连、免费无限流量**，而且**能用 Safari 做 PWA 全屏 App**。

**步骤：**

1. [tailscale.com](https://tailscale.com) 注册 → [Keys 页](https://login.tailscale.com/admin/settings/keys)
   → Generate auth key → 勾 **Reusable** → 复制（只显示一次）
2. 极空间 Docker → 镜像 → 仓库 → 自定义拉取 `tailscale/tailscale:latest`
3. 添加到容器，按下面填：

| 配置项 | 值 |
| --- | --- |
| 网络 | **host 模式**（必须） |
| 文件夹 | `Docker/tailscale/var/lib` → `/var/lib`<br>`Docker/tailscale/dev/net/tun` → `/dev/net/tun` |
| `TS_AUTHKEY` | 你复制的 key |
| `TS_ROUTES` | `192.168.1.0/24`（改成你家网段） |
| `TS_STATE_DIR` | `/var/lib/tailscale` |
| 能力 | `NET_ADMIN`、`SYS_MODULE` |

> 也可直接用现成配置 `zspace/docker-compose-tailscale.yml`。

4. 手机 App Store 装 **Tailscale**，同账号登录
5. [管理后台](https://login.tailscale.com/admin/machines) → 找到极空间
   → **Edit route settings** → Approve 那条 `192.168.1.0/24`
   → 顺手关掉 **Key expiry**（否则几个月后自动掉线）

---

## 五、做成手机 App

### 方式 A：PWA（今天就能用，零成本）✅

已经给前端加好完整 iOS 全屏支持（图标、无地址栏、独立窗口）。

**iPhone 上 30 秒**（必须用 **Safari**）：
1. Safari 打开 `http://你的服务地址:3018`
2. 点底部**分享** ↑
3. 下滑找「**添加到主屏幕**」→ 添加
4. 桌面出现图标，点开就是全屏 App

> 配合 Tailscale，出门在外也能用这个图标直接进。

### 方式 B：原生壳 App（需 Mac 编译）

已写好完整 Xcode 工程（SwiftUI + WKWebView），功能：
全屏沉浸式（延伸到刘海下）、下拉刷新、**面容解锁**、原生设置页、中文网络兜底页。

**没有 Mac 的三条路：**

| 方式 | 成本 |
| --- | --- |
| GitHub Actions 自动打包 | 需 ¥688/年开发者账号 |
| 云 Mac 租一天 | ¥30~100 |
| 发给有 Mac 的朋友代编译 | 0 |

编译只需改 `ios/QuantTerminal/Config.swift` 里的 `defaultServerURL`。

**必须说明**：不是把 16 万行代码重写成 Swift（后端是 Python + Polars 引擎，iOS 跑不了）。
壳 App 用 WKWebView 承载网页，这是保住全部 25 个策略、68 列指标、回测引擎的唯一可行方案。

---

## 六、可选：部署到云服务器

不想依赖家里 NAS 开机，就搬云上。一台 Ubuntu VPS 上一条命令：

```bash
sudo bash deploy-cloud.sh
```

腾讯云/阿里云轻量 2核4G 约 ¥60~100/月。装完配个域名 + HTTPS（Caddy 一条命令自动签证书）。

---

## 七、运维与安全

### 常用操作
面板里直接点：启动 / 停止 / 重启 / 日志。改了配置后要点「重新启动」。

### 更新
1. 电脑重跑构建脚本，生成新 tar
2. 极空间导入新 tar（覆盖同名镜像）
3. Compose 项目点「重新启动」

### 三条红线 🔴

1. **`AUTH_PASSWORD` 必须设** —— 一旦能外网访问，没密码等于把持仓和策略挂公网上
2. **更新前先备份 `Docker/quant-terminal/data`** —— 自选、策略、监控记录全在这里
3. **绝对不要执行 `git clean -fdx`** —— 会连数据一起删掉

### 安全建议
优先用 Tailscale / 官方远程这类**加密隧道**，
**不要直接把 3018 端口映射到公网**——会被自动化扫描盯上。

### Z4Pro 专属提示
- 有 2 个 M.2 插槽，把 `Docker` 目录放**固态**上，启动和读写快很多，也不吵机械盘
- 官方不支持 PCIe 4.0，买便宜的 PCIe 3.0 固态即可
- **别开 SSH**，本方案全程用不到，开了失去官方软件售后

---

## 附：文件导航

| 文件 | 用途 |
| --- | --- |
| `zspace/build-z4pro.bat` | 一键构建镜像（纯英文，避免编码问题） |
| `zspace/docker-compose.yml` | Z4Pro 专用部署配置 |
| `zspace/docker-compose-tailscale.yml` | 手机异地访问 |
| `deploy-cloud.sh` | 云服务器部署 |
| `ios/` | 原生壳 App 工程源码 |
| `frontend/public/manifest.json` + `icon-*.png` | PWA 图标与配置 |
| `定制说明.md` | 品牌改造说明（改名/换 Logo/配色） |
| `操作说明书.md` | 项目原版功能文档 |

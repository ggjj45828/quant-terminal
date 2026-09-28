# GitHub 云端构建指南（GitHub Desktop 版）

本地 Docker 装不了 / 拉不动镜像？让 GitHub 的服务器免费帮你构建，极空间直接从云端拉。

> 本机**不用装 Docker、不用装 WSL、不用开 BIOS 虚拟化**，构建时还能关机睡觉。

---

## ⚠️ 为什么要装 GitHub Desktop

项目有 **920 个文件**，而 GitHub 网页端的「Upload files」**一次最多只能传 100 个**。
所以网页拖拽这条路走不通，必须用 **GitHub Desktop**（图形界面，全程点鼠标，不用敲命令）。

---

## 重要前提：仓库设为 Public

**是的，源码会公开。** 但不用担心：

- 项目本来就是 **MIT 开源**，公开没问题
- 我帮你改的只是品牌名和配色，没有你的私密信息
- **`.env`（密码、API Key）和 `data/`（自选、策略）已被 `.gitignore` 自动排除，不会上传** ✅

> Public 是为了让极空间能**免密拉取**镜像。Private 的话极空间要额外配认证，很麻烦。

---

## 六步操作

### 第 1 步：注册 GitHub + 装 GitHub Desktop

1. 打开 [github.com](https://github.com) 注册账号（免费），验证邮箱
2. 下载 [GitHub Desktop](https://desktop.github.com) 并安装
3. 打开 GitHub Desktop → **Sign in to GitHub.com** → 用浏览器登录授权

---

### 第 2 步：把源码文件夹变成 Git 仓库

1. GitHub Desktop 左上角 **File** → **Add local repository**（中文：文件 → 添加本地仓库）
2. **Choose...** 选你的源码文件夹 `tickflow-stock-panel`
3. 如果弹出提示 **"this directory does not appear to be a Git repository"**（这不是 Git 仓库）
   → 点 **create a repository**（创建仓库）

填写：

| 项 | 填什么 |
| --- | --- |
| **Name** | `quant-terminal` |
| **Description** | 随便，可留空 |
| **Local path** | 保持默认（就是你选的文件夹） |
| **Git ignore** | 选 **None**（项目已有自己的 .gitignore） |
| **License** | 选 **None**（项目已有 MIT LICENSE） |
| ⚠️ Initialize with README | **不勾**（仓库里已有 README.md） |

点 **Create repository**。

---

### 第 3 步：发布到 GitHub

1. 顶部出现蓝色的 **Publish repository**（发布仓库）按钮，点它
2. 弹窗里：

| 项 | 填什么 |
| --- | --- |
| Name | `quant-terminal` |
| Description | 可留空 |
| ⚠️ **Keep this code private** | **取消勾选** ← 关键！不勾才是 Public |

3. 点 **Publish repository**

上传 920 个文件要几分钟，右下角转圈结束就好。

**验证一下**：去 github.com 打开你的仓库，确认能看到 `Dockerfile`、`backend/`、`frontend/`。
并且确认**看不到 `.env`**（看到的话立刻删掉）。

---

### 第 4 步：触发云端构建

1. 打开你的仓库页面 → 顶部点 **Actions**
2. 第一次会提示 "I understand my workflows, go ahead and enable them" → 点它启用
3. 左侧列表点 **Build Z4Pro Image**
4. 右侧点 **Run workflow** → 再点绿色 **Run workflow**
5. 页面刷新，出现一个正在跑的任务，点进去能看实时日志

**构建 15~30 分钟。** 期间可以关网页、关电脑。

---

### 第 5 步：构建完成后，把镜像设为 Public

构建成功（绿色 ✅）后：

1. 点 GitHub 右上角**头像** → **Your profile**
2. 顶部标签点 **Packages** → 点 `quant-terminal`
3. 右侧 **Package settings** → 拉到底 **Danger Zone**
   → **Change visibility** → 选 **Public** → 输入包名确认

**你的镜像地址是：**
```
ghcr.io/你的用户名/quant-terminal:latest
```
> 用户名看浏览器地址栏 `github.com/` 后面那段。**必须全小写。**

---

### 第 6 步：极空间拉取镜像

1. 极空间 **Docker** → **镜像** → **仓库** → **自定义拉取**
2. 填：
   ```
   ghcr.io/你的用户名/quant-terminal:latest
   ```
3. 确定，等拉取完成

镜像到手后，回到 `Z4Pro完整手册.md` 从「**③ 建数据目录**」继续
（**跳过"导入 tar"**，你已经是直接拉镜像了）。

---

## 以后怎么更新

改了代码（换品牌名、改配色等）：

1. GitHub Desktop 会自动检测到改动
2. 左下角填 Summary（随便写，如 `update`）→ 点 **Commit to main**
3. 顶部点 **Push origin**（推送到 GitHub）
4. 网页 **Actions** → **Run workflow** 重新构建
5. 极空间重新拉一次镜像，容器重启

**数据在极空间的 `data` 文件夹里，不受影响，不用重新配置。**

---

## ⚠️ 已修复：TS2307 Cannot find module（重要）

如果你第一次构建报了这个错：

```
TS2307: Cannot find module '@/components/screener/StrategyStoreDialog'
```

**原因**：我最初给你的源码包解压时损坏了，少了 3 个文件、另有几个文件被截断。
**已修复**：本包已用上游源码全新重建并校验（全部文件齐全、大小逐一对齐、本地导入 0 失败）。

**如果你之前已经把旧包传上 GitHub 了**，请这样做：

1. 下载本修复包，解压后**整体覆盖**你本地的 `D:\tickflow-stock-panel` 文件夹
   （所有文件都选「替换」）
2. 打开 **GitHub Desktop**，会自动列出改动（几百个）
3. Summary 填 `fix` → **Commit to main** → **Push origin**
4. 回到网页 **Actions** → **Build Z4Pro Image** → **Run workflow** 重新构建

---

## 常见问题

**Q：Actions 里找不到 "Build Z4Pro Image"？**
A：确认 `.github/workflows/build-z4pro.yml` 上传上去了。
它是**隐藏文件夹**里的文件，GitHub Desktop 会自动包含，但如果你手动挑过文件可能漏掉。

**Q：构建失败？**
A：点进任务看日志，把红色报错最后 20 行发我。

**Q：极空间拉取失败 / 要登录？**
A：两种可能——
1. 镜像还是 Private → 回去做第 5 步
2. 极空间强制认证 → 用户名填 GitHub 用户名，密码填 **Personal Access Token**
   （GitHub → Settings → Developer settings → Personal access tokens → Tokens(classic)
   → Generate new token → 勾 `read:packages`）

**Q：不想公开源码？**
A：可以设 Private，但极空间拉取要配一次 PAT 认证。要的话我单独写步骤。

**Q：GitHub Desktop 里没看到我的改动？**
A：左下角 Changes 标签会列出改动文件。如果 `.env` 出现在里面，说明 gitignore 没生效，
   右键它 → **Ignore file** 排除掉。

---

## 附录：消除「915 个文件全部 changed」的假改动（可选）

首次提交时 GitHub Desktop 显示几百个文件待提交，这是**正常的**（首次要把所有文件加进仓库）。

但如果你看到很多文件的 diff 只是 **`LF → CRLF`**，这是 Windows 上 Git 自动转换行符造成的
**假改动**，不影响构建，但看着吓人。想消除的话：

1. 我已放好 `.gitattributes`（统一 LF，`.bat` 单独用 CRLF）
2. 在**源码文件夹**里打开命令行，依次执行：
   ```
   git config core.autocrlf false
   git rm --cached -r .
   git reset --hard
   ```
3. 回到 GitHub Desktop，改动数会大幅减少

> 不做也行。GitHub Actions 在 **Linux** 上跑，换行符不影响 Docker 构建。
> 这一步纯粹是为了界面清爽。

---

## 附：本地 Docker 想修好的话（可选）

如果以后想用本地构建，管理员 PowerShell 里：
```powershell
wsl --install
```
重启 → 开 Docker Desktop → 双击 `build.bat`。

但**不急**，云端这条路现在就能走通。

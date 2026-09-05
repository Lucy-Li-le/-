# Proof of Growth · 成长印记

Proof of Growth 是一个把“今天发生的一点小事”整理成成长卡的轻量应用：AI 帮用户看见进步，LocalStorage 保留个人记录，用户可以选择把成长卡的 Hash 写入 Monad Testnet，留下可验证的时间印记。

## 当前版本

- 前端：原生 HTML / CSS / JavaScript，无构建工具。
- AI：服务端调用 Dify Workflow API；浏览器不会接触 `DIFY_API_KEY`。
- 链上：OKX Wallet / EIP-1193，Monad Testnet，Chain ID `10143`。
- 隐私：链上只保存成长卡 Hash，不保存聊天原文；本地演示记录保存在浏览器 LocalStorage。
- 参赛约束：本仓库为比赛开始后新建的参赛版本；旧项目仅作为赛前练习，不复制旧 Git 历史。

## 本地启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python .\server.py
```

打开 <http://127.0.0.1:8080/>。

没有配置 `DIFY_API_KEY` 时，接口会返回安全的未配置状态，前端自动使用本地模拟数据，页面仍可独立演示。

如果要调用 Dify，把真实 Key 只写入本机 `.env`：

```text
DIFY_API_KEY=你的Dify Workflow API Key
```

`.env` 已被 `.gitignore` 排除，不能提交到 GitHub。

## 合约配置

部署新的 `contracts/GrowthProof.sol` 后，把完整合约地址填入 `contract-config.js` 的 `address` 字段。不要填写私钥、助记词或 API Key。

部署前确认：

- Wallet：OKX Wallet
- Network：Monad Testnet
- Chain ID：`10143`
- Value：`0 wei`

前端会对成长卡内容做 SHA-256，得到 `bytes32`，再调用 `recordGrowth(bytes32)`。钱包弹窗和交易确认由用户本人审核。

## Vercel 公网部署

1. 登录 Vercel，选择从 GitHub 导入本仓库。
2. Framework Preset 选择 `Other`，Build Command 留空，Output Directory 留空。
3. 在 Vercel 项目 `Settings → Environment Variables` 添加：

   ```text
   DIFY_API_KEY = 真实 Dify API Key
   ```

4. 重新部署，并在公网域名测试 AI 生成、钱包连接和上链按钮。

真实 API Key 只存在 Vercel 环境变量中，不写前端、不写 GitHub、不放浏览器请求体。

## 发布前安全检查

在仓库根目录执行：

```powershell
git status --short
rg -n --hidden -g '!*.png' -g '!*.jpg' -g '!.git' "DIFY_API_KEY|Authorization|Bearer |sk-|app-[A-Za-z0-9]" .
```

预期结果：只有 `.env.example` 的变量名和服务端代码中的环境变量读取，不应出现真实 Key、Bearer 值、私钥或助记词。

## 商业模式说明

### 用户价值

很多人的成长不是缺少努力，而是缺少一个能把微小行动重新看见的地方。Proof of Growth 用低压力的 AI 对话帮助用户完成“记录—理解—留下证据”这条最短路径。

### 初期模式

- 免费体验：每天生成有限数量的成长卡，保存到本地。
- 进阶服务：提供更长周期的成长回顾、主题化模板和个人成长报告。
- 社群/活动版：为黑客松、训练营和学习社群提供匿名化成长墙或阶段勋章。
- 链上价值：链上保存的是 Hash 和时间，不出售投机资产；它用于证明记录在某个时间点已经存在。

### 成本与边界

Dify 调用按实际服务额度产生成本，Vercel 使用平台额度；链上交易消耗 Monad Testnet 测试币。AI 输出仅作为自我记录草稿，不替代专业咨询或重要决策。

## 演示路径

1. 输入今天发生的事情。
2. 点击「和 AI 聊聊」，查看 AI 回复和成长卡。
3. 点击「保存成长记录」，验证 LocalStorage 记录。
4. 点击「连接钱包」，确认 OKX Wallet 为 Monad Testnet。
5. 点击「上链存证」，审核钱包弹窗后确认交易。
6. 点击 Monadscan 链接，展示交易结果。


const REQUIRED_FIELDS = ["emotion", "reply", "growth_title", "growth_summary"];
const CONTRACT_ABI = [
  "function recordGrowth(bytes32 growthHash)",
  "function getGrowthCount(address user) view returns (uint256)",
  "function getGrowthHash(address user, uint256 index) view returns (bytes32)",
];

const $ = (id) => document.getElementById(id);
let currentGrowth = null;
let currentMessage = "";
let currentHash = "";
let generating = false;
let walletAddress = "";

function localMock(userMessage) {
  const trimmed = userMessage.trim();
  return {
    emotion: "认真而勇敢",
    reply: `你没有等到完全准备好才开始。今天，你已经把“想做”变成了一个具体动作：${trimmed.slice(0, 42)}${trimmed.length > 42 ? "……" : ""}`,
    growth_title: "我为自己的下一步留下了证据",
    growth_summary: "面对陌生的 Web3 和 Monad，我完成了新的尝试，也更清楚下一步要往哪里走。",
  };
}

function validateGrowth(value) {
  let result = value;
  if (typeof result === "string") {
    try { result = JSON.parse(result); } catch { throw new Error("AI 返回格式不正确"); }
  }
  if (!result || typeof result !== "object") throw new Error("AI 返回格式不正确");
  const missing = REQUIRED_FIELDS.filter((field) => typeof result[field] !== "string" || !result[field].trim());
  if (missing.length) throw new Error(`AI 返回缺少字段：${missing.join("、")}`);
  return Object.fromEntries(REQUIRED_FIELDS.map((field) => [field, result[field].trim()]));
}

async function generateGrowth(userMessage) {
  const message = String(userMessage || "").trim();
  if (!message) throw new Error("请先写下今天发生的内容");

  let response;
  try {
    response = await fetch("/api/growth", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ user_message: message }),
    });
  } catch {
    throw new Error("暂时无法连接服务，请稍后再试");
  }

  let payload = {};
  try { payload = await response.json(); } catch { /* handled below */ }

  if (!response.ok) {
    if (payload.code === "DIFY_API_KEY_NOT_CONFIGURED" || payload.fallback === true) {
      return validateGrowth(localMock(message));
    }
    throw new Error([payload.code, payload.message].filter(Boolean).join("：") || `请求失败（HTTP ${response.status}）`);
  }
  return validateGrowth(payload);
}

window.generateGrowth = generateGrowth;

function showError(message) {
  const element = $("errorMessage");
  element.textContent = message;
  element.hidden = !message;
}

function renderGrowth(growth) {
  $("aiReply").textContent = `“${growth.reply}”`;
  $("emotionBadge").textContent = `今日情绪：${growth.emotion}`;
  $("growthTitle").textContent = growth.growth_title;
  $("growthSummary").textContent = growth.growth_summary;
  $("growthDate").textContent = new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
  $("saveGrowthBtn").disabled = false;
  $("onchainBtn").disabled = false;
}

function setGenerating(value) {
  generating = value;
  const button = $("talkBtn");
  button.disabled = value;
  button.textContent = value ? "整理中……" : "和 AI 聊聊";
}

function saveLocalRecord(extra = {}) {
  if (!currentGrowth) return;
  const records = JSON.parse(localStorage.getItem("proof-of-growth-records") || "[]");
  records.unshift({
    ...currentGrowth,
    user_message: currentMessage,
    created_at: new Date().toISOString(),
    ...extra,
  });
  localStorage.setItem("proof-of-growth-records", JSON.stringify(records.slice(0, 100)));
}

async function sha256Hex(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return `0x${Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
}

async function ensureMonadNetwork() {
  if (!window.ethereum) throw new Error("未检测到浏览器钱包，请安装并解锁 OKX Wallet");
  const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
  const chainId = await window.ethereum.request({ method: "eth_chainId" });
  const numericChainId = Number.parseInt(chainId, 16);
  if (numericChainId !== 10143) {
    throw new Error(`当前不是 Monad Testnet（检测到 Chain ID ${numericChainId}）`);
  }
  walletAddress = accounts[0] || "";
  $("networkStatus").textContent = `${walletAddress.slice(0, 6)}…${walletAddress.slice(-4)} · Monad`;
  $("connectWalletBtn").textContent = "钱包已连接";
  return walletAddress;
}

async function connectWallet() {
  showError("");
  try { await ensureMonadNetwork(); }
  catch (error) { showError(error.message || "钱包连接失败"); }
}

async function writeGrowthOnchain() {
  if (!currentGrowth) throw new Error("请先生成一张成长卡");
  const config = window.GROWTH_PROOF_CONFIG || {};
  if (!/^0x[a-fA-F0-9]{40}$/.test(config.address || "")) {
    throw new Error("尚未配置新的 GrowthProof 合约地址");
  }
  await ensureMonadNetwork();
  if (!window.ethers) throw new Error("钱包组件尚未加载完成，请刷新页面再试");

  const canonical = JSON.stringify({
    user_message: currentMessage,
    emotion: currentGrowth.emotion,
    reply: currentGrowth.reply,
    growth_title: currentGrowth.growth_title,
    growth_summary: currentGrowth.growth_summary,
  });
  currentHash = await sha256Hex(canonical);
  const provider = new window.ethers.BrowserProvider(window.ethereum);
  const signer = await provider.getSigner();
  const contract = new window.ethers.Contract(config.address, CONTRACT_ABI, signer);
  const transaction = await contract.recordGrowth(currentHash);
  $("localStatus").textContent = "交易已提交，等待 Monad Testnet 确认……";
  await transaction.wait();
  saveLocalRecord({ growth_hash: currentHash, tx_hash: transaction.hash, contract_address: config.address });
  $("localStatus").textContent = "已保存本地记录，并完成链上存证。";
  $("chainResult").hidden = false;
  const txLink = $("txLink");
  txLink.href = `${config.explorerUrl || "https://testnet.monadscan.com"}/tx/${transaction.hash}`;
  txLink.textContent = `查看交易 ${transaction.hash.slice(0, 10)}…`;
}

$("talkBtn").addEventListener("click", async () => {
  if (generating) return;
  const message = $("userMessage").value.trim();
  showError("");
  if (!message) { showError("请先写下今天发生的内容"); $("userMessage").focus(); return; }
  setGenerating(true);
  try {
    const growth = await generateGrowth(message);
    currentMessage = message;
    currentGrowth = growth;
    renderGrowth(growth);
    $("localStatus").textContent = "成长卡已生成，是否保存由你决定。";
  } catch (error) {
    showError(error.message || "生成失败，请稍后再试");
  } finally {
    setGenerating(false);
  }
});

$("saveGrowthBtn").addEventListener("click", () => {
  saveLocalRecord();
  $("localStatus").textContent = "已保存到当前浏览器的 LocalStorage。";
});

$("connectWalletBtn").addEventListener("click", connectWallet);
$("onchainBtn").addEventListener("click", async () => {
  const button = $("onchainBtn");
  button.disabled = true;
  showError("");
  try { await writeGrowthOnchain(); }
  catch (error) { showError(error.message || "上链失败"); }
  finally { button.disabled = !currentGrowth; }
});

window.addEventListener("load", () => {
  $("growthDate").textContent = new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
  if (window.ethereum) {
    window.ethereum.on?.("accountsChanged", () => { $("networkStatus").textContent = "请重新连接钱包"; });
    window.ethereum.on?.("chainChanged", () => { $("networkStatus").textContent = "网络已变化，请检查 Monad Testnet"; });
  }
});


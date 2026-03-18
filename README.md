# ⚡ GALCA (Grid Asset Lifecycle Cost Agents)

**电网资产全生命周期成本多智能体智能分析平台**
n🌍 **Live Demo 在线体验**: [http://149.129.217.7:8080](http://149.129.217.7:8080)


![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)
![Vue3](https://img.shields.io/badge/Frontend-Vue%203-4FC08D)
![SQLite](https://img.shields.io/badge/Database-SQLite-003B57)
![LangGraph](https://img.shields.io/badge/Multi--Agent-LangGraph-orange)
![Gemini](https://img.shields.io/badge/LLM-Gemini_1.5_Flash-green)

GALCA 是一个专为复杂工业与电网场景设计的**多智能体协作系统 (Multi-Agent System)**。它能够自主摄取异构文件（文本合同、台账表格、现场工单扫描件），利用视觉大模型 (Vision-LLM) 进行零样本提取，并通过有向无环图 (DAG) 将清洗后的数据流转至机器学习引擎，完成资产成本的拟合与趋势预测。

---

## 🚀 架构演进与极简部署 (V2.0)

本项目已从早期的单机 Streamlit 玩具，全面重构为**现代化前后端分离但极度轻量的工业级全栈架构**。特别针对**低配云服务器 (如 1核2G)** 进行了极限内存优化。

- **🖥️ 极简前端 (Frontend)**：基于 Vue 3 + Element Plus + ECharts。抛弃了沉重的 Node.js/Webpack 编译链，采用纯静态 CDN 注入的单文件 (`index.html`) 部署，内存占用几乎为零！
- **⚙️ 异步后端 (Backend)**：基于 FastAPI 构建高性能 REST API，利用 `BackgroundTasks` 异步调度耗时的 LangGraph 视觉大模型提取任务，拒绝请求超时。
- **💾 本地化存储 (Database)**：内置 SQLite 配合 SQLAlchemy ORM，自动沉淀大模型解析出的所有结构化台账，支持千万级历史回溯分析。

---

## ✨ 核心技术特性 (Key Features)

1. 📄 **万象文件摄取与智能容错 (V2.1 增强)**：支持 `.xlsx`, `.csv`, `.txt`, `.pdf`, `.jpg`, `.png` 等。增强的清洗逻辑可自动识别并兼容非标表头（如“用途/电压等级”、“规格/型号”等），将复杂财务文本自动洗录为标准化数值。
2. 👁️ **无 OCR 多模态提取**：摒弃传统脆弱的 OCR，直接利用 Gemini 的视觉编码器（Vision Encoder）理解图片工单的关键财务指标。
3. 🧠 **LangGraph 结构化流转**：利用 StateGraph 构建严谨的节点流转网络（提取 -> 清洗 -> 拟合 -> 报告），具备高容错率。
4. 📈 **无头数学拟合预测 (Headless Forecasting)**：无缝集成 `scikit-learn`，支持多项式回归与随机森林，并在后端以无头模式 (Agg) 极速生成预测折线，捕捉清洗后历史台账的非线性成本趋势。
5. 🎛️ **全动态仪表盘 (Dynamic Dashboard)**：前端具备状态感知（黄条加载、绿条完成）。支持从 SQLite 库中自动枚举识别到的设备，并提供图表与表格的**全局实时联动筛选**功能，满足管理员多设备分析需求。

---

## 🏗️ 系统数据流向

```text
[浏览器前端拖拽 Excel/JPG]
       │ (HTTP POST /api/v1/upload)
       ▼
[FastAPI 异步接收并存盘] ──► 返回 200 OK (前端不阻塞)
       │
       ▼ (触发 BackgroundTasks)
[LangGraph 智能体网络]
   ├─ 1. Universal Loader (加载异构数据)
   ├─ 2. Extraction Node (Gemini 强制输出 Pydantic JSON)
   └─ 3. Analytics Node (Scikit-learn 清洗与多项式拟合)
       │
       ▼ (SQLAlchemy)
[SQLite 数据库 (galca.db)] ◄── Frontend 定时请求 (/api/v1/records) 渲染图表
```

---

## 🛠️ 快速启动 (Quick Start)

本项目设计为一键极简启动，**只需一个轻量级 Python 进程**，即可同时托管 API 和前端界面。

### 1. 安装依赖
```bash
# 推荐使用虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlalchemy python-multipart
# 其他核心依赖如 langchain, pandas, scikit-learn 等
```

### 2. 启动服务
```bash
# 在项目根目录下运行
uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

### 3. 访问仪表盘
打开浏览器访问：`http://localhost:8080` 或你的服务器公网 IP，即可进入可视化大屏。

---


---
name: fintech-research
description: 金融研究与尽调辅助软件 FinResearch。当用户想要：启动该软件、上传并分析招股说明书/上市公司年报/行业报告/券商研报、提取财务指标（营收/净利润/毛利率/ROE/经营现金流等）、发现财务异常并溯源到原文页码、全文搜索金融文档、进行同行业公司对比，或做 AI 辅助的金融分析时使用。
---

# FinResearch — 金融研究与尽调辅助软件

本地运行的金融研究工作台：上传招股书、年报、研报等 PDF/Excel 资料，自动提取财务数据、计算指标、发现财务异常（每条异常可溯源到原始文件页码）、全文搜索，并支持基于原始资料的 AI 辅助分析。**所有资料只存在用户本机，不上传任何服务器。**

## 你的职责（本 skill 安装到哪个 agent 就由哪个 agent 执行）

用户会通过对话提出需求。常见任务与执行方式：

### 1. 首次安装（每台机器一次）
按顺序执行：
1. 检查环境：`python --version`（需 ≥3.10）、`node --version`（需 ≥18）。缺失时引导用户先安装（附下载链接：Python 官网 python.org、Node.js 官网 nodejs.org）
2. Windows 运行 `scripts/setup.bat`；macOS/Linux 运行 `scripts/setup.sh`
3. 安装完成后告知用户可用方式

### 2. 启动软件（GUI 界面）
- Windows：运行 `scripts/launch.bat`（开发模式）
- 首次启动会安装依赖，之后秒开
- 界面包含五个工作区：项目档案 | 财务指标 | 异常发现 | 全文搜索 | AI 问答

### 3. 无头分析（对话内直接分析，无需打开界面）
- 单文件分析：`.venv/Scripts/python -m finengine analyze <文件路径>`（engine/.venv；Windows 下 `engine\.venv\Scripts\python`）
- 分析输出包含：提取的财务指标（按年份）、发现的异常（含页码溯源）、可搜索内容摘要
- 回答用户问题时应引用 CLI 输出中的页码出处，**不得编造数据**；CLI 没有输出依据时明确说"资料中没有找到"

### 4. 重要原则
- **一切数据以用户上传的原始资料为准**：不得凭空编造财务数字；每条结论尽量附带文件页码
- 用户资料绝对不离开本机：仅 AI 分析时把检索到的相关片段发送给用户自己配置的 AI 服务（BYOK）
- 依赖安装失败时，把报错信息展示给用户，不要反复盲目重试

## 目录结构
```
SKILL.md       本文件
scripts/       setup / launch / analyze 脚本
engine/        Python 数据引擎（解析、提取、异常、搜索、AI 代理）
app/           桌面软件界面（Electron + React）
```

## 当前开发状态
处于 P0 开发期：工程骨架 + 解析流水线进行中。功能随里程碑逐步解锁（见 README 路线图）。

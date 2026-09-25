# FinResearch — 金融研究与尽调辅助软件

面向金融行业从业者与金融专业学生的本地研究工作台：上传招股说明书、年报、研报等资料，自动提取财务数据、计算核心指标、发现财务异常（每条可溯源到原文页码）、全文搜索，并支持基于原始资料的 AI 辅助分析。

**所有资料只存储在你自己的电脑上，不上传任何服务器。**

## 核心能力

| 工作区 | 功能 |
|---|---|
| 项目档案 | 以"尽调项目"组织资料，上传 PDF/Excel 自动解析（带进度条） |
| 财务指标 | 10 项核心指标（营收/净利润/毛利率/净利率/ROE/经营现金流/应收/存货/有息负债/研发费用）卡片 + 历年趋势图；双击修正、删除错误数据，每条数据可点出处跳回原文核对 |
| 异常发现 | 10 条内置规则自动检测财务异常（应收增速 vs 营收、净利 vs 现金流、毛利率变化等），每条异常给出中文计算过程 + 数据出处页码，点击即可跳回原文 |
| 全文搜索 | 项目内全文搜索，结果带页码与上下文摘录；内置金融术语同义词（搜"主要客户"同时匹配"前五大客户"） |
| AI 问答 | 基于上传资料的 AI 分析，回答强制标注出处页码，资料中没有的内容不编造（防幻觉） |

## 安装与使用

### 方式一：安装包（推荐给普通用户）

从 [GitHub Releases](https://github.com/KUKINYu/FinResearch/releases) 下载 `FinResearch-Setup-x.x.x.exe`，双击安装。

### 方式二：装进你的 Agent

#### Claude Code（一条命令安装）

在 Claude Code 里依次输入：

```
/plugin marketplace add KUKINYu/FinResearch
/plugin install fintech-research@FinResearch
```

装好后对 agent 说"启动金融研究软件"（agent 会自动安装依赖并启动），
或在对话里直接说"分析这份招股书"（无头模式，不需要打开界面）。

#### Codex 及其他 agent

本仓库本身就是一个跨 agent 的 skill（`SKILL.md` 在根目录）：
把仓库复制到 agent 的 skills 目录（如 `~/.codex/skills/`），
对 agent 说"分析这份招股书"即可。

### 从源码运行（开发者）

要求：Python ≥3.10、Node.js ≥18

```bash
# Windows 双击 scripts\setup.bat（macOS/Linux 运行 scripts/setup.sh）
# 安装完成后：
scripts\launch.bat        # 启动软件（开发模式）
```

## AI 服务（BYOK）

AI 问答使用你自己的 API Key，费用由你自己的账号承担（软件本身零 AI 成本）：

- 软件内「AI 问答 → ⚙ AI 设置」填入 Key 即可
- 支持：DeepSeek、通义千问、智谱 GLM、Kimi、OpenAI、Claude
- Key 用 Windows 系统级加密（DPAPI）存储在本机
- 不配置 Key 也能使用除 AI 问答外的全部功能

## 数据与隐私

- 数据目录：`文档\FinResearch`（文件原件 + 数据库 + 缓存）
- 文件原件只读存储，解析永不修改原件
- AI 分析只把检索到的相关片段发送给你配置的 AI 服务商

## 路线图

- ✅ P0：项目管理、财务提取、校对、异常溯源、搜索、AI 问答、打包
- ⏳ P1：同行业公司对比（A股数据源）、异常规则自定义、报告导出、OCR 增强
- ⏳ P2：估值测算（PE/PB/PS/EV-EBITDA 分情景）、尽调清单模板、港股/美股

## 开源许可

[Apache-2.0](LICENSE)

> 注意：本项目仅供学习研究使用。招股书等公开披露文件的使用请遵守巨潮资讯网等服务条款；引入外部数据源前请确认其商用授权。

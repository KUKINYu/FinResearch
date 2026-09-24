# FinResearch — 金融研究与尽调辅助软件（开发规范）

产品需求与实施计划见 `C:\Users\于劭然\.claude\plans\ipo-pdf-excel-toasty-meteor.md`（经创始人确认）。

## 项目定位
本地桌面软件 + 跨 agent skill：面向金融从业者/学生的金融研究与 IPO 尽调工具。核心价值 = **可溯源**（每个数字、每条结论都能点回原始文件具体页码）。不是 AI 聊天软件。

## 目录结构
```
F:\于劭然\Fintech\
├── SKILL.md        # 跨 agent 技能说明（Claude Code / Codex 通用格式）
├── CLAUDE.md       # 本文件（开发规范）
├── README.md       # 面向用户的说明
├── scripts/        # setup.bat（装依赖）、launch.bat（启动）、analyze.bat（无头分析）
├── engine/         # Python 数据引擎（FastAPI + 解析 + 规则引擎 + 搜索 + AI 代理）
│   ├── requirements.txt
│   └── finengine/  # 包：main.py(服务) cli.py(命令行) config.py(路径)
└── app/            # Electron + React + TypeScript 桌面界面（金融终端风格）
```

## 已确认的技术决策（不要轻易更改，改前先与创始人确认）
- 界面：Electron + React + TypeScript + electron-vite + ECharts + pdf.js
- 引擎：Python 3.11 + FastAPI + uvicorn，仅监听 127.0.0.1 随机端口 + 随机令牌（引擎启动时向 stdout 打印 JSON ready 行：`{"event":"ready","port":N,"token":"..."}`，Electron 解析）
- PDF 提取：**pdfplumber**（MIT）。**禁用 PyMuPDF（AGPL，商用有法律风险）**
- OCR：rapidocr_onnxruntime（Apache-2.0，CPU 可跑，不用 PaddlePaddle 框架）
- 存储：SQLite（SQLAlchemy 2.0 + Alembic 迁移，第一天就用迁移）；数据目录默认 `文档\FinResearch`
- 搜索：SQLite FTS5（中文 trigram）+ 本地向量 bge-small-zh-v1.5（fastembed，不装 PyTorch）
- AI：BYOK 多模型网关——OpenAI 兼容接口（DeepSeek/通义/GLM/Kimi/OpenAI，openai 库换 base_url）+ Anthropic 官方 SDK；AI Key 用 Windows DPAPI 加密存储
- 报告：Word 用 python-docx；PDF 用 HTML + Electron 打印
- **分发：GitHub 公开仓库 = 一个跨 agent skill**（SKILL.md 根目录，仅依赖标准命令行，不用 Claude Code 专有特性）；开源许可 Apache-2.0（发布时加 LICENSE）
- 合规红线：AkShare 数据仅限学术研究，商用前必须换授权数据源；引入任何新库前先查开源许可

## 常用命令（Windows）
```bash
# 引擎（在 engine/ 下）
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m finengine serve        # 启动引擎
.venv/Scripts/python -m pytest tests/          # 引擎测试

# 界面（在 app/ 下）
npm install
npm run dev          # 开发模式（自动拉起引擎？不——由 Electron 主进程拉起引擎）
npm run build        # 构建
npm run dist         # 打包 Windows 安装包

# 打包引擎（Spike A 验证）
.venv/Scripts/pyinstaller engine.spec
```

## 开发约定
- 引擎逻辑全部用 pytest 覆盖（纯逻辑测试，不需要界面）
- git 每完成一个里程碑提交一次；提交信息中文
- 每页文本、每条财务数据都带**出处四元组**：file_id + 页码 + 页内坐标 + 原始文字（这是全产品的地基）
- UI 配色：深蓝（主 #1B3A6B 系）、浅蓝（辅）、白、浅灰
- 中文界面与文档；面向"不懂代码的创始人"，代码注释用中文说明意图

## 已知环境坑（2026-09-23 实测）
- 本开发会话的 Bash 环境被注入了 `ELECTRON_RUN_AS_NODE=1`（Claude Code VSCode 扩展注入，非系统永久设置），会让 electron.exe 以纯 Node 模式运行（`electron --version` 输出 v20.x 即中招）。**在本会话里启动/测试 Electron 前必须 `unset ELECTRON_RUN_AS_NODE`**。启动脚本 launch.bat / launch.sh 已内置防御。
- 少数用户机器也可能存在该变量（第三方工具设置）：M8 打包时需处理（安装快捷方式经清理变量的引导器启动）。
- npm 11 默认拦截安装脚本（allowScripts），electron/esbuild 已放行并写入 package.json。
- electron-builder 解压 winCodeSign 缓存需符号链接权限：已为用户开启开发人员模式注册表项（HKCU\AppModelUnlock\AllowDevelopmentWithoutDevLicense=1，**重启后生效**）；重启前打包用 `win.signAndEditExecutable: false`（exe 无产品图标/版本信息），M8 重启后恢复 true 并补图标。
- Git Bash 控制台显示中文路径为乱码（GBK 控制台 vs UTF-8 输出），属显示问题不影响功能。

## 里程碑进度（见计划文件第七节）
- [x] Spike A：打包可行性——**通过**（引擎 exe 12.9MB；NSIS 安装包 + 免安装版均构建成功；打包成品运行验证：引擎拉起、界面-引擎链路打通）
- [x] Spike B：招股书解析 POC——**通过**（5 份真实招股书覆盖沪深三大板块：中塑/鸿富诚/沈鼓/燧原/信诺维。数字版 4 份适用指标提取全覆盖；沈鼓 9 项数值与公开披露完全一致；燧原为"表格线缺失+标签在表外"布局，经文本行回退通道同样提取成功。19 个单元测试固化全部踩坑经验。遗留小问题：①ROE 多口径时取首个匹配（扣非口径）②回退通道纯"-"占位符在数值前时被剥离，若"-"是第一列数据会错位，待真实样本出现再处理）
- [x] Spike C：RAG 溯源 POC——**通过**（bge-small-zh-v1.5 本地向量模型，150 页 387 块建索引 18.4 秒；6 个真实研究问题 top-5 命中 3-5 条直接相关，每条命中带页码出处。遗留：纯关键词类问题（如"关联交易"章节）需要 M6 的 FTS5 关键词检索做混合检索；模型从 HF 下载需 28 秒，M7 打包时需内置或预下载缓存）
- [x] M1 工程骨架（Electron 壳 + 引擎启停 + 握手协议 + skill 脚本 + 开发规范；已提交 eb6a3e2）
- [x] M2 项目/文件管理 + 上传 + 解析流水线（SQLite 数据层、后台解析线程+进度、财务提取入库、项目档案界面；已提交 42b51f3）
- [x] M3 PDF 阅读器 + 校对界面（pdf.js 跳页高亮、指标双击修正/删除/出处跳转；已提交 5fa696c）
- [x] M4 趋势图 + 口径过滤（ECharts 趋势图；子公司数据污染已修复——严格期间格式识别、表头标签校验、不完整行丢弃、转置表纯期间格限制；5 份招股书回归验证零污染；已提交 0628f64）
- [x] M5 异常检测 + 溯源（10 条内置规则：应收/存货增速vs营收、净利vs现金流、现金流背离、毛利率/资产负债率变化、有息负债覆盖、研发占比、收现比、周转天数；每条异常带中文计算过程+数据出处可跳原文；解析完成后自动分析；中塑实测触发 2 条高危异常均计算正确）
- [x] M6 全文搜索（FTS5 中文 trigram + 短词 LIKE 回退 + 金融术语同义词扩展；结果带页码摘录可跳原文；修复重复解析页面翻倍）
- [x] M7 AI 问答（BYOK 六家服务商模板：DeepSeek/通义/GLM/Kimi/OpenAI 走 OpenAI 兼容接口，Claude 走 Anthropic SDK；Key 用 Windows DPAPI 加密存储；RAG 混合检索+强制页码引用+防编造提示词；token 消耗透明显示；向量模型未就绪时自动降级为关键词检索）
- [ ] M8 打包发布（重新验证安装包、图标、README/LICENSE、GitHub 发布准备）

## M7 遗留（网络相关）
- 本地向量模型 bge-small-zh-v1.5（~95MB）今日多次下载卡顿（HF 与 hf-mirror 均不稳）；已做优雅降级：模型未就绪时纯关键词检索（功能可用），模型缓存固定放 文档\FinResearch\cache\models，下载成功后自动启用向量模式。M8 打包时可考虑预置模型或提供离线模型包。

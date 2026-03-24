# 📚 Related Work Agent (RWA)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License MIT">
  <img src="https://img.shields.io/badge/LLMs-OpenAI%20%7C%20Anthropic%20%7C%20DeepSeek%20%7C%20Qwen%20%7C%20Ollama-orange.svg" alt="LLMs Supported">
  <img src="https://img.shields.io/badge/Retrieval-SPECTER2%20%7C%20ColBERT%20%7C%20CrossEncoder-purple.svg" alt="RAG Pipeline">
</p>

<p align="center">
  <b>[ English | <a href="#-中文说明">中文说明</a> ]</b>
</p>

An automated, agentic workflow designed to generate high-quality, publication-ready **"Related Work"** sections for academic papers. By providing related PDF papers and your own manuscript draft, RWA analyzes the stylistic nuances of your target venue, performs multi-stage academic retrieval (RAG), and iteratively refines the generated LaTeX output through an LLM-as-a-Judge reflection process.

## ✨ Key Features

- 🤖 **Multi-LLM Ecosystem**: Seamlessly integrate with Anthropic (Claude), OpenAI (GPT-4), DeepSeek, Qwen (DashScope), Azure OpenAI, or run fully locally via Ollama.
- 🔎 **Three-Stage Academic RAG**: 
  - **Dense Retrieval**: Utilizes `allenai/specter2_base` specifically tuned for academic contexts.
  - **Late Interaction (Optional)**: Employs `ColBERTv2` for precise token-level matching.
  - **Reranking**: Integrates `Cross-Encoder` for fine-grained re-ordering.
- 🎯 **Style Emulation**: Automatically analyzes papers from your target journal/conference to mimic paragraph structure, citation density, word count, and transition phrases.
- 🔄 **Self-Reflective Iteration**: Uses an LLM Scorer to evaluate the draft across multiple dimensions (Coverage, Accuracy, Comparison Quality, Novelty Highlights) and iteratively writes improved versions.
- 📝 **Native LaTeX Output**: Generates strictly valid LaTeX code, handles robust character escaping, and auto-refines `.bib` entries for seamless compilation.

## 🚀 Quick Start

### 1. Installation

Requires Python 3.10+.

```bash
# Clone the repository
git clone https://github.com/your-username/related_work_agent.git
cd related_work_agent

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install core dependencies
pip install -e .

# Install specific LLM provider(s) you intend to use
pip install -e ".[deepseek]"       # DeepSeek
pip install -e ".[anthropic]"      # Claude
pip install -e ".[openai]"         # GPT-4
pip install -e ".[dashscope]"      # Qwen
pip install -e ".[colbert]"        # Optional: Enable ColBERT for higher-quality retrieval
```

### 2. Configuration

Copy the environment template and fill in your API keys:
```bash
cp .env.example .env
```

Modify `config.yaml` to set your desired LLM provider, target venue, and retrieval parameters.

### 3. Data Preparation

Structure your papers as follows in the `data/` directory:
```text
data/
├── background_papers/     # Traditional/background papers (for early paragraphs)
├── comparison_papers/     # Highly related/competing papers (for comparative paragraphs)
├── venue_style_papers/    # Papers from the target venue (for style extraction)
└── my_paper/              # Your paper draft (.pdf, .tex, .txt, or .md)
```

### 4. Run the Agent

```bash
rwa                              # Standard execution
rwa --iterations 1               # Fast test (only 1 generation iteration)
rwa --skip-indexing              # Skip vector DB rebuild (if data hasn't changed)
rwa --config custom_config.yaml  # Run with a specific config file
```

## 📂 Output Structure

Results are saved to `outputs/{timestamp}/`. The `final_best.tex` is your final polished draft!

```text
outputs/2026xxxx_xxxxxx/
├── iteration_1/
│   ├── draft.tex              # 1st LaTeX Draft
│   ├── draft_readable.md      # Readable Markdown version
│   └── score.json             # Evaluation score and improvement suggestions
├── iteration_n/               # Refined iterations
├── final_best.tex             # ★ The highest-scoring final draft (Ready to \input)
└── references_draft.bib       # Auto-generated BibTeX entries
```

---

<hr>

# 🇨🇳 中文说明

**Related Work Agent (RWA)** 是一个基于大语言模型（LLM）的自动化多智能体工作流。只需提供相关参考文献 PDF 与你自己论文的草稿，系统即可自动分析目标期刊/会议的写作风格，通过多阶段学术级 RAG 检索对应内容，并利用“自我反思与多轮迭代”机制，生成高质量、可直接编译的 **“相关工作 (Related Work)”** 中文/英文 LaTeX 章节。

## ✨ 核心特性

- 🤖 **多模型自由切换**：支持接入 Anthropic, OpenAI, DeepSeek, 阿里云通义千问 (DashScope), Azure，以及通过 Ollama 在本地无网运行开源模型。
- 🔎 **学术级精细检索 (RAG)**：
  - **向量召回**：使用专为学术论文训练的 `allenai/specter2_base`。
  - **ColBERT 匹配 (可选)**：启用后可通过 Late Interaction 提供 Token 级别的极致学术词汇匹配。
  - **精排**：通过 `Cross-Encoder` 实现顶层重排序。
- 🎯 **期刊风格自适应**：自动从目标期刊的示例论文中提取写作模式（篇幅、引用密度、段落逻辑、过渡词等），智能模仿。
- 🔄 **自动评分与多轮迭代**：生成草稿后，由独立的评分 LLM 从准确性、对比度、自身创新点突出程度等 7 个维度进行打分并提出改进意见，自动流转到下一轮重新撰写。
- 📝 **原生 LaTeX 生态**：输出纯净合法的 LaTeX 代码（自动处理 `%`、`&` 等特殊字符转义），并配套自动补全的 `.bib` 参考文献文档。

## 🚀 快速开始

### 1. 安装环境

环境要求：Python 3.10 及以上。

```bash
# 获取源码
git clone https://github.com/your-username/related_work_agent.git
cd related_work_agent

# 推荐使用虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装基础依赖
pip install -e .

# 根据你需要使用的 LLM，安装对应的可选依赖
pip install -e ".[deepseek]"       # 若想用 DeepSeek API
pip install -e ".[dashscope]"      # 若想用 通义千问 API
pip install -e ".[anthropic]"      # 若想用 Claude API
pip install -e ".[openai]"         # 若想用 OpenAI API

# 可选高精度检索（构建索引较慢）
pip install -e ".[colbert]"
```

### 2. 配置密钥与参数

```bash
# 复制并配置环境变量
cp .env.example .env
# 使用你喜欢的编辑器修改 .env 填入你的对应 API Key
```

在 `config.yaml` 中配置目标期刊名称、生成语言、迭代轮次及所用的 LLM 提供商。生成 LLM 与评分 LLM 可以配置为不同模型（如使用顶配模型生成，廉价高速模型评分）。

### 3. 数据集准备

请将相关论文的 PDF 或源文件放入以下目录：
```text
data/
├── background_papers/     # 背景或较老的方法论文（用于前几段综述）
├── comparison_papers/     # 高度相似的竞品论文（用于后半部分横向对比，以突出你的创新）
├── venue_style_papers/    # 目标期刊上近期发表的论文（系统会学习它们的写作结构）
└── my_paper/              # 你自己的论文草稿文件 (.pdf / .tex / .md / .txt均可)
```

### 4. 启动 Agent

完成配置后，使用命令行直接运行：

```bash
rwa                              # 标准执行（执行全部管线）
rwa --iterations 1               # 快速调试模式（仅生成一轮）
rwa --skip-indexing              # 已构建过 Chroma 向量库后可跳过索引构建
rwa --config my_custom_cfg.yaml  # 指定自定义配置文件读取
```

## 📂 输出结构说明

每次运行的产物将全量保存在 `outputs/{时间戳}/` 目录下：

- `iteration_x/`：包含该轮生成的 `.tex` 草稿、便于阅读的 Markdown 格式及详细评分解释。
- **`final_best.tex`**：系统根据多轮评分选出的**最佳版本**。将其内容直接 `\input` 或复制到你的主文稿中即可编译！
- `references_draft.bib`：LLM 辅助完善规范化的引用数据。

## ⚙️ 进阶配置与自定义开发

查阅项目根目录下的 `related_work_agent_dev_doc.md` 开发文档，其中包含了有关模块切分、多维查询解析、ColBERT 精排调优的更深入的架构设计与二次开发指南。

## 📄 License

本项目采用 [MIT License](LICENSE) 开源。

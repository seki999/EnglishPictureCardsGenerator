# English Picture Cards Generator

本地 Windows 10/11、Python 3.11+ 的 CLI 工具。读取 Markdown / CSV / Excel，生成分层词汇 JSON 和英文场景 prompt，可通过本地 ComfyUI + SDXL 为每条例句生成 PNG。没有 GUI、TTS 或音频功能。

## 最短运行步骤

在项目目录打开 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
# 不需要 ComfyUI：只生成 JSON 和 prompt
.\.venv\Scripts\python.exe -m app.main --dry-run
# 启动 ComfyUI 并配置 checkpoint 后，先生成一张
.\.venv\Scripts\python.exe -m app.main --generate-images --resume --limit 1
```

安装脚本创建 `.venv`、安装依赖，并执行 dry-run。已在项目中附带 sample input / output。日常使用可双击 `run_generate.bat`；它会自动准备尚未安装的虚拟环境。安装依赖需要联网，生成阶段无需在线生成服务或 API key。

## 准备 ComfyUI 和模型

1. 安装 [Python for Windows](https://www.python.org/downloads/windows/)，勾选添加到 PATH。
2. 从 [ComfyUI 官方仓库](https://github.com/Comfy-Org/ComfyUI#installing) 和 [官方 Releases](https://github.com/Comfy-Org/ComfyUI/releases) 获取 Windows NVIDIA portable 压缩包，完整解压。ComfyUI 使用自己的 Python 环境，不需要安装到本项目 `.venv`。
3. 准备完整 SDXL checkpoint，例如 [Stability AI SDXL Base 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/main) 的 `sd_xl_base_1.0.safetensors`。将文件放到解压目录下 `ComfyUI/models/checkpoints/`，再启动或重启 ComfyUI。
4. 运行 portable 的 `run_nvidia_gpu.bat`。浏览器打开 `http://127.0.0.1:8188`，确认能够访问。若已安装 ComfyUI，只需启动现有版本。
5. 编辑 `config/config.yaml` 的 `generation.checkpoint`，必须与 ComfyUI 中 checkpoint 名称完全一致（包括子目录）。端口不同则修改 `comfyui.url`。

也可按[官方手动安装说明](https://github.com/Comfy-Org/ComfyUI#manual-install-windows-linux)在独立环境安装 ComfyUI，并在它的目录运行 `python main.py`。无 GPU 可使用 `python main.py --cpu`，但 SDXL 推理会非常慢，建议提高 `task_timeout`。GPU 显存不足时可降低图片尺寸或按 ComfyUI 官方说明调整内存选项。此项目不自动下载数 GB 的模型，也不代替安装 ComfyUI。

## 输入

支持 `.md` / `.markdown`、UTF-8（允许 BOM）`.csv`、`.xlsx` / `.xlsm`。Excel 读取活动工作表，公式读取已缓存的结果；旧 `.xls` 请先另存为 `.xlsx`。

无表头时固定九列：

```text
word, part_of_speech, phonetic_uk, phonetic_us, definition_zh,
phrase, phrase_zh, sentence_zh, sentence_en
```

标准英文表头可调整列顺序；中文表头支持：单词、词性、英式音标、美式音标、中文释义、短语、短语中文、中文例句、英文例句。`word`、`definition_zh`、`sentence_en` 必填，其余允许为空。Markdown 支持有无首尾竖线、对齐分隔线、空行及正文说明。分隔行自动跳过，不会把示例的第一条数据误认为表头；单元格里的竖线写成 `\|`。每条记录需放在一行，输入文件使用一个词汇表。列数错误会明确报错。

示例 `data/input/sample_vocab.md` 刻意保留“首行是 abstain 数据，第二行是分隔线”的格式。CSV 可以用相同九列导出；包含逗号的字段应使用标准 CSV 双引号。

## CLI

```powershell
.\.venv\Scripts\python.exe -m app.main --input data/input/sample_vocab.md --output data/output/toeic-vocabulary-001.json --generate-images
.\.venv\Scripts\python.exe -m app.main --generate-images --resume --limit 3
.\.venv\Scripts\python.exe -m app.main --generate-images --dry-run
```

| 选项 | 行为 |
| --- | --- |
| `--config PATH` | 指定 YAML 配置 |
| `--input PATH` / `--output PATH` | 覆盖配置的输入 / JSON 输出 |
| `--generate-images` | 调用 ComfyUI；不传时仅输出 JSON / prompt |
| `--dry-run` | 只写 JSON / prompt，优先于 `--generate-images`，完全不访问 ComfyUI |
| `--resume` | 显式启用默认自动恢复行为 |
| `--limit N` | 最多尝试生成 N 条待处理例句；跳过项不占额度；0 不访问 ComfyUI |
| `--force` | 在生成模式下重新生成已完成图片，成功后替换文件 |

结束后打印总输入记录数、成功数、跳过数、失败数、待处理数。成功/跳过/失败计数针对唯一例句的本次运行；重复输入会合并，所以这几项之和可能小于总输入记录数。dry-run 的成功数为 0、例句均待处理；已有生成状态可保留。退出码：0 正常，1 输入/配置/API/图片错误，130 用户中断。

## JSON 和路径约定

结构为 `words[] -> meanings[] -> examples[] -> image`，与要求的 schema 1.0 一致。相同单词、词性及音标合并；相同释义、短语及短语中文合并；完全相同双语例句去重。ID 格式为 `abstain`、`abstain-01`、`abstain-01-001`。词性不同的同名单词会加短 hash 防止冲突。

配置中的文件路径相对于项目根目录，不依赖启动 shell 的目录，可配置绝对路径。**JSON 中 image.path 相对于 JSON 文件所在目录**，使用 `/` 分隔符。默认输出在 `data/output/`，因此路径为 `../../assets/images/abstain-01-001.png`。前端应以 JSON 所在目录解析它，不能再以项目根目录解析。这样 JSON 移至其他位置时仍由程序重新计算正确路径。dry-run 会写入预期路径，但不会创建图片；只显示 `status=completed` 的图。

`image` 包含全部要求字段，并额外保留 `checkpoint`、`scheduler` 和任务提交后的 `prompt_id`。`model` 是显示标签，真正加载的文件由 `checkpoint` 决定。`seed=-1` 在首次提交前换成实际随机种子并保存；重试同一图片使用同一 seed。

状态为 `pending`、`generating`、`completed`、`failed`。每次提交和每张图结束时原子写入 JSON，避免中途写出半个文件。JSON 写入失败会记录日志并停止，避免在无法保存进度时继续生成。

## 断点、重试和日志

- 默认读取已有同 deck JSON，恢复 ID、双语句子、prompt 和参数完全匹配的图片状态。完成且文件存在、可解码时自动跳过；丢失或损坏会重新生成。修改内容、prompt 或生成参数会使旧状态失效。改变输入顺序可能改变编号并导致重新生成；续跑时保持顺序。
- 保存了 `prompt_id` 的未完成任务下次运行继续轮询，避免超时后重复提交。确认 ComfyUI 重启丢失任务历史时，可用 `--force` 重新提交；它会重做本次额度内的图片。
- HTTP GET 的连接/超时/5xx 错误自动重试；已明确执行失败的单图可重试。`retries: 2` 表示最多额外两次。单条失败保留错误并继续其他例句。
- POST 提交超时无法确认服务端是否已经接收，因此本次运行不盲目重发。没有收到任务 ID 的这种极小窗口无法完全自动去重；请先查看 ComfyUI 队列再续跑。
- `task_timeout` 是单次轮询时间窗口（网络重试可能额外耗时），超时保留任务 ID。客户端不取消其他 ComfyUI 任务。
- 日志写入 `logs/generator.log`，错误含堆栈；失败详情同时写到 JSON 的 `error_message`。

## Prompt 规则

所有 prompt 使用 realistic photo、clean composition、natural lighting、educational flashcard illustration，末尾为 `No text in image.`；negative prompt 排除 text、watermark、logo、captions、subtitles、letters、signage 等。程序不向图片添加文字或中文释义。总统、就职、投票等场景使用虚构人物与通用环境，不提示真实政治人物身份。

第一版完全离线：医疗戒酒、弃权、就职演说、投票、道歉、同意等有专门可视化规则，其他句子提取动作片段保守回退。它不是通用语言模型，复杂抽象句子的 prompt 需要人工校对。可在 YAML 按短语覆盖场景：

```yaml
prompt_overrides:
  reach a compromise: "Two colleagues shake hands across a meeting table after moving two plain objects toward the center."
```

写英文场景，不写需要显示的学习文字。扩散模型仍可能产生伪文字或语义不准确的图，提示词不能保证每次消除；可人工检查后用不同 seed / `--force` 重做。

## Workflow

`workflows/sdxl_basic_api.json` 是 API 格式，不是可视编辑器画布格式。仅使用原生 checkpoint、CLIP 编码、latent、KSampler、VAE 解码、SaveImage，不需要 custom nodes；完整 SDXL checkpoint 不需要单独 refiner。

模板用完整字符串 `{{prompt}}`、`{{negative_prompt}}`、`{{width}}`、`{{height}}`、`{{steps}}`、`{{cfg}}`、`{{seed}}`、`{{checkpoint}}`、`{{sampler}}`、`{{scheduler}}`、`{{filename_prefix}}` 作为占位符，注入时保留数值类型。可替换成自己的 API workflow，必须保留一个 `SaveImage` 输出节点。程序通过 `/prompt` 提交、`/history/{prompt_id}` 轮询、`/view` 下载 SaveImage 输出到本地；见 [ComfyUI 官方 API 路由](https://github.com/Comfy-Org/docs/blob/main/development/comfyui-server/comms_routes.mdx)。源图保留在 ComfyUI 输出目录。

## 验证与项目结构

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试使用本地模拟 HTTP 服务验证任务提交、参数类型、轮询、下载、跳过、失败续跑，无需 GPU。真实模型出图需本机已启动 ComfyUI 后执行 `--limit 1`。

```text
app/                  解析、标准化、prompt、API、图片生成、原子 JSON 写入、CLI
config/config.yaml    路径、checkpoint、参数、prompt 覆盖
workflows/            可配置 API workflow
data/input/           示例 Markdown
data/output/          示例和实际 JSON
assets/images/        每条例句一个 PNG
logs/                 运行日志
tests/                解析与模拟 API 集成测试
setup.ps1             安装与 dry-run
run_generate.bat      一键生成入口
requirements.txt      Python 依赖
```

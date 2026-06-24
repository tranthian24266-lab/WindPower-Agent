# 风电小模型包接入手册

本手册说明如何制作一个能够从平台“模型库 → 添加模型”页面上传、验证和发布的小模型包。

当前版本支持以下任务类型：

- `fault_diagnosis`：故障诊断
- `rul_prediction`：故障预测与剩余寿命估计
- `anomaly_detection`：健康状态检测

平台只接受 ZIP 压缩包。上传后，模型包先进入隔离目录；结构检查和真实冒烟推理都通过后，才能发布为候选版本。上传包中的 `requirements.txt` 不会被自动安装。

## 1. 标准目录

```text
my_model_v1.zip
└── my_model/
    ├── README.md
    ├── model_card.json
    ├── config.yaml
    ├── inference.py
    ├── requirements.txt
    ├── weights/
    │   └── model.pth
    ├── test_data/
    │   └── sample.csv
    ├── scripts/                 # 可选
    │   ├── model.py
    │   └── preprocess.py
    └── examples/                # 可选
        └── run_example.py
```

ZIP 中可以直接放这些文件，也可以像示例一样再包一层模型目录，但只能包含一个 `model_card.json`。

## 2. 必需文件及作用

| 路径 | 是否必需 | 作用 |
|---|---:|---|
| `model_card.json` | 是 | 机器可读的模型身份、版本、任务类型、输入输出、限制和前端参数定义。平台主要通过它注册模型。 |
| `config.yaml` | 是 | 模型默认运行参数，例如权重路径、窗口长度、采样率和阈值。推理代码自行读取。 |
| `inference.py` | 是 | 平台统一推理入口，必须提供顶层 `predict()` 函数。 |
| `requirements.txt` | 是 | 声明依赖，供管理员检查环境兼容性；平台不会自动安装。没有额外依赖时可只写注释。 |
| `README.md` | 是 | 面向使用者的模型说明，包括数据要求、输出含义、适用范围和来源。 |
| `weights/` | 是 | 存放至少一个正式推理产物，例如 `.pth`、`.pt`、`.joblib`、`.onnx`。 |
| `test_data/` | 是 | 存放至少一个冒烟测试样本。支持 `.csv`、`.npy`、`.npz`、`.mat`。 |
| `scripts/` | 否 | 放置网络结构、特征提取、预处理等由 `inference.py` 调用的本地模块。 |
| `examples/` | 否 | 放置独立运行示例，便于模型作者在平台外验证。 |

不要把训练集、训练缓存、虚拟环境、Git 仓库、密码、API Key 或无关运行输出放入模型包。

## 3. `model_card.json`

最小示例：

```json
{
  "model_id": "bearing_fault_cnn_v1",
  "family_code": "bearing_fault_cnn",
  "model_name": "轴承故障 CNN 模型",
  "model_version": "1.0.0",
  "task_type": "fault_diagnosis",
  "description": "用于识别风机轴承故障状态",
  "framework": "pytorch",
  "runtime_profile": "platform-default",
  "input_format": [".csv", ".npy"],
  "output_labels": ["healthy", "inner_race_fault", "outer_race_fault"],
  "dataset": "用户自建轴承数据集",
  "limitations": [
    "输入采样频率必须为 12.8kHz",
    "当前仅验证三分类场景"
  ],
  "adapter_entrypoint": "inference.py:predict"
}
```

字段规则：

| 字段 | 必需 | 规则 |
|---|---:|---|
| `model_id` | 是 | 每一个已发布版本都必须全局唯一。只使用小写字母、数字、点、下划线和连字符。建议包含版本后缀。 |
| `family_code` | 否 | 同一模型家族多个版本使用相同值；省略时等于 `model_id`。 |
| `model_name` | 是 | 前端展示名称，可在上传向导中补充修改。 |
| `model_version` | 是 | 版本号，例如 `1.0.0`；只能使用安全标识字符。 |
| `task_type` | 是 | 必须是当前支持的三个任务类型之一。 |
| `description` | 推荐 | 模型用途和能力概述。 |
| `framework` | 推荐 | 例如 `pytorch`、`scikit-learn`、`onnxruntime`。 |
| `runtime_profile` | 推荐 | 建议填写 `platform-default`，表示使用平台现有受控环境。 |
| `input_format` | 推荐 | 模型实际支持的扩展名列表。 |
| `output_labels` | 按任务 | 分类模型建议填写；回归模型可改用 `output_schema` 描述。 |
| `dataset` | 推荐 | 数据集名称、来源或“用户自建数据集”。 |
| `limitations` | 推荐 | 必须如实记录采样率、设备、工况、标签和泛化限制。 |
| `input_contract` | 是 | 描述扩展名、容器类型、字段、数组键和形状，供智能体自动选择任务和模型。 |
| `adapter_entrypoint` | 是 | 当前固定为 `inference.py:predict`。 |

### 同一家族增加新版本

例如：

```json
{
  "model_id": "bearing_fault_cnn_v2",
  "family_code": "bearing_fault_cnn",
  "model_version": "2.0.0"
}
```

`family_code` 保持不变，`model_id` 和 `model_version` 必须变化。这样前端会把多个版本放在同一个模型家族下。

### 自动路由 `input_contract`

智能检测会读取模型卡中的输入契约，并与上传文件的结构进行匹配：

```json
{
  "input_contract": {
    "accepted_suffixes": [".csv"],
    "container_types": ["tabular"],
    "required_columns": ["wind_speed", "power", "generator_speed"],
    "minimum_required_column_ratio": 0.8
  }
}
```

可用字段：

| 字段 | 作用 |
|---|---|
| `accepted_suffixes` | 允许的扩展名，例如 `.csv`、`.mat`、`.npy`、`.npz`。 |
| `container_types` | 数据容器类型：`tabular`、`matlab`、`numeric_array`、`numeric_archive`。 |
| `required_columns` | CSV 必须匹配的关键字段。 |
| `minimum_required_column_ratio` | 字段最低匹配率，推荐 `0.8`。 |
| `required_array_keys` | MAT/NPZ 必须存在的变量键。 |
| `alternative_array_keys` | 满足任意一个即可的兼容变量键。 |
| `required_last_dimension` | NPY 窗口最后一维的固定长度。 |

模型包缺少 `input_contract` 时，上传检查不会通过。契约应描述已经验证过的真实输入，不要为了提高匹配率而填写过宽的格式。

## 4. 动态运行参数

如果模型需要允许用户调整阈值或批大小，可以在 `model_card.json` 中增加 `parameter_schema`：

```json
{
  "parameter_schema": {
    "confidence_threshold": {
      "type": "number",
      "title": "置信度阈值",
      "default": 0.75,
      "minimum": 0,
      "maximum": 1
    },
    "device": {
      "type": "select",
      "title": "运行设备",
      "default": "auto",
      "options": ["auto", "cpu", "cuda"]
    }
  }
}
```

推理时平台会把选择的参数作为 `options` 字典传入。模型必须对缺失参数提供安全默认值。

## 5. `config.yaml`

示例：

```yaml
weight_file: weights/model.pth
device: auto
sample_rate: 12800
window_size: 4096
batch_size: 32
confidence_threshold: 0.75
```

要求：

- 路径必须使用相对于模型目录的路径。
- 不要写开发者电脑的绝对路径。
- 不要保存密码、令牌或数据库连接。
- `config.yaml` 是模型默认配置；可调参数仍应通过 `options` 覆盖。

## 6. `inference.py`

必须提供以下入口：

```python
def predict(
    input_path: str,
    output_dir: str,
    options: dict | None = None,
) -> dict:
    ...
```

最小示例：

```python
from pathlib import Path
import json


def predict(input_path: str, output_dir: str, options: dict | None = None) -> dict:
    options = options or {}
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. 读取 input_path
    # 2. 加载 weights/ 中的模型
    # 3. 执行与训练一致的预处理和推理
    prediction = {"label": "healthy", "confidence": 0.95}

    result = {
        "status": "success",
        "task_type": "fault_diagnosis",
        "model_id": "bearing_fault_cnn_v1",
        "risk_level": "low",
        "prediction": prediction,
    }
    (output_path / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result
```

必须遵守：

- 返回值必须是可以 JSON 序列化的字典。
- 建议至少返回 `status`、`task_type`、`model_id` 和任务结果。
- 所有输出只能写入传入的 `output_dir`。
- 不能修改模型目录、注册表或项目文件。
- 不能依赖当前工作目录；使用 `Path(__file__).resolve().parent` 定位权重和配置。
- 不应访问网络、启动服务、开启交互窗口或无限创建子进程。
- 不得在模块导入阶段直接执行训练或推理。

定位模型目录的推荐写法：

```python
MODEL_DIR = Path(__file__).resolve().parent
WEIGHT_PATH = MODEL_DIR / "weights" / "model.pth"
```

## 7. `requirements.txt`

示例：

```text
numpy>=1.26,<3
torch>=2.4,<3
scikit-learn>=1.5,<2
```

平台只展示和检查依赖，不会执行 `pip install -r requirements.txt`。模型作者应优先使用平台已经具备的依赖。需要增加依赖时，由管理员评估后统一更新平台运行环境。

禁止使用：

- `-e` 本地路径
- 本地磁盘绝对路径
- 未审核的 Git URL
- 安装后执行脚本
- 私有仓库凭据

## 8. 测试数据

`test_data/` 中至少放一个体积较小、允许随模型分发的真实格式样本。平台按文件名排序后选择第一个支持的样本执行冒烟测试。

样本必须：

- 能被 `predict()` 单独处理。
- 不包含隐私或敏感生产数据。
- 足以验证权重加载、预处理、推理和输出写入。
- 不应依赖额外标签文件；如果确实需要，应让 `predict()` 能在没有标签时运行。

## 9. 上传、验证和发布

1. 在模型库点击“添加模型”。
2. 上传 ZIP 包。
3. 查看平台解析出的模型 ID、版本、任务、权重和测试样本。
4. 补充模型名称、说明、数据集和适用限制。
5. 点击“保存信息并验证”。
6. 平台执行静态检查和独立子进程冒烟推理。
7. 通过后点击“发布候选版本”。
8. 候选版本不会自动替换当前生产模型。
9. 观察运行效果后，再由管理员分配 `canary`、`champion` 或 `default` 别名。

## 10. 验证项目

平台会检查：

- ZIP 路径穿越和符号链接。
- 上传大小、解压大小和文件数量。
- 必需文件和目录。
- `model_card.json` 格式和字段。
- `model_id` 唯一性。
- 任务类型是否受支持。
- 权重目录是否为空。
- 测试样本是否存在。
- `inference.py` 能否解析并定义顶层 `predict()`。
- 冒烟推理是否在超时前完成。
- 返回值是否为 JSON 字典。

## 11. 归档和删除

- 已分配 `default`、`champion`、`canary` 或 `fallback` 的模型不能归档或删除，必须先切换别名。
- 有诊断历史的模型只能归档，不能永久删除。
- 删除只适用于平台通过上传流程托管的模型，内置模型不允许从前端删除。
- 删除后的文件先进入服务器回收站，不会立即物理销毁。

## 12. 安全边界

`inference.py` 是可执行 Python 代码。当前本地版本通过管理员权限、隔离上传目录、独立子进程和超时降低风险，但不是容器级安全沙箱。因此：

- 只上传来源可信、经过代码审查的模型包。
- 开启 RBAC 时，只有管理员拥有模型包管理权限。
- 不向普通用户开放任意模型代码上传权限。
- 生产部署建议进一步把验证和推理迁移到无网络、受资源限制的独立容器。

## 13. 发布前检查清单

- [ ] `model_id` 全局唯一，`family_code` 能正确关联模型家族。
- [ ] 版本号与权重一致。
- [ ] 模型卡如实说明数据来源和限制。
- [ ] 不使用开发电脑绝对路径。
- [ ] `weights/` 只包含运行需要的模型产物。
- [ ] `test_data/` 含可独立推理的小样本。
- [ ] `predict()` 返回 JSON 字典并只写入 `output_dir`。
- [ ] 依赖已被平台环境支持。
- [ ] 本地已经使用与平台一致的入口完成冒烟测试。
- [ ] ZIP 中没有训练集、密钥、虚拟环境和无关输出。

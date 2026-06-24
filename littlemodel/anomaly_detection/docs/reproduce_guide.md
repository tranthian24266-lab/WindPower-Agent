# 风电异常检测论文复现指南：Autoencoder-Based Transfer Learning for Wind Turbine Anomaly Detection

## 0. 复现目标与边界

本指南用于在本地逐步复现论文 **Transfer learning applications for autoencoder-based anomaly detection in wind turbines** 的主要方法链路。

需要注意：原论文使用的两个德国北海海上风电场 SCADA 数据不是公开数据，因此本复现不追求复现论文中的完全相同数值，而是复现它的核心方法流程：

1. 使用风机 SCADA 数据训练 Autoencoder 正常行为模型；
2. 用重构误差 RMSE 作为 anomaly score；
3. 通过最大化 F1/2-score 选择异常阈值；
4. 比较 baseline AE 与迁移学习 AE；
5. 复现三种迁移策略：
   - 只更新 threshold；
   - 冻结 encoder，只微调 decoder；
   - 微调整个 AE；
6. 输出 anomaly detection 指标和论文风格图表。

本地数据集已经下载到：

```text
C:\Users\luzian\Desktop\windpower_dataset\AD
```

训练环境：

```powershell
conda activate pytorch
```

必须使用本机 GPU 训练，不要在 CPU 上训练。如果检测不到 CUDA，应停止并提示用户修复环境。

---

## 1. 项目目录

在数据集目录下新建一个复现工程目录：

```text
C:\Users\luzian\Desktop\windpower_dataset\AD\wind_ae_transfer_ad_repro
```

建议工程结构如下：

```text
wind_ae_transfer_ad_repro/
│
├── configs/
│   └── config.yaml
│
├── src/
│   ├── 00_inspect_dataset.py
│   ├── 01_preprocess.py
│   ├── 02_build_splits.py
│   ├── model_ae.py
│   ├── train_source.py
│   ├── train_baseline.py
│   ├── train_transfer.py
│   ├── evaluate.py
│   ├── plot_results.py
│   ├── cleanup.py
│   └── run_all.py
│
├── outputs/
│   ├── reports/
│   ├── tables/
│   ├── figures/
│   ├── models/
│   └── logs/
│
├── temp/
│   ├── processed/
│   └── splits/
│
├── run_reproduction.bat
├── requirements_used.txt
└── README_REPRODUCTION.md
```

数据集原始文件和解压文件不要移动，代码只读取：

```text
C:\Users\luzian\Desktop\windpower_dataset\AD\raw
C:\Users\luzian\Desktop\windpower_dataset\AD\extracted
```

---

## 2. 环境检查

先写 `src/00_inspect_dataset.py`，功能包括：

1. 检查 Python、PyTorch、CUDA；
2. 检查 `torch.cuda.is_available()` 是否为 `True`；
3. 打印 GPU 名称；
4. 检查数据集目录是否存在；
5. 自动搜索 README、event_info、status、csv、parquet 等文件；
6. 随机读取几个数据文件，输出：
   - 文件路径；
   - 行数；
   - 列数；
   - 前 10 个列名；
   - 时间戳列候选；
   - turbine id / asset id 列候选；
   - wind farm id 列候选；
   - status / label / event 列候选；
   - 数值型 SCADA 特征数量。

环境检查要求：

```python
import torch

if not torch.cuda.is_available():
    raise RuntimeError("CUDA is not available. Stop here. Do not train on CPU.")

device = torch.device("cuda")
print("CUDA device:", torch.cuda.get_device_name(0))
```

输出报告保存到：

```text
outputs/reports/dataset_inspection_report.txt
```

---

## 3. 数据读取与字段识别

由于 CARE To Compare 数据集的文件结构可能与论文私有数据不同，代码不要硬编码单一文件名。应当自动搜索数据集目录下的表格文件。

数据发现逻辑：

1. 从以下目录递归搜索数据文件：

```text
C:\Users\luzian\Desktop\windpower_dataset\AD\extracted
```

2. 支持格式：
   - `.csv`
   - `.parquet`
   - `.pkl`
   - `.xlsx` 只用于元信息，不作为主要训练数据

3. 优先寻找包含以下信息的文件：
   - timestamp / time / date；
   - turbine id / asset id；
   - wind farm id；
   - SCADA sensor columns；
   - status / event / label。

4. 如果多个文件对应不同风机，可以逐文件读取；如果单个大文件包含多台风机，则按 turbine id 分组。

5. 对 README 和 event_info 文件进行文本扫描，保存关键信息到报告中，但不要人工假设字段含义。代码应根据 README 和实际列名确定正常/异常标签。

---

## 4. 标签定义

原论文将 `normal operation` 视为正常行为，其它 OP-mode 视为异常，同时还结合功率和风速过滤明显不合理样本。

在公开数据集上按以下规则适配：

1. 如果数据中有明确的 `status`、`status_type_id`、`label`、`normal`、`anomaly`、`event` 字段，则优先使用这些字段。
2. 正常样本定义为正常运行状态，例如：
   - normal；
   - normal operation；
   - healthy；
   - status id 表示正常的样本。
3. 异常样本定义为：
   - 故障事件窗口；
   - abnormal / anomaly / fault；
   - 非正常运行状态；
   - README 或 event_info 中明确标注的异常状态。
4. 如果标签字段不清楚，程序必须停止，并在报告中输出候选字段，让用户确认，不要强行训练。
5. AE 训练阶段只使用正常样本。
6. 阈值选择和测试阶段需要使用 normal/anomaly 标签。

生成统一标签列：

```text
label = 0 表示 normal
label = 1 表示 anomaly
```

---

## 5. 特征筛选与预处理

按照论文思路做 SCADA 特征筛选，但适配公开数据集。

### 5.1 特征候选

保留数值型 SCADA 特征，删除以下列：

1. 时间戳；
2. turbine id / asset id；
3. wind farm id；
4. status / label / event；
5. 文件名、字符串描述、备注；
6. 明显的计数器类变量；
7. set point 类变量；
8. 低质量统计量。CARE2Compare 数据说明明确提示部分 `Min` / `Max` / `Std` 统计列可能不可信，首次跑 demo 时默认优先使用 Avg 类传感器列，不要一开始就把这些统计列全部纳入训练。

优先保留平均值类特征，例如列名包含：

```text
Avg
average
mean
```

如果 Avg 类特征太少，再保留其它连续数值 SCADA 特征，但需要在报告中说明。

首次最小复现的默认策略：

```text
优先保留：Avg / average / mean
暂缓引入：Min / Max / Std
```

如果后续需要引入 `Min` / `Max` / `Std`，报告里必须额外记录：

```text
1. 引入了哪些列；
2. 引入原因；
3. 是否出现异常值、缺失或物理不一致；
4. 相比 Avg-only 基线，结果是否变差。
```

### 5.2 删除低质量特征

对候选特征执行：

1. 删除缺失率超过 50% 的列；
2. 删除超过 80% 为 0 的列；
3. 删除常数列；
4. 删除唯一值数量小于等于 3 的低方差列；
5. 删除明显的累计计数器列，例如列名包含：
   - counter；
   - count；
   - total；
   - cumulative；
   - production since；
   - operating hours；
   - energy since；
6. 删除明显的 set point 列，例如列名包含：
   - setpoint；
   - set point；
   - reference；
   - command。

### 5.3 角度特征处理

如果列名中包含 angle、direction、yaw、azimuth 等角度含义，做 sin/cos 转换：

```python
angle_rad = np.deg2rad(angle_degree)
angle_sin = np.sin(angle_rad)
angle_cos = np.cos(angle_rad)
```

转换后删除原角度列。

### 5.4 归一化

使用 MinMaxScaler，将特征缩放到 `[0, 1]`。

注意避免数据泄漏：

1. baseline 模型的 scaler 只用目标风机 baseline_train 中的正常样本拟合；
2. transfer 模型的 scaler 只用 source_train 正常样本和 target_tuning 正常样本拟合，不允许使用 test；
3. test 数据只能 transform，不能 fit；
4. scaler 要和模型一起保存。

---

## 6. 数据划分

先实现 asset-to-asset 迁移，这是论文中最适合复现的主实验。

### 6.1 自动选择可用风机

程序应根据数据自动选择满足以下条件的风场和风机：

1. 同一风场内至少有 2 台风机；
2. 每台风机有足够长的时间序列；
3. 目标风机测试区间内至少有一部分异常样本；
4. 特征列在同一风场内能对齐。

如果可用数据不足 12 个月，可以允许降级，但要在报告中说明：

```text
优先：12个月 baseline/source train + 1/2/3个月 tuning + 1个月 test
降级：6个月 baseline/source train + 1/2个月 tuning + 1个月 test
再降级：3个月 baseline/source train + 1个月 tuning + 1个月 test
```

不能为了凑长度使用 test 数据训练。

### 6.2 时间划分

按时间排序后划分：

```text
source_train:
    源风机历史正常数据，用于训练 source AE。

baseline_train:
    目标风机较长历史正常数据，用于训练 baseline AE。

target_tuning_1m:
    测试前 1 个月目标风机数据，用于阈值更新或模型微调。

target_tuning_2m:
    测试前 2 个月目标风机数据。

target_tuning_3m:
    测试前 3 个月目标风机数据。

target_test:
    目标风机 tuning 后的后续 1 个月数据，用于最终测试。
```

AE 参数训练只使用 `label == 0` 的正常样本。

阈值选择可以使用 tuning 数据中的 normal/anomaly 标签。如果 tuning 数据只有正常样本，按原论文逻辑设置阈值为 tuning anomaly score 的最大值，并在报告中记录。

---

## 7. 模型结构

写 `src/model_ae.py`。

模型为全连接 Autoencoder，激活函数使用 PReLU。

根据输入维度自动选择结构：

```python
if input_dim >= 100:
    hidden_dims = [200, 100, 50, 100, 200]
    batch_size = 128
else:
    hidden_dims = [25, 10, 25]
    batch_size = 64
```

模型形式：

```text
input_dim → hidden_dims → input_dim
```

loss：

```python
MSELoss
```

optimizer：

```python
Adam
```

默认参数：

```yaml
learning_rate_source: 0.001
learning_rate_baseline: 0.001
learning_rate_decoder_tuning: 0.001
learning_rate_ae_tuning: 0.0001
epochs_source: 10
epochs_baseline: 10
epochs_decoder_tuning: 10
epochs_ae_tuning: 10
epochs_multi_asset_source: 30
activation: PReLU
```

所有训练必须在 CUDA 上执行。

---

## 8. Baseline 模型

写 `src/train_baseline.py`。

目标：

```text
用目标风机 baseline_train 中的正常样本，从头训练 AE。
```

步骤：

1. 读取目标风机 baseline_train；
2. 只选择 `label == 0` 的样本训练 AE；
3. 用 baseline_train 全部样本计算 anomaly score；
4. 通过最大化 F1/2-score 选择 threshold；
5. 在 target_test 上测试；
6. 保存模型、scaler、features、threshold、config。

保存路径：

```text
outputs/models/baseline_target_<target_id>.pt
```

---

## 9. Source 模型

写 `src/train_source.py`。

目标：

```text
用源风机 source_train 中的正常样本训练 source AE。
```

步骤：

1. 读取源风机 source_train；
2. 只使用正常样本训练；
3. 保存 source AE；
4. 保存 scaler、features、config。

保存路径：

```text
outputs/models/source_<source_id>.pt
```

---

## 10. Transfer Learning 三种方法

写 `src/train_transfer.py`。

### 10.1 threshold 方法

```text
不更新 AE 参数，只重新选择 threshold。
```

步骤：

1. 加载 source AE；
2. 用 source AE 对 target_tuning 数据计算 anomaly score；
3. 用 target_tuning 标签选择 threshold；
4. 在 target_test 上测试；
5. 保存结果。

模型命名：

```text
transfer_threshold_source_<source_id>_target_<target_id>_tuning_<n>m.pt
```

### 10.2 decoder 方法

```text
冻结 encoder，只微调 decoder。
```

步骤：

1. 加载 source AE；
2. 冻结 encoder 参数；
3. 只训练 decoder 参数；
4. 训练数据为 target_tuning 中的正常样本；
5. 学习率 0.001；
6. 训练 10 epochs；
7. 用 target_tuning 重新选择 threshold；
8. 在 target_test 上测试；
9. 保存结果。

模型命名：

```text
transfer_decoder_source_<source_id>_target_<target_id>_tuning_<n>m.pt
```

### 10.3 AE 方法

```text
微调整个 Autoencoder。
```

步骤：

1. 加载 source AE；
2. 所有参数可训练；
3. 训练数据为 target_tuning 中的正常样本；
4. 学习率 0.0001；
5. 训练 10 epochs；
6. 用 target_tuning 重新选择 threshold；
7. 在 target_test 上测试；
8. 保存结果。

模型命名：

```text
transfer_ae_source_<source_id>_target_<target_id>_tuning_<n>m.pt
```

注意：AE 微调整体时容易过拟合，需要保存训练 loss 曲线。

---

## 11. Anomaly Score 与阈值选择

写 `src/evaluate.py`。

### 11.1 Anomaly score

每个样本的异常分数为重构 RMSE：

```python
score = np.sqrt(np.mean((x - x_hat) ** 2, axis=1))
```

### 11.2 F1/2-score

实现：

```python
from sklearn.metrics import precision_score, recall_score, accuracy_score, fbeta_score

f12 = fbeta_score(y_true, y_pred, beta=0.5, zero_division=0)
```

### 11.3 阈值选择

在 tuning 或 training 数据上遍历候选阈值：

```python
candidate_thresholds = np.unique(scores)
```

对每个阈值：

```python
pred = (scores >= threshold).astype(int)
```

选择 F1/2-score 最大的阈值。

如果标签全为同一类：

```python
threshold = scores.max()
```

并在日志中记录：

```text
Only one class found in threshold tuning labels. Use max anomaly score as threshold.
```

### 11.4 输出指标

每个模型输出：

```text
precision
recall
accuracy
F1/2-score
threshold
num_train_normal
num_tuning_samples
num_test_samples
num_test_normal
num_test_anomaly
```

保存到：

```text
outputs/tables/baseline_metrics.csv
outputs/tables/transfer_metrics.csv
outputs/tables/delta_f12.csv
```

其中：

```text
delta_f12 = transfer_f12 - baseline_f12
```

---

## 12. Criticality 曲线

写 `src/plot_results.py` 中的 criticality 函数。

逻辑：

```python
criticality = 0

for each timestamp:
    if status is normal:
        if pred is anomaly:
            criticality = min(criticality + 1, 1000)
        else:
            criticality = max(criticality - 1, 0)
    else:
        criticality = criticality
```

注意这里的 status normal/abnormal 是运行状态，不是预测标签。若公开数据集无法清楚区分运行状态和故障标签，则用 `label == 0` 作为 normal status 的近似，并在报告中说明。

---

## 13. 图表输出

至少输出以下图。

### 13.1 baseline 性能图

```text
outputs/figures/baseline_f12_by_turbine.png
```

内容：

```text
x轴：target turbine id
y轴：F1/2-score
```

### 13.2 asset-to-asset 迁移结果图

```text
outputs/figures/asset_to_asset_delta_f12_boxplot.png
```

内容：

```text
x轴：tuning method，包含 threshold、decoder、AE
y轴：ΔF1/2-score
分组：tuning data = 1m、2m、3m
```

### 13.3 case study 图

```text
outputs/figures/case_study_anomaly_score_and_criticality.png
```

内容两行：

```text
上图：anomaly score + threshold，正常点和异常点用不同 marker
下图：baseline、threshold、decoder、AE 的 criticality 曲线对比
```

图风格要求：

1. 白色背景；
2. 字体使用 Times New Roman；
3. 不使用中文标题；
4. 坐标轴和图例简洁；
5. dpi 至少 300；
6. 图片不要过度装饰。

---

## 14. 主运行脚本

写 `src/run_all.py`，按顺序执行：

```text
1. inspect dataset
2. preprocess
3. build splits
4. train baseline
5. train source
6. transfer threshold
7. transfer decoder
8. transfer AE
9. evaluate
10. plot results
11. cleanup
```

同时写 Windows 批处理脚本：

```text
run_reproduction.bat
```

内容类似：

```bat
@echo off
call conda activate pytorch
cd /d C:\Users\luzian\Desktop\windpower_dataset\AD\wind_ae_transfer_ad_repro
python src\run_all.py --config configs\config.yaml
pause
```

运行前必须在 Python 中再次确认 CUDA 可用，不允许 CPU 训练。

---

## 15. 配置文件

写 `configs/config.yaml`，至少包含：

```yaml
project_root: "C:/Users/luzian/Desktop/windpower_dataset/AD/wind_ae_transfer_ad_repro"
dataset_root: "C:/Users/luzian/Desktop/windpower_dataset/AD"
extracted_data_dir: "C:/Users/luzian/Desktop/windpower_dataset/AD/extracted"

random_seed: 42
device: "cuda"

experiment:
  mode: "asset_to_asset"
  auto_select_turbines: true
  max_target_turbines: 5
  tuning_months: [1, 2, 3]
  test_months: 1
  prefer_train_months: 12
  fallback_train_months: [6, 3]

model:
  lr_source: 0.001
  lr_baseline: 0.001
  lr_decoder_tuning: 0.001
  lr_ae_tuning: 0.0001
  epochs_source: 10
  epochs_baseline: 10
  epochs_decoder_tuning: 10
  epochs_ae_tuning: 10
  epochs_multi_asset_source: 30
  batch_size_high_dim: 128
  batch_size_low_dim: 64

preprocess:
  missing_ratio_drop: 0.5
  zero_ratio_drop: 0.8
  low_unique_threshold: 3
  prefer_avg_features: true
  min_feature_count: 10

outputs:
  save_models: true
  save_figures: true
  save_tables: true
  cleanup_after_success: true
```

---

## 16. 最小验收标准

复现成功至少满足：

1. 能自动识别数据集结构；
2. 能生成统一预处理数据；
3. 能完成至少 1 个 source-target pair 的实验；
4. baseline AE 成功训练；
5. threshold、decoder、AE 三种迁移方式都成功运行；
6. 所有模型均在 CUDA 上训练；
7. 输出指标表：
   - `baseline_metrics.csv`
   - `transfer_metrics.csv`
   - `delta_f12.csv`
8. 输出图：
   - `baseline_f12_by_turbine.png`
   - `asset_to_asset_delta_f12_boxplot.png`
   - `case_study_anomaly_score_and_criticality.png`
9. 保存最终小模型：
   - baseline 模型；
   - source 模型；
   - decoder transfer 模型；
   - AE transfer 模型；
10. 生成复现报告：
    - `outputs/reports/final_reproduction_report.md`

---

## 17. 复现报告内容

写 `outputs/reports/final_reproduction_report.md`，包括：

1. 数据集路径；
2. 实际使用的风场和风机；
3. 实际使用的时间范围；
4. 特征数量；
5. 正常/异常样本数量；
6. 模型结构；
7. CUDA 设备名称；
8. baseline 结果；
9. transfer 结果；
10. 哪种迁移方法最好；
11. 与原论文趋势是否一致；
12. 如果结果与论文不一致，解释可能原因：
    - 原论文数据是私有数据；
    - 公开数据集标签和 OP-mode 定义不同；
    - 可用时间跨度不同；
    - 故障事件分布不同；
    - 特征维度不同。

---

## 18. 清理规则

复现成功后执行 `src/cleanup.py`。

只清理工程目录中的临时文件，不要删除原始数据集。

可以删除：

```text
temp/processed 中可重复生成的大型中间文件
temp/splits 中重复缓存
__pycache__
.ipynb_checkpoints
临时日志
失败实验的中间 checkpoint
```

必须保留：

```text
src/
configs/
run_reproduction.bat
requirements_used.txt
README_REPRODUCTION.md

outputs/models/ 中最终小模型
outputs/tables/ 中最终结果表
outputs/figures/ 中最终图片
outputs/reports/final_reproduction_report.md
outputs/logs/ 中主运行日志
```

不要删除：

```text
C:\Users\luzian\Desktop\windpower_dataset\AD\raw
C:\Users\luzian\Desktop\windpower_dataset\AD\extracted
```

除非用户明确要求删除原始数据。

---

## 19. 推荐执行顺序

不要一次性写完所有复杂功能后再运行。按下面顺序边写边测：

```text
Step 1：写 00_inspect_dataset.py，确认数据结构。
Step 2：写 01_preprocess.py，只处理一个风场和两台风机。
Step 3：写 model_ae.py，确认 CUDA 训练正常。
Step 4：写 train_baseline.py，跑通 baseline。
Step 5：写 train_source.py，跑通 source。
Step 6：写 train_transfer.py，先跑 threshold。
Step 7：加入 decoder tuning。
Step 8：加入 AE tuning。
Step 9：写 evaluate.py 输出指标。
Step 10：写 plot_results.py 输出图。
Step 11：扩展到多个 target turbines。
Step 12：生成 final_reproduction_report.md。
Step 13：执行 cleanup.py。
```

每一步都要保存日志。如果某一步失败，不要继续后面的步骤。

---

## 20. 重要注意事项

1. 原论文私有数据不可获得，因此本复现是方法复现，不是原始数值复现。
2. 不允许使用 test 数据拟合 scaler、训练模型或选择 threshold。
3. AE 训练只用正常样本。
4. threshold 选择可以使用 tuning 区间的标签。
5. 如果 tuning 区间只有正常样本，则用该区间 anomaly score 最大值作为 threshold。
6. 所有训练必须使用 GPU。
7. 不要把所有模型保存成很大的 checkpoint，只保存必要内容：
   - model state_dict；
   - scaler；
   - feature list；
   - threshold；
   - config；
   - metrics。
8. 最终优先复现 asset-to-asset，不强制做 multi-asset。asset-to-asset 跑通后，如果时间允许再补 multi-asset。
9. 结果趋势应重点看：
   - transfer 是否接近 baseline；
   - decoder tuning 是否通常优于只更新 threshold；
   - AE tuning 是否可能过拟合；
   - 小样本 tuning 是否能达到可用效果。

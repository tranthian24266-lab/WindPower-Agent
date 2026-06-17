# NREL 风电故障诊断公开数据集复现任务书

本文档用于指导 Codex 在本地逐步复现论文公开风电数据集部分。目标不是完整复现论文中 CWRU/XJTU 的所有对比实验，而是优先复现 NREL/OEDI 公开风电传动系统振动数据上的核心流程：数据检查 → 数据预处理 → MSCNN-BiLSTM 单传感器模型训练 → 多传感器加权投票融合 → 测试评估 → 清理多余文件，只保留代码、结果和最终小模型。

论文方法对应：MSCNN-BiLSTM + weighted majority voting for multi-sensors。

---

## 0. 总体要求

### 0.1 固定工作目录

所有代码、日志、模型、结果都放在：

```text
C:\Users\luzian\Desktop\windpower_dataset
```

数据集已经下载完成，不要重复下载。默认目录结构如下：

```text
C:\Users\luzian\Desktop\windpower_dataset
├─ raw
│  └─ nrel
│     ├─ zip
│     ├─ extracted
│     └─ docs
├─ processed
│  └─ nrel
├─ scripts
├─ logs
└─ results
```

如果实际目录结构和上面略有差异，先扫描并记录真实路径，不要移动原始数据，除非确实需要整理。

### 0.2 运行环境

训练必须使用本地 `pytorch` conda 环境，并启用 GPU：

```bat
conda activate pytorch
```

不要在 CPU 上训练。每个训练脚本启动后必须打印：

```python
torch.cuda.is_available()
torch.cuda.get_device_name(0)
```

如果 CUDA 不可用，立即停止并在日志中说明原因，不要自动切换到 CPU 继续训练。

### 0.3 复现范围

本次只复现公开风电数据集部分，即 NREL/OEDI Wind Turbine Gearbox Condition Monitoring Vibration Analysis Benchmarking Dataset。

不要下载 CWRU、XJTU。
不要实现论文中所有对比模型。
不要做过度工程化封装。
优先保证主链路跑通、结果可复查、最终模型足够小。

---

## 1. 需要最终保留的文件

复现成功后，最终只保留这些核心文件和目录：

```text
C:\Users\luzian\Desktop\windpower_dataset
├─ README_REPRODUCE.md
├─ scripts
│  ├─ 01_inspect_nrel_mat.py
│  ├─ 02_preprocess_nrel.py
│  ├─ 03_model_mscnn_bilstm.py
│  ├─ 04_train_single_sensor.py
│  ├─ 05_evaluate_vote.py
│  ├─ 06_cleanup_keep_final.py
│  └─ utils.py
├─ processed
│  └─ nrel
│     ├─ train_sensor1.npy
│     ├─ train_sensor2.npy
│     ├─ train_y.npy
│     ├─ val_sensor1.npy
│     ├─ val_sensor2.npy
│     ├─ val_y.npy
│     ├─ test_sensor1.npy
│     ├─ test_sensor2.npy
│     ├─ test_y.npy
│     └─ meta.json
├─ models
│  └─ nrel
│     ├─ sensor1_mscnn_bilstm_best.pth
│     ├─ sensor2_mscnn_bilstm_best.pth
│     └─ vote_weights.json
├─ results
│  └─ nrel
│     ├─ metrics.csv
│     ├─ sensor1_confusion_matrix.png
│     ├─ sensor2_confusion_matrix.png
│     ├─ majority_vote_confusion_matrix.png
│     ├─ weighted_vote_confusion_matrix.png
│     └─ reproduce_summary.md
└─ logs
   └─ nrel_reproduce.log
```

原始压缩包和解压后的原始数据可以在最终确认复现成功后删除，或者移动到 `archive_to_delete` 后再由用户手动确认删除。不要在没有成功训练和测试前删除原始数据。

---

## 2. 第一步：检查 NREL 数据结构

创建脚本：

```text
scripts\01_inspect_nrel_mat.py
```

目标：扫描 `raw\nrel\extracted` 下所有 `.mat` 文件，确认变量名、传感器通道、采样长度和文件命名规律。

### 2.1 脚本功能

脚本需要完成：

1. 递归查找所有 `.mat` 文件。
2. 打印并保存每个 `.mat` 文件的：
   - 文件路径
   - 文件大小
   - MATLAB 变量名
   - 每个变量的 shape、dtype
   - 是否包含 AN5、AN6、AN8、AN9 或类似传感器字段
   - 是否包含高速轴 RPM 或转速相关字段
3. 输出到：

```text
logs\nrel_mat_structure.txt
```

### 2.2 读取方式

优先使用：

```python
from scipy.io import loadmat
```

如果某些文件是 HDF5 v7.3 格式，再尝试：

```python
import h5py
```

不要只凭文件名猜测变量结构，必须实际打开文件检查。

---

## 3. 第二步：构建 NREL 四分类数据集

创建脚本：

```text
scripts\02_preprocess_nrel.py
```

目标：从 NREL 原始 `.mat` 文件中构建四分类数据集。

### 3.1 类别定义

按照论文 NREL 公开数据集部分构建 4 类：

```text
0: Healthy condition 1
1: Healthy condition 2
2: HS-SH downwind bearing overheating
3: IMS-SH downwind bearings damage
```

论文中的传感器设置为：

```text
Class 0: train AN8, test AN9, Healthy condition 1
Class 1: train AN5, test AN6, Healthy condition 2
Class 2: train AN8, test AN9, HS-SH downwind bearing overheating
Class 3: train AN5, test AN6, IMS-SH downwind bearings damage
```

复现时为了实现多传感器投票，整理成两个传感器视角：

```text
sensor1: 优先使用 AN8/AN9 这一组
sensor2: 优先使用 AN5/AN6 这一组
```

如果实际文件中 AN5、AN6、AN8、AN9 的命名方式不同，脚本需要自动打印候选变量，人工选择最接近的通道后再继续。不要静默使用错误通道。

### 3.2 样本切片

每个样本长度：

```text
4096
```

每个类别尽量构建：

```text
train: 200 samples/class
val: 50 samples/class
test: 200 samples/class
```

如果某类数据不足，使用实际可切出的最大数量，并在 `processed\nrel\meta.json` 中记录。不要通过重复复制样本凑数。

建议滑窗设置：

```text
window_size = 4096
train_stride = 4096
test_stride = 4096
```

如果样本不够，再把 stride 改为 2048，但必须在 `meta.json` 记录。

### 3.3 标准化

每个样本独立做 z-score 标准化：

```python
x = (x - x.mean()) / (x.std() + 1e-8)
```

保存为 `float32`。

### 3.4 输出文件

输出到：

```text
processed\nrel
```

文件名固定为：

```text
train_sensor1.npy
train_sensor2.npy
train_y.npy
val_sensor1.npy
val_sensor2.npy
val_y.npy
test_sensor1.npy
test_sensor2.npy
test_y.npy
meta.json
```

数组形状要求：

```text
X: [N, 1, 4096]
y: [N]
```

脚本结尾必须打印每个文件的 shape、类别分布和保存路径。

---

## 4. 第三步：实现 MSCNN-BiLSTM 模型

创建脚本：

```text
scripts\03_model_mscnn_bilstm.py
```

目标：用 PyTorch 实现论文主模型的可训练版本。

### 4.1 模型结构

输入：

```text
[N, 1, 4096]
```

主结构：

```text
Continuous multi-scale coarse-grained layer
→ parallel 1D CNN feature extractor
→ BiLSTM
→ Dropout
→ FC classifier
```

### 4.2 多尺度层

实现一个简化但贴近论文的 continuous multi-scale coarse-grained layer。

建议使用多个尺度：

```python
scales = [1, 2, 3]
```

对每个尺度 t：

- t=1 时直接输出原始信号。
- t>1 时使用一维平均池化模拟连续粗粒化，保持输出长度仍为 4096。
- 三个尺度输出分别送入相同结构的 CNN 分支，最后 concat。

不要使用会改变样本长度且无法进入后续 CNN 的传统非连续粗粒化。

### 4.3 CNN 参数

单个 CNN 分支按论文 Table 2 的思路实现：

```text
Conv1: in_channels=1, out_channels=16, kernel_size=128, stride=5
BatchNorm1d
ReLU
MaxPool1d: kernel_size=64, stride=3

Conv2: in_channels=16, out_channels=32, kernel_size=2, stride=2
BatchNorm1d
ReLU
MaxPool1d: kernel_size=3, stride=2

Conv3: in_channels=32, out_channels=8, kernel_size=2, stride=1
BatchNorm1d
ReLU
MaxPool1d: kernel_size=3, stride=2
```

三个尺度分支输出后 concat。随后把特征整理为 BiLSTM 输入：

```text
batch_first=True
shape = [N, sequence_length, feature_dim]
```

### 4.4 BiLSTM 与分类层

建议参数：

```python
lstm_hidden = 64
lstm_layers = 1
bidirectional = True
dropout = 0.5
num_classes = 4
```

分类：

```text
BiLSTM last output → Dropout → Linear → logits
```

训练时使用 `CrossEntropyLoss`，所以模型输出 logits，不要提前 softmax。

---

## 5. 第四步：训练单传感器模型

创建脚本：

```text
scripts\04_train_single_sensor.py
```

目标：分别训练 sensor1 和 sensor2 两个 MSCNN-BiLSTM 子模型。

### 5.1 命令格式

必须支持：

```bat
conda activate pytorch

python scripts\04_train_single_sensor.py --sensor sensor1 --epochs 80 --batch_size 256 --lr 0.001
python scripts\04_train_single_sensor.py --sensor sensor2 --epochs 80 --batch_size 256 --lr 0.001
```

### 5.2 训练配置

默认配置：

```text
optimizer: Adam
learning_rate: 0.001
batch_size: 256
epochs: 80
loss: CrossEntropyLoss
metric: accuracy, macro-F1
early stopping patience: 15
```

如果显存不足，把 batch size 改为 128，并记录到日志。

### 5.3 GPU 要求

脚本必须：

1. 检查 CUDA。
2. 打印 GPU 名称。
3. 把 model 和 data 放到 CUDA。
4. 如果 CUDA 不可用，直接报错退出。

不要自动使用 CPU。

### 5.4 保存模型

每个传感器保存验证集 macro-F1 最好的模型：

```text
models\nrel\sensor1_mscnn_bilstm_best.pth
models\nrel\sensor2_mscnn_bilstm_best.pth
```

保存内容包括：

```python
{
    "model_state_dict": model.state_dict(),
    "config": config,
    "best_val_f1": best_val_f1,
    "epoch": best_epoch,
    "label_names": [...]
}
```

训练日志保存到：

```text
logs\train_sensor1.log
logs\train_sensor2.log
```

---

## 6. 第五步：测试与多传感器投票

创建脚本：

```text
scripts\05_evaluate_vote.py
```

目标：加载两个传感器模型，分别测试单模型结果，并实现 majority voting 与 weighted majority voting。

### 6.1 输出内容

输出以下指标：

```text
accuracy
macro-F1
per-class F1
confusion matrix
```

结果保存为：

```text
results\nrel\metrics.csv
results\nrel\sensor1_confusion_matrix.png
results\nrel\sensor2_confusion_matrix.png
results\nrel\majority_vote_confusion_matrix.png
results\nrel\weighted_vote_confusion_matrix.png
results\nrel\reproduce_summary.md
```

### 6.2 普通多数投票

对于每个样本：

```python
pred1 = sensor1 prediction
pred2 = sensor2 prediction
```

如果两个传感器预测一致，直接取该类。

如果不一致，用两个模型中最大 softmax 置信度更高的预测作为最终结果。原因是只有两个传感器时，普通多数投票会出现平票。

### 6.3 加权投票

先实现手动权重版，权重参考论文 NREL 部分：

```python
weights = {
    0: [1, 2],
    1: [1, 2],
    2: [1, 2],
    3: [1, 1],
}
```

含义：

```text
每个类别都有一个 [sensor1_weight, sensor2_weight]
```

对每个样本，计算每个类别的加权票数：

```python
score[class_id] = 0
score[pred1] += weights[pred1][0]
score[pred2] += weights[pred2][1]
final_pred = argmax(score)
```

如果加权票数仍然相同，用两个模型对应类别 softmax 置信度之和打破平票。

### 6.4 可选 GA 权重搜索

如果前面的训练和测试已经跑通，可以增加一个简单 GA 或网格搜索版本：

```text
候选权重: 1, 2, 3
目标函数: validation macro-F1
搜索对象: 4 个类别 × 2 个传感器的权重矩阵
```

不要为了 GA 写复杂框架。优先使用网格/随机搜索，得到最优权重后保存：

```text
models\nrel\vote_weights.json
```

如果搜索后的权重没有超过手动权重，就保留手动权重，并在 summary 中说明。

---

## 7. 第六步：结果判断标准

本复现不要求逐数值等于论文，因为论文没有完整公开代码、随机种子、具体切片索引和完整文件划分细节。

复现成功标准：

1. 能成功读取 NREL 数据。
2. 能构建 4 分类数据集。
3. 能在 GPU 上训练两个单传感器 MSCNN-BiLSTM 模型。
4. 能输出单传感器和融合后的混淆矩阵。
5. weighted voting 的 macro-F1 不低于两个单传感器中较差的一个。
6. `results\nrel\reproduce_summary.md` 中清楚记录：
   - 使用了哪些原始文件
   - 使用了哪些通道
   - 每类样本数
   - 切片长度和 stride
   - 模型超参数
   - 单传感器结果
   - majority voting 结果
   - weighted voting 结果
   - 与论文设置不完全一致的地方

---

## 8. 第七步：清理多余资料

创建脚本：

```text
scripts\06_cleanup_keep_final.py
```

目标：在复现成功后清理多余资料，只保留代码、最终模型和最终结果。

### 8.1 清理前检查

脚本必须先检查这些文件是否存在：

```text
models\nrel\sensor1_mscnn_bilstm_best.pth
models\nrel\sensor2_mscnn_bilstm_best.pth
results\nrel\metrics.csv
results\nrel\weighted_vote_confusion_matrix.png
results\nrel\reproduce_summary.md
```

如果缺任何一个，不允许清理。

### 8.2 清理方式

不要直接永久删除。先把以下目录移动到：

```text
archive_to_delete
```

可移动内容：

```text
raw\nrel\zip
raw\nrel\extracted
```

保留：

```text
raw\nrel\docs
```

也就是说，论文说明文档和 license 保留，原始大数据可以归档待删除。

### 8.3 用户确认

脚本运行时必须打印：

```text
The reproduction has finished. Large raw data have been moved to archive_to_delete.
Please manually delete archive_to_delete after confirming all results are valid.
```

不要自动清空回收站，不要永久删除。

---

## 9. 建议执行顺序

严格按下面顺序执行，每一步完成后检查输出文件再继续：

```bat
conda activate pytorch

python scripts\01_inspect_nrel_mat.py

python scripts\02_preprocess_nrel.py

python scripts\04_train_single_sensor.py --sensor sensor1 --epochs 80 --batch_size 256 --lr 0.001

python scripts\04_train_single_sensor.py --sensor sensor2 --epochs 80 --batch_size 256 --lr 0.001

python scripts\05_evaluate_vote.py

python scripts\06_cleanup_keep_final.py
```

注意：`03_model_mscnn_bilstm.py` 是被训练脚本导入的模型文件，不需要单独运行。

---

## 10. 写代码风格要求

1. 代码尽量简单，不要过度封装。
2. 每个脚本都要有清晰的 main 函数。
3. 所有路径统一使用 `pathlib.Path`。
4. 所有随机种子固定为：

```python
seed = 42
```

5. 训练日志必须同时输出到终端和 log 文件。
6. 绘制混淆矩阵时不要加大标题，图片只保留坐标轴标签和类别名。
7. 保存图片分辨率：

```python
dpi = 300
```

8. 如果遇到实际数据字段和本文档不一致，先写一个清晰的报错和候选字段列表，不要静默猜测。

---

## 11. 最终总结文件要求

`results\nrel\reproduce_summary.md` 至少包含：

```text
# NREL MSCNN-BiLSTM Reproduction Summary

## Dataset
- Source files used:
- Sensor channels used:
- Sampling frequency if available:
- Window size:
- Stride:
- Class mapping:
- Train/val/test sample counts:

## Model
- Multi-scale settings:
- CNN structure:
- BiLSTM hidden size:
- Dropout:
- Optimizer:
- Learning rate:
- Batch size:
- Epochs:
- Device:

## Results
| Method | Accuracy | Macro-F1 | Class 0 F1 | Class 1 F1 | Class 2 F1 | Class 3 F1 |
|---|---:|---:|---:|---:|---:|---:|
| Sensor1 | | | | | | |
| Sensor2 | | | | | | |
| Majority Vote | | | | | | |
| Weighted Vote | | | | | | |

## Notes
- Differences from the paper:
- Problems encountered:
- Final kept files:
```

---

## 12. 重要提醒

这次任务的核心是“可复现的工程链路”，不是追求和论文完全相同的小数点结果。论文没有公开完整代码和所有划分细节，因此只要数据来源、类别设置、模型结构、训练流程、多传感器投票机制和评估指标对齐，就可以视为公开数据集部分复现成功。

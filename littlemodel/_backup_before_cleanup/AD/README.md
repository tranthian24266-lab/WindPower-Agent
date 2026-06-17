# Wind Turbine Anomaly Detection — 部署小模型

## 概述

本模型用于**风机 SCADA 数据异常检测**，基于 Autoencoder 迁移学习。

- **任务**: 风机异常检测 (Anomaly Detection)
- **模型类型**: 全连接 Autoencoder（Decoder Tuning 迁移学习）
- **输入**: 55 维 SCADA 传感器特征
- **输出**: anomaly_score（RMSE） + 二分类预测（normal / anomaly）
- **来源风机（Source）**: Turbine 13
- **目标风机（Target）**: Turbine 10
- **测试 F1/2**: **0.6572**
- **测试 Precision**: 0.7194
- **测试 Recall**: 0.4883
- **测试 Accuracy**: 0.7126

---

## 文件说明

```
C:\Users\luzian\Desktop\littlemodel\AD\
├── README.md                    # 本文件
├── best_anomaly_model.pt        # 部署模型（PyTorch checkpoint）
├── model_metadata.json          # 模型元信息（JSON格式）
├── test_data_sample.csv          # 测试数据样本 1000行（含标签）
└── inference_anomaly.py         # 推理脚本（可选）
```

---

## 模型详情

### 架构

```
输入 (55) → 全连接层1 (25) → PReLU 
         → 全连接层2 (10, 潜变量) → PReLU 
         → 全连接层3 (25) → PReLU 
         → 全连接层4 (55, 输出)
```

- **激活函数**: PReLU
- **训练方式**: 冻结 Encoder（source=13 预训练），仅微调 Decoder 在目标风机（target=10）上调优 10 epochs
- **学习率**: 0.001 (Decoder tuning)

### 输入特征（55维 SCADA 传感器，均为 10分钟平均值）

```
sensor_0_avg, wind_speed_3_avg, wind_speed_4_avg,
sensor_6_avg, sensor_7_avg, sensor_8_avg, sensor_9_avg,
sensor_10_avg, sensor_11_avg, sensor_12_avg, sensor_13_avg,
sensor_14_avg, sensor_15_avg, sensor_16_avg, sensor_17_avg,
sensor_18_avg, sensor_19_avg, sensor_20_avg, sensor_21_avg,
sensor_22_avg, sensor_23_avg, sensor_24_avg, sensor_25_avg,
reactive_power_27_avg, reactive_power_28_avg,
power_29_avg, power_30_avg,
sensor_31_avg, sensor_32_avg, sensor_33_avg, sensor_34_avg,
sensor_35_avg, sensor_36_avg, sensor_37_avg,
sensor_38_avg, sensor_39_avg, sensor_40_avg, sensor_41_avg,
sensor_43_avg,
sensor_44, sensor_45, sensor_47, sensor_48,
sensor_50, sensor_51, sensor_52_avg, sensor_53_avg,
sensor_1_avg_sin, sensor_1_avg_cos,
sensor_2_avg_sin, sensor_2_avg_cos,
sensor_5_avg_sin, sensor_5_avg_cos,
sensor_42_avg_sin, sensor_42_avg_cos
```

完整特征列表见 `model_metadata.json` 中的 `feature_cols` 字段。

### 数据预处理

输入数据需要按以下步骤处理（详见推理代码）：

1. **特征选择**: 只取上述 55 列
2. **缺失值**: NaN 填充为 0
3. **归一化**: 使用保存在模型中的 `MinMaxScaler`（已 fit 在 source train + target tuning normal 数据上）
4. **注意**: 归一化必须在 [0, 1] 范围内，使用模型自带的 scaler，不要用新的 scaler

### 异常分数

每个样本的异常分数 = **RMSE reconstruction error**:

```
anomaly_score = sqrt(mean((x - x_hat)^2, axis=1))
```

### 异常判定

- **threshold**: 0.04287（在目标风机调优集上通过最大化 F1/2-score 选出）
- anomaly_score >= threshold → **anomaly (1)**
- anomaly_score < threshold → **normal (0)**

---

## 快速使用

### Python 推理

```python
import torch
import pickle
import numpy as np
import pandas as pd

# 1. 加载模型
ckpt = torch.load('best_anomaly_model.pt', map_location='cpu', weights_only=False)

# 2. 构建模型
class WindAutoencoder(torch.nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.encoder = torch.nn.Sequential(
            torch.nn.Linear(input_dim, 25), torch.nn.PReLU(),
            torch.nn.Linear(25, 10), torch.nn.PReLU(),
        )
        self.decoder = torch.nn.Sequential(
            torch.nn.Linear(10, 25), torch.nn.PReLU(),
            torch.nn.Linear(25, input_dim),
        )
    def forward(self, x):
        return self.decoder(self.encoder(x))

input_dim = ckpt['input_dim']
model = WindAutoencoder(input_dim)
model.load_state_dict(ckpt['state_dict'])
model.eval()

# 3. 预处理
df = pd.read_csv('your_data.csv')
features = ckpt['feature_cols']
X = df[features].fillna(0).values.astype(np.float64)
X_scaled = ckpt['scaler'].transform(X).astype(np.float32)

# 4. 推理
with torch.no_grad():
    X_t = torch.tensor(X_scaled)
    X_hat = model(X_t)
    scores = torch.sqrt(torch.mean((X_t - X_hat)**2, dim=1)).numpy()

# 5. 判定
threshold = ckpt['threshold']
predictions = (scores >= threshold).astype(int)
df['anomaly_score'] = scores
df['prediction'] = predictions  # 0=normal, 1=anomaly
```

### 测试数据

`test_data_sample.csv` 包含 1000 行目标风机 Turbine 10 的实际 SCADA 数据：
- **500 条正常样本** (sample_label=0)
- **500 条异常样本** (sample_label=1)
- 可用于验证推理管线

---

## 训练来源

本模型来自论文复现实验：

**论文**: "Transfer learning applications for autoencoder-based anomaly detection in wind turbines"

**数据集**: CARE To Compare — Wind Farm A（葡萄牙陆上风场，EDP Open Data）

**训练环境**:
- Python 3.9.23
- PyTorch 2.8.0+cu129
- CUDA 12.9
- GPU: NVIDIA GeForce RTX 5070 Laptop GPU
- Conda env: `pytorch`

**训练代码**: `C:\Users\luzian\Desktop\windpower_dataset\AD\wind_ae_transfer_ad_repro\`

### 复现项目结构

```
wind_ae_transfer_ad_repro/
├── src/
│   ├── 00_inspect_dataset.py    # 数据检查
│   ├── 01_preprocess.py         # 预处理（特征筛选 + 归一化）
│   ├── 02_build_splits.py       # 数据划分（事件级隔离）
│   ├── model_ae.py              # AE 模型定义
│   ├── train_source.py          # 源风机 AE 训练
│   ├── train_baseline.py        # 目标风机 Baseline AE
│   ├── train_transfer.py        # 三种迁移方法
│   ├── evaluate.py              # 指标计算
│   ├── plot_results.py          # 图表输出
│   └── inference_anomaly.py     # 推理脚本
├── configs/config.yaml
├── outputs/
│   ├── models/          # 70个训练模型
│   ├── tables/          # 5张结果表
│   ├── figures/         # 4张结果图
│   └── reports/         # 复现报告
└── temp/processed/      # 预处理数据缓存
```

---

## 标签定义

| 标签值 | 含义 | 数据来源 |
|--------|------|----------|
| 0 | **Normal** 正常运行 | `status_type_id` ∈ {0, 2}（Normal Operation / Idling） |
| 1 | **Anomaly** 异常 | `status_type_id` ∉ {0, 2}（Derated / Service / Downtime / Other） |

### Wind Farm A 异常事件类型

| Event ID | 目标风机 | 故障描述 |
|----------|----------|----------|
| 40 | Turbine 10 | Generator bearing failure |
| 42 | Turbine 10 | Hydraulic group |
| 10 | Turbine 10 | Gearbox failure |

---

## 性能对比

在 20 组 source→target 迁移实验中的平均表现：

| 方法 | 平均 F1/2 | 平均 Precision | 平均 Recall |
|------|-----------|----------------|-------------|
| Baseline（目标自训练） | 0.3609 | — | — |
| Threshold 迁移 | 0.3698 | 0.3919 | 0.4677 |
| Decoder 微调 | **0.4096** | 0.4150 | 0.4368 |
| AE 全微调 | 0.4099 | 0.4166 | 0.4469 |

**本模型（13→10 Decoder）在全部实验中排名第1（F1/2=0.6572）**。

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v2 | 2026-06-03 | 修复 scaler 不一致、事件泄漏、多 target 覆盖、阈值搜索优化 |
| v1 | 2026-06-03 | 初始版本（仅 target=0，scaler 混合使用，已废弃） |

v1 旧结果归档于 `outputs/archive_before_fix_20260603_142544/`。

---

## 注意事项

1. **不要重新拟合 scaler** — 必须使用模型自带的 `MinMaxScaler`
2. **特征名必须完全匹配** — 缺失的特征列用 0 填充
3. **输入顺序** 必须与 `feature_cols` 列表一致
4. **数据频率** 应为 10 分钟 SCADA 平均值
5. **threshold** 是在目标风机调优集上优化的，不同风机可能需要重新选择阈值
6. 模型在 **正常数据上训练**（只见过 normal），异常分数基于重构误差

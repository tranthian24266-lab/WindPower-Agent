# Wind Turbine HSSB RUL 论文复现指南（SK-derived indices + SVR）

## 0. 复现目标

本项目用于复现论文：

> Saidi et al., *Wind turbine high-speed shaft bearings health prognosis through a spectral Kurtosis-derived indices and SVR*, Applied Acoustics, 2017.

目标不是做深度学习模型，而是复现论文中的经典信号处理 + 机器学习流程：

```text
风机高速轴轴承振动数据
→ 传统时域特征
→ Spectral Kurtosis (SK)
→ SK-derived degradation indices
→ Area under SK 健康指标
→ SVR 预测 RUL
→ 输出图表、指标和最终小模型
```

重点复现内容：

1. 读取 50 个 `data-*.mat` 文件。
2. 计算传统时域特征：Mean、Std、Skewness、Kurtosis、Peak-to-Peak。
3. 计算 Spectral Kurtosis 曲线。
4. 提取 SK-derived 特征：SK_Mean、SK_Std、SK_Skewness、SK_Kurtosis、SK_Peak2Peak、SK_Area。
5. 计算健康指标的 Monotonicity 和 Trendability。
6. 用 `Kurtosis + SVR` 做 baseline。
7. 用 `Area under SK + SVR` 做主方法。
8. 按时间顺序做两组实验：
   - 前 60% 训练，后 40% 测试。
   - 前 40% 训练，后 60% 测试。
9. 生成论文风格结果图和最终训练好的小模型文件。
10. 复现完成后删除中间冗余资料，只保留必要代码、最终特征、图表、日志和小模型。

---

## 1. 已有数据位置

数据已经下载并检查完成，路径固定为：

```text
C:\Users\luzian\Desktop\windpower_dataset\RUL\WindTurbineHighSpeedBearingPrognosis-Data
```

检查结果：

```text
已发现 50 个 data-*.mat 文件
每个文件包含 vibration 和 tach
vibration_length = 585936
tach 非空
vibration 无 NaN / Inf
读取方式为 scipy.io.loadmat
采样率 fs = 97656 Hz
```

因此不需要重新下载数据集。后续任务从数据读取和复现代码开始。

---

## 2. 环境要求

在执行任何 Python 脚本前，先激活本地环境：

```bat
conda activate pytorch
```

注意：

- 这篇论文的核心模型是 `sklearn.svm.SVR`，它本身不是 CUDA 模型，通常运行在 CPU 上。
- 不要为了使用 GPU 而额外改成深度学习模型，否则会偏离论文。
- 仍然需要在脚本启动时检测 CUDA，并把检测结果写入日志，用于确认本地环境正常。
- 如果后续没有使用 GPU，不要判定为错误，因为 SVR 复现本身不依赖 CUDA。

建议依赖：

```bat
pip install numpy scipy pandas scikit-learn matplotlib joblib tqdm
```

如已安装则跳过。

---

## 3. 推荐项目结构

请在下面目录内完成所有复现工作：

```text
C:\Users\luzian\Desktop\windpower_dataset\RUL
```

最终结构建议如下：

```text
RUL
│
├── WindTurbineHighSpeedBearingPrognosis-Data
│   ├── data-20130307T015746Z.mat
│   ├── ...
│   └── data-*.mat
│
├── reproduction
│   ├── README_reproduce.md
│   ├── requirements.txt
│   ├── run_all.py
│   │
│   ├── src
│   │   ├── config.py
│   │   ├── data_io.py
│   │   ├── feature_extraction.py
│   │   ├── metrics.py
│   │   ├── train_svr.py
│   │   ├── plot_results.py
│   │   └── cleanup.py
│   │
│   ├── outputs
│   │   ├── features
│   │   │   ├── traditional_features.csv
│   │   │   ├── sk_features.csv
│   │   │   └── all_features.csv
│   │   │
│   │   ├── models
│   │   │   ├── svr_area_sk_60_40.joblib
│   │   │   ├── svr_area_sk_40_60.joblib
│   │   │   └── svr_kurtosis_baseline_60_40.joblib
│   │   │
│   │   ├── figures
│   │   │   ├── fig_feature_trends.png
│   │   │   ├── fig_monotonicity_trendability.png
│   │   │   ├── fig_svr_fit_kurtosis_vs_area_sk.png
│   │   │   ├── fig_rul_prediction_area_sk_60_40.png
│   │   │   └── fig_rul_prediction_area_sk_40_60.png
│   │   │
│   │   └── reports
│   │       ├── metrics_summary.csv
│   │       ├── reproduction_log.txt
│   │       └── final_summary.md
│   │
│   └── _tmp
```

---

## 4. 复现脚本设计

### 4.1 `config.py`

统一写路径和参数：

```python
from pathlib import Path

ROOT = Path(r"C:\Users\luzian\Desktop\windpower_dataset\RUL")
DATA_DIR = ROOT / "WindTurbineHighSpeedBearingPrognosis-Data"
WORK_DIR = ROOT / "reproduction"

OUTPUT_DIR = WORK_DIR / "outputs"
FEATURE_DIR = OUTPUT_DIR / "features"
MODEL_DIR = OUTPUT_DIR / "models"
FIGURE_DIR = OUTPUT_DIR / "figures"
REPORT_DIR = OUTPUT_DIR / "reports"
TMP_DIR = WORK_DIR / "_tmp"

FS = 97656
EXPECTED_NUM_FILES = 50

# STFT/SK 参数
SK_NPERSEG = 128
SK_NOVERLAP = SK_NPERSEG // 2

# RUL 设置：最后一个测点为失效点
RUL_START_FROM_N_MINUS_1 = True

# SVR 网格搜索参数
SVR_PARAM_GRID = {
    "svr__C": [1, 10, 100, 1000],
    "svr__gamma": ["scale", 0.001, 0.01, 0.1],
    "svr__epsilon": [0.01, 0.05, 0.1, 0.5],
}
```

---

### 4.2 `data_io.py`

功能：

1. 搜索 `data-*.mat`。
2. 按文件名排序。
3. 使用 `scipy.io.loadmat` 读取。
4. 返回 `vibration`、`tach`、文件名、测点序号。
5. 对读取失败、变量缺失、空数组、NaN/Inf 给出明确报错。

要求：

- 不要随机打乱文件。
- 文件顺序就是时间顺序。
- 如果文件数量不是 50，写 WARNING，但不要立即退出。
- 如果 `vibration` 缺失或为空，必须停止。

---

### 4.3 `feature_extraction.py`

需要实现传统特征和 SK-derived 特征。

#### 4.3.1 传统时域特征

对每个 `vibration` 计算：

```text
mean
std
skewness
kurtosis
peak_to_peak
rms
```

其中论文主比较指标为：

```text
mean
std
skewness
kurtosis
peak_to_peak
```

`rms` 可以保留作为补充，但不要作为主结果重点。

#### 4.3.2 Spectral Kurtosis

用 STFT 近似计算 SK：

```python
from scipy.signal import stft
import numpy as np

def compute_spectral_kurtosis(x, fs, nperseg=128, noverlap=64):
    f, t, Zxx = stft(
        x,
        fs=fs,
        nperseg=nperseg,
        noverlap=noverlap,
        detrend=False,
        boundary=None,
        padded=False,
    )
    abs_z = np.abs(Zxx)
    m2 = np.mean(abs_z ** 2, axis=1)
    m4 = np.mean(abs_z ** 4, axis=1)
    sk = m4 / (m2 ** 2 + 1e-12) - 2.0
    return f, sk
```

说明：

- 论文使用 SK/Kurtogram 思路定位冲击故障特征。
- 本复现采用 STFT 形式的 SK 近似实现，重点复现退化指标趋势和 SVR-RUL 预测链路。
- 不要过度追求与 MATLAB 图像逐点一致，优先保证流程、趋势和结果合理。

#### 4.3.3 SK-derived 特征

对每个测点的 `SK(f)` 计算：

```text
sk_mean
sk_std
sk_skewness
sk_kurtosis
sk_peak_to_peak
sk_area
sk_area_positive
sk_max
```

其中主方法使用：

```text
sk_area
```

`sk_area` 默认定义为：

```python
sk_area = np.trapz(sk, f)
```

同时保留一个备选指标：

```python
sk_area_positive = np.trapz(np.maximum(sk, 0), f)
```

后续主结果先使用 `sk_area`。如果 `sk_area` 趋势明显异常，再在日志中说明并尝试 `sk_area_positive`，但不要偷偷替换。

#### 4.3.4 输出特征文件

保存：

```text
outputs/features/traditional_features.csv
outputs/features/sk_features.csv
outputs/features/all_features.csv
```

`all_features.csv` 至少包含：

```text
index
file_name
date_string
rul
mean
std
skewness
kurtosis
peak_to_peak
rms
sk_mean
sk_std
sk_skewness
sk_kurtosis
sk_peak_to_peak
sk_area
sk_area_positive
sk_max
```

RUL 标签构造：

```python
N = len(files)
rul = np.arange(N - 1, -1, -1)
```

即最后一个测点的 RUL 为 0。

---

### 4.4 `metrics.py`

实现：

```python
def monotonicity(x):
    dx = np.diff(x)
    pos = np.sum(dx > 0)
    neg = np.sum(dx < 0)
    return abs(pos - neg) / max(len(dx), 1)

def trendability(x):
    t = np.arange(len(x))
    if np.std(x) < 1e-12:
        return 0.0
    return abs(np.corrcoef(t, x)[0, 1])
```

说明：

- 论文中的 Trendability 原定义更适合多个 run-to-failure 设备之间比较。
- 当前数据只有一个 HSSB 退化过程，因此这里用“特征与时间序列的绝对相关系数”作为单设备趋势性近似。
- 在 `final_summary.md` 里必须说明这个差异。

---

### 4.5 `train_svr.py`

训练三类模型：

#### A. Baseline：Kurtosis + SVR，60/40

输入：

```text
X = kurtosis
y = rul
split = int(0.6 * N)
```

输出模型：

```text
outputs/models/svr_kurtosis_baseline_60_40.joblib
```

#### B. 主方法：Area under SK + SVR，60/40

输入：

```text
X = sk_area
y = rul
split = int(0.6 * N)
```

输出模型：

```text
outputs/models/svr_area_sk_60_40.joblib
```

#### C. 主方法：Area under SK + SVR，40/60

输入：

```text
X = sk_area
y = rul
split = int(0.4 * N)
```

输出模型：

```text
outputs/models/svr_area_sk_40_60.joblib
```

#### 训练要求

必须按时间顺序切分，不能随机打乱。

使用 sklearn Pipeline：

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("svr", SVR(kernel="rbf")),
])
```

可以用 `TimeSeriesSplit` 在训练集内部做网格搜索：

```python
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=3)
grid = GridSearchCV(
    pipe,
    param_grid=SVR_PARAM_GRID,
    scoring="neg_root_mean_squared_error",
    cv=tscv,
)
```

注意：

- `StandardScaler` 只能在训练集上 fit。
- 测试集不能参与归一化、调参或模型选择。
- 不允许 `shuffle=True`。
- 保存预测结果到 `metrics_summary.csv` 和单独预测 CSV。

评价指标：

```text
MAE
RMSE
R2
```

预测结果 CSV 至少包含：

```text
index
file_name
true_rul
pred_rul
split_type
feature_used
is_train
```

---

### 4.6 `plot_results.py`

生成论文风格图，不需要完全照搬论文排版，但内容要对应。

#### 图 1：特征趋势图

输出：

```text
outputs/figures/fig_feature_trends.png
```

内容：

- 传统特征趋势：Kurtosis、Skewness、Mean、Std、Peak-to-Peak。
- SK-derived 特征趋势：SK_Kurtosis、SK_Skewness、SK_Mean、SK_Std、SK_Peak-to-Peak、SK_Area。

要求：

- 横轴为 1 到 50 的测点序号。
- 图中不要使用中文。
- 字体优先 Times New Roman。
- 图片 dpi >= 300。

#### 图 2：Monotonicity / Trendability

输出：

```text
outputs/figures/fig_monotonicity_trendability.png
```

内容：

- 对传统特征和 SK-derived 特征分别画柱状图。
- 指标包括 Monotonicity 和 Trendability。
- 用于对齐论文 Fig. 6 的分析逻辑。

#### 图 3：SVR 拟合对比

输出：

```text
outputs/figures/fig_svr_fit_kurtosis_vs_area_sk.png
```

内容：

- 左图：Kurtosis 原始健康指标与 SVR 平滑/拟合趋势。
- 右图：Area under SK 原始健康指标与 SVR 平滑/拟合趋势。
- 重点展示 Area under SK 比普通 Kurtosis 更适合作为退化趋势指标。

如果实现“SVR 拟合健康指标”不方便，可以改为画健康指标本身的趋势，并在标题/说明中注明该图主要用于指标趋势对比。

#### 图 4：RUL 预测，60/40

输出：

```text
outputs/figures/fig_rul_prediction_area_sk_60_40.png
```

内容：

- 真实 RUL 曲线。
- 预测 RUL 曲线。
- 用竖线标出训练/测试分界点。
- 标注 Train/Test，但不要过度装饰。

#### 图 5：RUL 预测，40/60

输出：

```text
outputs/figures/fig_rul_prediction_area_sk_40_60.png
```

内容同上。

---

### 4.7 `run_all.py`

一键执行完整复现流程：

```text
1. 创建输出目录
2. 检查 CUDA 和 Python 环境
3. 读取 50 个 .mat 文件
4. 提取传统特征
5. 计算 SK 和 SK-derived 特征
6. 构造 RUL 标签
7. 计算 Monotonicity / Trendability
8. 训练 SVR 模型
9. 生成所有图表
10. 保存 final_summary.md
11. 执行 cleanup
```

运行方式：

```bat
cd C:\Users\luzian\Desktop\windpower_dataset\RUL\reproduction
conda activate pytorch
python run_all.py
```

---

## 5. 最终总结文件 `final_summary.md`

`outputs/reports/final_summary.md` 必须包含：

```text
1. 数据路径
2. 文件数量
3. 采样率
4. 特征提取方法
5. SK 实现方式
6. RUL 标签定义
7. 训练/测试划分方式
8. SVR 参数
9. 评价指标结果
10. 生成的模型文件
11. 生成的图表文件
12. 与原论文的差异说明
```

差异说明必须写清楚：

```text
- 原论文未给出完整 SVR 超参数，因此本复现使用训练集 TimeSeriesSplit 网格搜索选择参数。
- 原论文基于 SK/Kurtogram 思路，本复现采用 STFT 形式计算 Spectral Kurtosis。
- Trendability 原定义更适合多个设备，本复现数据只有一个 run-to-failure 过程，因此使用特征与时间的绝对相关性作为单设备趋势性近似。
- SVR 是 sklearn 模型，通常不使用 CUDA；本复现仍在 pytorch 环境下运行并记录 CUDA 可用性。
```

---

## 6. 清理规则

复现成功后，删除冗余内容，只保留必要文件。

### 必须保留

```text
reproduction/README_reproduce.md
reproduction/requirements.txt
reproduction/run_all.py
reproduction/src/*.py
reproduction/outputs/features/all_features.csv
reproduction/outputs/models/*.joblib
reproduction/outputs/figures/*.png
reproduction/outputs/reports/metrics_summary.csv
reproduction/outputs/reports/final_summary.md
reproduction/outputs/reports/reproduction_log.txt
```

### 可以删除

```text
reproduction/_tmp
__pycache__
.ipynb_checkpoints
临时调试图
临时 CSV
重复模型
下载 zip
多余示例文件
```

### 不要删除

```text
WindTurbineHighSpeedBearingPrognosis-Data
dataset_manifest.csv
download_check_log.txt
check_dataset.py
```

这些文件用于证明数据来源和完整性。

---

## 7. 成功标准

复现成功需要满足：

```text
1. 能一键运行 python run_all.py
2. 成功读取 50 个 data-*.mat 文件
3. 成功生成 all_features.csv
4. 成功生成至少 3 个 SVR 模型 joblib 文件
5. 成功生成 5 张结果图
6. metrics_summary.csv 中包含 MAE、RMSE、R2
7. final_summary.md 中说明复现结果和与论文差异
8. cleanup 后目录干净，只保留必要文件
```

---

## 8. 不要做的事情

```text
不要重新下载数据集
不要随机划分训练集和测试集
不要把测试集用于归一化或调参
不要把 SVR 改成 LSTM、CNN、Transformer 等深度学习模型
不要为了使用 GPU 而偏离论文方法
不要删除原始数据集
不要删除数据检查日志
不要只画图不保存模型
不要只保存模型不保存预测结果
```

---

## 9. 运行完成后需要汇报给用户的内容

运行完成后，请输出：

```text
1. 复现是否成功
2. all_features.csv 路径
3. 模型文件路径
4. 结果图路径
5. metrics_summary.csv 的主要结果
6. final_summary.md 路径
7. 是否完成清理
8. 如果失败，给出失败步骤、报错原因和下一步建议
```


export function formatDate(value?: string | null): string {
  if (!value) {
    return "--";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function taskTypeLabel(taskType?: string | null): string {
  switch (taskType) {
    case "fault_diagnosis":
      return "故障诊断";
    case "rul_prediction":
      return "故障预测";
    case "anomaly_detection":
      return "健康状态检测";
    default:
      return taskType || "--";
  }
}

export function modelNameZh(modelId: string, fallback?: string | null): string {
  switch (modelId) {
    case "nrel_binary_mscnn_bilstm_sensor1":
      return "齿轮箱故障诊断模型";
    case "hssb_svr_multifeature_60_40":
      return "轴承故障预测模型";
    case "scada_ae_decoder_transfer_13_to_10":
      return "SCADA 健康状态检测模型";
    default:
      return fallback || modelId;
  }
}

export function shortModelDisplayName(value?: string | null): string {
  switch (value) {
    case "SCADA Autoencoder Transfer Anomaly Detection Model":
      return "Health Detection Model";
    case "NREL Binary MSCNN-BiLSTM Fault Diagnosis Model":
      return "Fault Diagnosis Model";
    case "HSSB SVR Multi-feature RUL Prediction Model":
      return "Fault Prediction Model";
    default:
      return value || "--";
  }
}

export function modelStatusLabel(status?: string | null): string {
  switch (status) {
    case "active":
      return "启用中";
    case "production":
      return "生产中";
    case "testing":
      return "测试中";
    case "staging":
      return "预发布";
    case "draft":
      return "草稿";
    case "deprecated":
      return "已弃用";
    case "archived":
      return "已归档";
    case "inactive":
      return "未启用";
    default:
      return status || "--";
  }
}

export function validationStatusLabel(status?: string | null): string {
  switch (status) {
    case "passed":
      return "已通过";
    case "pending":
      return "待验证";
    case "failed":
      return "未通过";
    case "skipped":
      return "已跳过";
    default:
      return status || "--";
  }
}

export function modelSummaryZh(model: {
  model_id: string;
  task_type: string;
  dataset?: string | null;
}): string {
  switch (model.model_id) {
    case "nrel_binary_mscnn_bilstm_sensor1":
      return "基于振动信号的二分类故障诊断模型，用于快速判断设备状态更接近健康还是受损。";
    case "hssb_svr_multifeature_60_40":
      return "基于多特征与支持向量回归的剩余寿命预测模型，输出轴承 RUL 估计值。";
    case "scada_ae_decoder_transfer_13_to_10":
      return "基于 SCADA 自编码器迁移学习的健康状态检测模型，通过重构误差识别异常样本并给出风险等级。";
    default:
      if (model.task_type === "fault_diagnosis") {
        return "用于风电设备故障诊断的已注册模型。";
      }
      if (model.task_type === "rul_prediction") {
        return "用于风电设备故障预测与寿命趋势评估的已注册模型。";
      }
      if (model.task_type === "anomaly_detection") {
        return "用于风电设备健康状态检测的已注册模型。";
      }
      return model.dataset || model.model_id;
  }
}

export function catalogDescriptionZh(options: {
  familyCode?: string | null;
  taskType?: string | null;
  fallback?: string | null;
}): string {
  switch (options.familyCode) {
    case "scada_ae_decoder_transfer_13_to_10":
      return "面向风机 SCADA 数据的迁移学习健康状态检测模型，用重构误差识别目标机组的异常运行片段。";
    case "nrel_binary_mscnn_bilstm_sensor1":
      return "基于振动信号的二分类故障诊断模型，适合作为现场初筛与复核入口。";
    case "hssb_svr_multifeature_60_40":
      return "基于多特征与支持向量回归的故障预测模型，适合做寿命趋势研判和维护计划参考。";
    default:
      if (options.taskType === "fault_diagnosis") {
        return "用于风电设备故障诊断的已注册模型，可辅助判断设备当前是否存在异常故障征兆。";
      }
      if (options.taskType === "rul_prediction") {
        return "用于风电设备故障预测的已注册模型，可辅助评估部件寿命趋势与检修窗口。";
      }
      if (options.taskType === "anomaly_detection") {
        return "用于风电设备健康状态检测的已注册模型，可辅助识别运行数据中的偏离模式与风险样本。";
      }
      return options.fallback || "--";
  }
}

export function catalogLimitationsZh(options: {
  familyCode?: string | null;
  fallback?: string[] | null;
}): string {
  switch (options.familyCode) {
    case "scada_ae_decoder_transfer_13_to_10":
      return "该版本依赖本地受信任的迁移学习检查点与 scaler 元数据。异常分数来自自编码器重构误差，更适合识别运行偏离，不应直接当作故障类别判定结果。";
    case "nrel_binary_mscnn_bilstm_sensor1":
      return "该版本输出的是健康/故障二分类结果，更适合作为快速筛查，不覆盖具体故障类型定位；使用前应确认输入振动通道与训练时的采样方式保持一致。";
    case "hssb_svr_multifeature_60_40":
      return "该版本给出的是基于当前特征分布的寿命估计值，对工况漂移和数据缺失较敏感；建议结合趋势变化和业务阈值共同解释，不宜单独作为停机依据。";
    default:
      if (options.fallback && options.fallback.length > 0) {
        return options.fallback.join(" ");
      }
      return "当前版本暂未提供更细的适用边界说明，建议结合数据来源、特征口径和业务场景谨慎解读结果。";
  }
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "--";
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toFixed(value % 1 === 0 ? 0 : 4) : "--";
  }

  if (typeof value === "string") {
    return value;
  }

  return JSON.stringify(value, null, 2);
}

export function riskLabel(risk?: string | null): string {
  if (!risk) {
    return "未知";
  }

  switch (risk) {
    case "critical":
      return "高风险";
    case "warning":
      return "需关注";
    case "normal":
      return "正常";
    default:
      return risk;
  }
}

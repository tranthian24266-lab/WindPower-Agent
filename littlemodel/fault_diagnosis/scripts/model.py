from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def coarse_grain_same_length(x: torch.Tensor, scale: int) -> torch.Tensor:
    if scale == 1:
        return x
    padding = scale // 2
    pooled = F.avg_pool1d(x, kernel_size=scale, stride=1, padding=padding, count_include_pad=False)
    if pooled.size(-1) > x.size(-1):
        pooled = pooled[..., : x.size(-1)]
    elif pooled.size(-1) < x.size(-1):
        pooled = F.pad(pooled, (0, x.size(-1) - pooled.size(-1)))
    return pooled


class CNNBranch(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=128, stride=5),
            nn.BatchNorm1d(16),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=64, stride=3),
            nn.Conv1d(16, 32, kernel_size=2, stride=2),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=3, stride=2),
            nn.Conv1d(32, 8, kernel_size=2, stride=1),
            nn.BatchNorm1d(8),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=3, stride=2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.features(x)


class MSCNNBiLSTM(nn.Module):
    def __init__(
        self,
        input_channels: int = 1,
        scales: list[int] | None = None,
        lstm_hidden: int = 64,
        lstm_layers: int = 1,
        dropout: float = 0.5,
        num_classes: int = 2,
    ) -> None:
        super().__init__()
        if input_channels != 1:
            raise ValueError("This model expects single-channel input.")
        self.scales = scales or [1, 2, 3]
        self.branches = nn.ModuleList([CNNBranch() for _ in self.scales])
        self.lstm = nn.LSTM(
            input_size=8 * len(self.scales),
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(lstm_hidden * 2, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        branch_outputs = []
        for scale, branch in zip(self.scales, self.branches):
            branch_outputs.append(branch(coarse_grain_same_length(x, scale)))
        features = torch.cat(branch_outputs, dim=1)
        sequence = features.transpose(1, 2)
        lstm_output, _ = self.lstm(sequence)
        last_output = lstm_output[:, -1, :]
        return self.classifier(self.dropout(last_output))

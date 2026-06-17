from __future__ import annotations

import torch.nn as nn


class WindAutoencoder(nn.Module):
    def __init__(self, input_dim: int, activation: str = "prelu") -> None:
        super().__init__()
        if input_dim >= 100:
            hidden_dims = [200, 100, 50, 100, 200]
            self.architecture = "large"
        else:
            hidden_dims = [25, 10, 25]
            self.architecture = "small"

        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.activation_name = activation

        encoder_layers = []
        prev_dim = input_dim
        mid_idx = len(hidden_dims) // 2
        for index in range(mid_idx + 1):
            encoder_layers.append(nn.Linear(prev_dim, hidden_dims[index]))
            encoder_layers.append(nn.PReLU() if activation == "prelu" else nn.ReLU())
            prev_dim = hidden_dims[index]
        self.encoder = nn.Sequential(*encoder_layers)

        decoder_layers = []
        prev_dim = hidden_dims[mid_idx]
        for index in range(mid_idx + 1, len(hidden_dims)):
            decoder_layers.append(nn.Linear(prev_dim, hidden_dims[index]))
            decoder_layers.append(nn.PReLU() if activation == "prelu" else nn.ReLU())
            prev_dim = hidden_dims[index]
        decoder_layers.append(nn.Linear(prev_dim, input_dim))
        self.decoder = nn.Sequential(*decoder_layers)

        self.latent_dim = hidden_dims[mid_idx]

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded

    def get_architecture_info(self) -> dict[str, object]:
        return {
            "input_dim": self.input_dim,
            "hidden_dims": self.hidden_dims,
            "latent_dim": self.latent_dim,
            "activation": self.activation_name,
            "architecture": self.architecture,
        }


def create_model(input_dim: int, activation: str = "prelu") -> WindAutoencoder:
    return WindAutoencoder(input_dim=input_dim, activation=activation)


def get_batch_size(input_dim: int) -> int:
    return 128 if input_dim >= 100 else 64

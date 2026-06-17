import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm
import umap
import plotly.graph_objects as go
import plotly.colors as pc


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Używane urządzenie: {device}")

DATA_PATH = '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/chr6_hla_ld.vcor'
SAVE_DIR = '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae'
os.makedirs(SAVE_DIR, exist_ok=True)

SIZES = [25, 50, 75, 100, 125, 150]
EPOCHS = 20
BATCH_SIZE = 500
BATCHES_PER_EPOCH = 30
LATENT_DIM = 50
#REGION_START = 28000000
#REGION_END   = 30100000


print("Wczytywanie danych...")
df = pd.read_table(DATA_PATH)

all_unique_snps = pd.concat([df['ID_A'], df['ID_B']]).unique()
N = len(all_unique_snps)
snp_to_idx = {id_: idx for idx, id_ in enumerate(all_unique_snps)}

M_matrix = np.zeros((N, N), dtype=np.float32)
idx_a = df['ID_A'].map(snp_to_idx).values
idx_b = df['ID_B'].map(snp_to_idx).values
r2_values = df['PHASED_R2'].values

M_matrix[idx_a, idx_b] = r2_values
M_matrix[idx_b, idx_a] = r2_values
np.fill_diagonal(M_matrix, 1.0)

max_margin = max(SIZES) // 2 + 1
valid_mask = (idx_a >= max_margin) & (idx_a < N - max_margin) & \
             (idx_b >= max_margin) & (idx_b < N - max_margin)
valid_pairs = np.vstack((idx_a[valid_mask], idx_b[valid_mask])).T


class BlockFocusDataset(Dataset):
    def __init__(self, matrix, valid_pairs, sizes, batches_per_epoch, batch_size):
        self.matrix = torch.tensor(matrix, dtype=torch.float32)
        self.valid_pairs = valid_pairs
        self.sizes = sizes
        self.total_samples = batches_per_epoch * batch_size

    def __len__(self): return self.total_samples

    def __getitem__(self, idx):
        pair_idx = np.random.randint(0, len(self.valid_pairs))
        i, j = self.valid_pairs[pair_idx]
        if i > j: i, j = j, i

        crops = {}
        for size in self.sizes:
            half = size // 2
            extra = size % 2
            patch = self.matrix[i-half : i+half+extra, j-half : j+half+extra]
            crops[size] = patch.unsqueeze(0)
        return crops, (i, j)

dataloader = DataLoader(BlockFocusDataset(M_matrix, valid_pairs, SIZES, BATCHES_PER_EPOCH, BATCH_SIZE), batch_size=BATCH_SIZE, shuffle=True)

class SpatialAttention(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size=7, padding=3)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        avg_out = torch.mean(x, dim=1, keepdim=True)
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        y = torch.cat([avg_out, max_out], dim=1)
        mask = self.sigmoid(self.conv(y))
        return x * mask

class AttentionEncoder(nn.Module):
    def __init__(self, emb_dim=50):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16), nn.ReLU(),
            SpatialAttention(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64), nn.ReLU(),
            nn.AdaptiveMaxPool2d((2, 2)),
            nn.Flatten(),
            nn.Linear(64 * 4, 128), nn.ReLU(),
            nn.Linear(128, emb_dim)
        )
    def forward(self, x):
        z = self.features(x)
        z = F.normalize(z, p=2, dim=1)
        return z

class SpecificDecoder(nn.Module):
    def __init__(self, window_size, emb_dim=50):
        super().__init__()
        self.window_size = window_size
        self.decode = nn.Sequential(
            nn.Linear(emb_dim, 64 * 4), nn.ReLU(),
            nn.Unflatten(1, (64, 2, 2)),
            nn.Upsample(scale_factor=2, mode='nearest'),
            nn.Conv2d(64, 32, kernel_size=3, padding=1), nn.ReLU(),
            nn.Upsample(scale_factor=2, mode='nearest'),
            nn.Conv2d(32, 16, kernel_size=3, padding=1), nn.ReLU(),
            nn.Upsample(size=(window_size, window_size), mode='bilinear', align_corners=False),
            nn.Conv2d(16, 1, kernel_size=3, padding=1), nn.Sigmoid()
        )
    def forward(self, z):
        return self.decode(z)

encoder = AttentionEncoder(emb_dim=LATENT_DIM).to(device)
decoders = nn.ModuleDict({str(s): SpecificDecoder(s, emb_dim=LATENT_DIM).to(device) for s in SIZES})

all_params = list(encoder.parameters())
for dec in decoders.values():
    all_params += list(dec.parameters())
optimizer = optim.Adam(all_params, lr=0.001)

def weighted_block_loss(reconstructed, target, alpha=20.0):
    weight = 1.0 + alpha * target
    mse = (reconstructed - target) ** 2
    return torch.mean(mse * weight)


print("\nRozpoczynam trening (Zabezpieczony przed rozmiarem okna)...")
for epoch in range(EPOCHS):
    encoder.train()
    for dec in decoders.values(): dec.train()
    epoch_loss = 0.0
    loop = tqdm(dataloader, desc=f"Epoka {epoch+1}/{EPOCHS}", leave=False)

    for crops, _ in loop:
        optimizer.zero_grad()
        total_batch_loss = 0.0
        for size in SIZES:
            x = crops[size].to(device)
            z = encoder(x)
            x_hat = decoders[str(size)](z)
            total_batch_loss += weighted_block_loss(x_hat, x, alpha=20.0)

        total_batch_loss.backward()
        optimizer.step()
        epoch_loss += total_batch_loss.item()
        loop.set_postfix(loss=f"{total_batch_loss.item() / len(SIZES):.4f}")

    print(f"--- Epoka {epoch+1}/{EPOCHS} | Avg Weighted Loss: {epoch_loss / len(dataloader):.4f} ---")

encoder_save_path = os.path.join(SAVE_DIR, 'attention_encoder_fixed_50D.pth')
torch.save(encoder.state_dict(), encoder_save_path)


def get_latent_vector_attn(model, matrix, i, j, size):
    model.eval()
    half = size // 2
    extra = size % 2
    patch = torch.tensor(matrix[i-half:i+half+extra, j-half:j+half+extra], dtype=torch.float32)
    patch = patch.unsqueeze(0).unsqueeze(0).to(device)
    with torch.no_grad():
        z = model(patch)
    return z[0].cpu().numpy()

print("\nRedukcja UMAP i generowanie HTML...")
NUM_POINTS = 150
test_pts = [tuple(valid_pairs[np.random.randint(0, len(valid_pairs))]) for _ in range(NUM_POINTS)]

all_vectors_50d = []
for pt_idx, (i, j) in enumerate(test_pts):
    for size in SIZES:
        all_vectors_50d.append(get_latent_vector_attn(encoder, M_matrix, i, j, size))

reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=30, min_dist=0.3)
vectors_2d = reducer.fit_transform(np.array(all_vectors_50d))
vectors_2d_reshaped = vectors_2d.reshape(NUM_POINTS, len(SIZES), 2)

fig = go.Figure()
plotly_markers = ['circle', 'square', 'triangle-up', 'diamond', 'pentagon', 'star']
palette = pc.qualitative.Alphabet + pc.qualitative.Dark24 + pc.qualitative.Light24
def get_color(idx): return palette[idx % len(palette)]

for pt_idx, (i, j) in enumerate(test_pts):
    coords_x = vectors_2d_reshaped[pt_idx, :, 0]
    coords_y = vectors_2d_reshaped[pt_idx, :, 1]
    traj_color = get_color(pt_idx)

    fig.add_trace(go.Scatter(
        x=coords_x, y=coords_y, mode='lines',
        line=dict(width=1.5, color=traj_color),
        opacity=0.6, showlegend=False, hoverinfo='skip'
    ))

    for idx, size in enumerate(SIZES):
        m_size = 14 if idx == len(SIZES)-1 else 9
        fig.add_trace(go.Scatter(
            x=[coords_x[idx]], y=[coords_y[idx]], mode='markers',
            marker=dict(symbol=plotly_markers[idx], size=m_size, color=traj_color, line=dict(width=1, color='DarkSlateGrey')),
            name=f'Okno {size}x{size}', legendgroup=f'size_{size}', showlegend=(pt_idx == 0),
            hovertemplate=(f"<b>Para SNP: ({i}, {j})</b><br>Rozmiar okna: {size}x{size}<br>Wymiar 1: %{{x:.3f}}<br>Wymiar 2: %{{y:.3f}}<br><extra></extra>")
        ))

fig.update_layout(
    title='umap', title_font=dict(size=22),
    xaxis_title='UMAP 1', yaxis_title='UMAP 2', template='plotly_white',
    width=1400, height=900, hovermode='closest',
    legend=dict(title="Rozmiary okien", bgcolor="rgba(255, 255, 255, 0.8)", bordercolor="black", borderwidth=1)
)

html_save_path = os.path.join(SAVE_DIR, 'umap.html')
fig.write_html(html_save_path)
print(f"\n[GOTOWE] Zapisano plik: {html_save_path}")

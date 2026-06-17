import os
import random
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import umap
import plotly.graph_objects as go
import plotly.colors as pc
from scipy.interpolate import LSQUnivariateSpline
from scipy.spatial import KDTree
from sklearn.cluster import KMeans

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    print(f"Zablokowano ziarno losowości (Seed = {seed}).")

set_seed(42)


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Używane urządzenie: {device}")

DATA_PATH = '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/chr6_hla_ld.vcor'
MODEL_PATH = '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae/attention_encoder_fixed_50D.pth'

OUTPUT_DIR = '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae/mgr_wizualizacje/wiz_1'
os.makedirs(OUTPUT_DIR, exist_ok=True)

SIZES = [25, 50, 75, 100, 125, 150]
LATENT_DIM = 50
REGION_START = 28000000
REGION_END   = 30100000
NUM_POINTS = 1500

size_to_symbol = {25: 'circle', 50: 'square', 75: 'triangle-up', 100: 'diamond', 125: 'pentagon', 150: 'star'}


print("Wczytywanie i wycinanie regionu HLA...")
df = pd.read_table(DATA_PATH)
df_hla = df[(df['POS_A'] >= REGION_START) & (df['POS_A'] <= REGION_END) &
            (df['POS_B'] >= REGION_START) & (df['POS_B'] <= REGION_END)].copy()

all_unique_snps = pd.concat([df_hla['ID_A'], df_hla['ID_B']]).unique()
N = len(all_unique_snps)
snp_to_idx = {id_: idx for idx, id_ in enumerate(all_unique_snps)}

M_matrix = np.zeros((N, N), dtype=np.float32)
idx_a = df_hla['ID_A'].map(snp_to_idx).values
idx_b = df_hla['ID_B'].map(snp_to_idx).values
r2_values = df_hla['PHASED_R2'].values

M_matrix[idx_a, idx_b] = r2_values
M_matrix[idx_b, idx_a] = r2_values
np.fill_diagonal(M_matrix, 1.0)
M_matrix = np.sqrt(M_matrix)

max_window = max(SIZES)
max_margin = max_window // 2 + 1
valid_mask = (idx_a >= max_margin) & (idx_a < N - max_margin) & \
             (idx_b >= max_margin) & (idx_b < N - max_margin)
valid_pairs = np.vstack((idx_a[valid_mask], idx_b[valid_mask])).T

def get_non_overlapping_points(pairs, num_points, min_dist):
    np.random.shuffle(pairs)
    selected = []
    for pt in pairs:
        i, j = pt
        overlap = False
        for (sel_i, sel_j) in selected:
            if (abs(i - sel_i) < min_dist and abs(j - sel_j) < min_dist) or \
               (abs(i - sel_j) < min_dist and abs(j - sel_i) < min_dist):
                overlap = True; break
        if not overlap:
            selected.append((i, j))
            if len(selected) == num_points: break
    return selected

test_pts = get_non_overlapping_points(valid_pairs, NUM_POINTS, min_dist=max_window)


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
            nn.Conv2d(1, 16, kernel_size=3, padding=1), nn.BatchNorm2d(16), nn.ReLU(), SpatialAttention(),
            nn.MaxPool2d(2), nn.Conv2d(16, 32, kernel_size=3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.AdaptiveMaxPool2d((2, 2)), nn.Flatten(), nn.Linear(64 * 4, 128), nn.ReLU(), nn.Linear(128, emb_dim)
        )
    def forward(self, x):
        z = self.features(x)
        return F.normalize(z, p=2, dim=1)

encoder = AttentionEncoder(emb_dim=LATENT_DIM).to(device)
encoder.load_state_dict(torch.load(MODEL_PATH, map_location=device))
encoder.eval()

def get_latent_vector_attn(model, matrix, i, j, size):
    half, extra = size // 2, size % 2
    patch = torch.tensor(matrix[i-half:i+half+extra, j-half:j+half+extra], dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(device)
    with torch.no_grad(): z = model(patch)
    return z[0].cpu().numpy()

print("Ekstrakcja wektorów 50D...")
all_vectors_50d, sizes_flat, pt_idx_flat = [], [], []
for pt_idx, (i, j) in enumerate(test_pts):
    for size in SIZES:
        all_vectors_50d.append(get_latent_vector_attn(encoder, M_matrix, i, j, size))
        sizes_flat.append(size)
        pt_idx_flat.append(pt_idx)

sizes_flat = np.array(sizes_flat)
pt_idx_flat = np.array(pt_idx_flat)

print("Redukcja UMAP...")
reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=25, min_dist=0.2)
vectors_2d = reducer.fit_transform(np.array(all_vectors_50d))
flat_x, flat_y = vectors_2d[:, 0], vectors_2d[:, 1]

print("Obliczanie Z_norm...")
all_znorms = np.zeros(len(flat_x))
for flat_idx in range(len(flat_x)):
    size = sizes_flat[flat_idx]
    pt_idx = pt_idx_flat[flat_idx]
    i, j = test_pts[pt_idx]
    half, extra = size // 2, size % 2
    patch = M_matrix[i-half:i+half+extra, j-half:j+half+extra]
    sum_sq = np.sum(patch**2)
    all_znorms[flat_idx] = float(np.mean(patch / np.sqrt(sum_sq))) if sum_sq > 0 else 0.0


print("Budowanie Głównego Trendu (Splajnu)...")
sort_idx = np.argsort(flat_x)
x_sorted, y_sorted = flat_x[sort_idx], flat_y[sort_idx]
internal_knots = np.unique(np.percentile(x_sorted, np.arange(10, 100, 10)))
internal_knots = internal_knots[(internal_knots > x_sorted.min()) & (internal_knots < x_sorted.max())]
spline_model = LSQUnivariateSpline(x_sorted, y_sorted, t=internal_knots)
all_knots_x = spline_model.get_knots()
all_knots_y = spline_model(all_knots_x)

x_curve_dense = np.linspace(x_sorted.min(), x_sorted.max(), 5000)
y_curve_dense = spline_model(x_curve_dense)
curve_points = np.column_stack((x_curve_dense, y_curve_dense))
tree = KDTree(curve_points)

dist_matrix = np.abs(flat_x[:, None] - all_knots_x[None, :])
cluster_labels = np.argmin(dist_matrix, axis=1)
orig_indices = np.arange(len(flat_x))

def process_knot(knot_idx):
    mask = (cluster_labels == knot_idx)
    x_k, y_k, z_k = flat_x[mask], flat_y[mask], all_znorms[mask]
    idx_k = orig_indices[mask]
    sizes_k = sizes_flat[mask]
    dist_k, _ = tree.query(np.column_stack((x_k, y_k)))

    results = {}
    for k in [3, 4]:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
        labels = kmeans.fit_predict(np.column_stack((x_k, y_k)))
        centroids = kmeans.cluster_centers_

        mean_dist = [np.mean(dist_k[labels == c]) if np.sum(labels==c)>0 else 0 for c in range(k)]
        closest_c = np.argmin(mean_dist)

        reps = {c: [] for c in range(k)}
        for c in range(k):
            mask_c = (labels == c)
            pts_c = np.column_stack((x_k[mask_c], y_k[mask_c]))
            idx_c = idx_k[mask_c]
            sizes_c = sizes_k[mask_c]

            for s in SIZES:
                mask_s = (sizes_c == s)
                pts_s = pts_c[mask_s]
                idx_s = idx_c[mask_s]

                extracted = 0
                if len(pts_s) > 0:
                    dists = np.linalg.norm(pts_s - centroids[c], axis=1)
                    num_reps = min(2, len(dists))
                    top_idx = np.argsort(dists)[:num_reps]
                    for rep_i in top_idx:
                        global_idx = idx_s[rep_i]
                        pt_idx = pt_idx_flat[global_idx]
                        i, j = test_pts[pt_idx]
                        half, extra = s // 2, s % 2
                        patch = M_matrix[i-half:i+half+extra, j-half:j+half+extra]
                        reps[c].append({'patch': patch, 'size': s, 'valid': True})
                        extracted += 1

                while extracted < 2:
                    reps[c].append({'patch': np.full((s, s), np.nan), 'size': s, 'valid': False})
                    extracted += 1

        results[k] = {
            'labels': labels, 'x': x_k, 'y': y_k, 'sizes': sizes_k,
            'means': [np.mean(z_k[labels == c]) if np.sum(labels==c)>0 else 0.0 for c in range(k)],
            'stds': [np.std(z_k[labels == c]) if np.sum(labels==c)>0 else 0.0 for c in range(k)],
            'closest_c': closest_c, 'reps': reps
        }
    return results

print("Przetwarzanie Pierwszego Węzła...")
res_first = process_knot(0)
print("Przetwarzanie Ostatniego Węzła...")
res_last = process_knot(len(all_knots_x) - 1)


print(f"\nGenerowanie i zapisywanie osobnych wykresów w: {OUTPUT_DIR}")

full_palette = pc.qualitative.Prism + pc.qualitative.Vivid

fig_global = go.Figure()
fig_global.add_trace(go.Scatter(x=flat_x, y=flat_y, mode='markers', marker=dict(color='lightgrey', size=4), name='Wszystkie macierze'))
fig_global.add_trace(go.Scatter(x=x_curve_dense, y=y_curve_dense, mode='lines', line=dict(color='firebrick', width=4), name='Główny trend (Splajn)'))
fig_global.add_trace(go.Scatter(x=all_knots_x, y=all_knots_y, mode='markers', marker=dict(color='black', symbol='x', size=12, line=dict(width=2)), name='Węzły trendu'))

fig_global.update_layout(
    title='Globalna przestrzeń UMAP - Macierze LD',
    template='plotly_white',
    xaxis_title="Wymiar UMAP 1",
    yaxis_title="Wymiar UMAP 2",
    width=1000, height=800,
    font=dict(size=16)
)
fig_global.write_image(os.path.join(OUTPUT_DIR, "01_Globalny_UMAP.png"), scale=3)


knot_data = [("Wezel_Pierwszy", res_first), ("Wezel_Ostatni", res_last)]

for knot_name, res_knot in knot_data:
    for k in [3, 4]:
        labels = res_knot[k]['labels']
        x_k, y_k, sizes_k = res_knot[k]['x'], res_knot[k]['y'], res_knot[k]['sizes']
        closest_c = res_knot[k]['closest_c']

        fig_zoom = go.Figure()
        fig_zoom.add_trace(go.Scatter(x=x_curve_dense, y=y_curve_dense, mode='lines', line=dict(color='black', width=3, dash='dot'), name='Trend'))

        for c in range(k):
            for s, sym in size_to_symbol.items():
                mask = (labels == c) & (sizes_k == s)
                if np.any(mask):
                    lw = 2 if c == closest_c else 0.5
                    op = 1.0 if c == closest_c else 0.7
                    fig_zoom.add_trace(go.Scatter(
                        x=x_k[mask], y=y_k[mask], mode='markers',
                        marker=dict(symbol=sym, color=full_palette[c], size=10, opacity=op, line=dict(width=lw, color='black')),
                        name=f'K{c+1} (Rozmiar: {s}x{s})'
                    ))

        margin_x, margin_y = (x_k.max() - x_k.min()) * 0.1, (y_k.max() - y_k.min()) * 0.1
        fig_zoom.update_layout(
            title=f'Zbliżenie na {knot_name.replace("_", " ")} (Podział na K={k})',
            template='plotly_white',
            xaxis=dict(title="Wymiar UMAP 1", range=[x_k.min()-margin_x, x_k.max()+margin_x]),
            yaxis=dict(title="Wymiar UMAP 2", range=[y_k.min()-margin_y, y_k.max()+margin_y]),
            width=800, height=600,
            font=dict(size=14),
            legend=dict(title="Klastry i Okna", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        fig_zoom.write_image(os.path.join(OUTPUT_DIR, f"02_{knot_name}_K{k}_UMAP_Zoom.png"), scale=3)

        fig_bar = go.Figure()
        bar_texts = [f"Klaster {c+1}" + (" (Najbliżej trendu)" if c == closest_c else "") for c in range(k)]
        fig_bar.add_trace(go.Bar(
            x=bar_texts, y=res_knot[k]['means'],
            error_y=dict(type='data', array=res_knot[k]['stds'], visible=True, color='black', thickness=2),
            marker=dict(color=full_palette[:k], line=dict(color='black', width=1.5))
        ))
        fig_bar.update_layout(
            title=f'Gęstość strukturalna LD (Z_norm) - {knot_name.replace("_", " ")} (K={k})',
            template='plotly_white',
            xaxis_title="Klastry",
            yaxis_title="Średnia Z_norm ± Odchylenie Standardowe",
            width=700, height=600,
            font=dict(size=14)
        )
        fig_bar.write_image(os.path.join(OUTPUT_DIR, f"03_{knot_name}_K{k}_Znorm_Bar.png"), scale=3)

        for c in range(k):
            reps_c = res_knot[k]['reps'][c]
            size_counter = {} 

            for item in reps_c:
                if item['valid']:
                    s = item['size']
                    size_counter[s] = size_counter.get(s, 0) + 1
                    rep_num = size_counter[s]

                    fig_heat = go.Figure(data=go.Heatmap(
                        z=item['patch'], colorscale='RdBu_r', zmin=0, zmax=1, showscale=True
                    ))

                    fig_heat.update_layout(
                        title=dict(text=f'Klaster {c+1} (Rozmiar {s}x{s})', font=dict(size=20), x=0.5),
                        template='plotly_white',
                        width=500, height=500,
                        margin=dict(l=30, r=30, t=60, b=30)
                    )
                    fig_heat.update_xaxes(showticklabels=False, scaleanchor="y", scaleratio=1)
                    fig_heat.update_yaxes(showticklabels=False, autorange="reversed")

                    heat_filename = f"04_{knot_name}_K{k}_Klaster{c+1}_Rozmiar{s}_Rep{rep_num}.png"
                    fig_heat.write_image(os.path.join(OUTPUT_DIR, heat_filename), scale=3)

print(f"\n[GOTOWE] Zapisano wszystkie wykresy w folderze: \n{OUTPUT_DIR}")

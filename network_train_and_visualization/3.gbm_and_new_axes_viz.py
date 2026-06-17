import os
import random
import gc
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import umap
import plotly.graph_objects as go
from scipy.interpolate import LSQUnivariateSpline
from scipy.spatial import KDTree
from tqdm import tqdm
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, classification_report, accuracy_score
from sklearn.tree import plot_tree


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

TARGET_FILES = [
    '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae/ld_matrixes_for_test/chr1_reg_731643_5680231_matrix.vcor',
    '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae/ld_matrixes_for_test/chr6_hla_ld.vcor',
    '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae/ld_matrixes_for_test/chr9_reg_41114_3695931_matrix.vcor',
    '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae/ld_matrixes_for_test/chr15_reg_20148447_28057594_matrix.vcor',
    '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae/ld_matrixes_for_test/chr20_reg_61098_4764682_matrix.vcor'
]

MODEL_PATH = '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae/attention_encoder_fixed_50D.pth'
LATENT_DIR = '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae/latent_vectors'
MAIN_OUTPUT_DIR = '/home/dpietrzak/DominikPietrzak/ssd_disk/DominikPietrzak/modele_ae/mgr_wizualizacje/wiz_2'

os.makedirs(MAIN_OUTPUT_DIR, exist_ok=True)
os.makedirs(LATENT_DIR, exist_ok=True)

SIZES = [25, 50, 75, 100, 125, 150]
LATENT_DIM = 50
NUM_POINTS = 1500


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

print("\nInicjalizacja i wczytywanie modelu AE...")
encoder = AttentionEncoder(emb_dim=LATENT_DIM).to(device)
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Nie znaleziono pliku wag: {MODEL_PATH}")
encoder.load_state_dict(torch.load(MODEL_PATH, map_location=device))
encoder.eval()

def get_latent_vector_attn(model, matrix, i, j, size):
    half, extra = size // 2, size % 2
    patch = torch.tensor(matrix[i-half:i+half+extra, j-half:j+half+extra], dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(device)
    with torch.no_grad(): z = model(patch)
    return z[0].cpu().numpy()

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


for TARGET_FILE in TARGET_FILES:
    if not os.path.exists(TARGET_FILE):
        print(f"\n[!] POMINIĘTO: Nie znaleziono pliku {TARGET_FILE}")
        continue

    base_name = os.path.splitext(os.path.basename(TARGET_FILE))[0]
    print(f"\n" + "="*70)
    print(f"ROZPOCZĘTO ANALIZĘ: {base_name}")
    print("="*70)

    CURRENT_OUTPUT_DIR = os.path.join(MAIN_OUTPUT_DIR, base_name)
    os.makedirs(CURRENT_OUTPUT_DIR, exist_ok=True)

    latent_file_path = os.path.join(LATENT_DIR, f"{base_name}_latent_data.npz")

    print(" -> Wczytywanie danych .vcor do pamięci...")
    header_cols = pd.read_csv(TARGET_FILE, sep='\t', nrows=0).columns
    if len(header_cols) < 3:
        header_cols = pd.read_csv(TARGET_FILE, sep=r'\s+', nrows=0).columns

    cols_to_use = [c for c in header_cols if 'ID_A' in c or 'ID_B' in c or 'PHASED_R2' in c or 'POS_A' in c or 'POS_B' in c]

    df = pd.read_csv(
        TARGET_FILE,
        sep='\t' if '\t' in open(TARGET_FILE).readline() else r'\s+',
        engine='c', usecols=cols_to_use, dtype={'PHASED_R2': np.float32}
    )
    df.rename(columns={c: c.replace('#', '') for c in df.columns}, inplace=True)

    all_unique_snps = pd.concat([df['ID_A'], df['ID_B']]).unique()
    N = len(all_unique_snps)
    snp_to_idx = {id_: idx for idx, id_ in enumerate(all_unique_snps)}

    idx_to_pos = {}
    for snp_id, pos in zip(df['ID_A'].values, df['POS_A'].values):
        idx_to_pos[snp_to_idx[snp_id]] = pos
    for snp_id, pos in zip(df['ID_B'].values, df['POS_B'].values):
        idx_to_pos[snp_to_idx[snp_id]] = pos

    M_matrix = np.zeros((N, N), dtype=np.float32)
    idx_a = df['ID_A'].map(snp_to_idx).values
    idx_b = df['ID_B'].map(snp_to_idx).values
    r2_values = df['PHASED_R2'].values

    M_matrix[idx_a, idx_b] = r2_values
    M_matrix[idx_b, idx_a] = r2_values
    np.fill_diagonal(M_matrix, 1.0)

    max_window = max(SIZES)
    max_margin = max_window // 2 + 1
    valid_mask = (idx_a >= max_margin) & (idx_a < N - max_margin) & (idx_b >= max_margin) & (idx_b < N - max_margin)
    valid_pairs = np.vstack((idx_a[valid_mask], idx_b[valid_mask])).T

    if len(valid_pairs) < NUM_POINTS:
        print(f" [!] Za mało poprawnych par SNP. Zmniejszam próbę.")
        test_pts = get_non_overlapping_points(valid_pairs, len(valid_pairs), min_dist=max_window)
    else:
        test_pts = get_non_overlapping_points(valid_pairs, NUM_POINTS, min_dist=max_window)

    sizes_flat, pt_idx_flat, chrom_pos_flat = [], [], []
    for pt_idx, (i, j) in enumerate(test_pts):
        pos_i = idx_to_pos[i]
        for size in SIZES:
            sizes_flat.append(size)
            pt_idx_flat.append(pt_idx)
            chrom_pos_flat.append(pos_i)

    chrom_pos_flat = np.array(chrom_pos_flat)
    sizes_flat = np.array(sizes_flat)

    if os.path.exists(latent_file_path):
        print(f" -> Znaleziono bazę wektorów: {latent_file_path}. Wczytywanie z dysku...")
        data_cache = np.load(latent_file_path)
        all_vectors_50d = data_cache['vectors']
        all_znorms = data_cache['z_norms']
        chrom_pos_flat = data_cache['positions']
        sizes_flat = data_cache['sizes']
    else:
        print(" -> Ekstrakcja wektorów 50D i obliczanie Z_norm...")
        all_vectors_50d = []
        all_znorms = []

        for flat_idx in tqdm(range(len(pt_idx_flat)), desc="Przetwarzanie Łat (Patches)"):
            size = sizes_flat[flat_idx]
            pt_idx = pt_idx_flat[flat_idx]
            i, j = test_pts[pt_idx]

            all_vectors_50d.append(get_latent_vector_attn(encoder, M_matrix, i, j, size))

            half, extra = size // 2, size % 2
            patch = M_matrix[i-half:i+half+extra, j-half:j+half+extra]
            sum_sq = np.sum(patch**2)
            z_val = float(np.mean(patch / np.sqrt(sum_sq))) if sum_sq > 0 else 0.0
            all_znorms.append(z_val)

        all_vectors_50d = np.array(all_vectors_50d)
        all_znorms = np.array(all_znorms)

        np.savez(latent_file_path, vectors=all_vectors_50d, z_norms=all_znorms, positions=chrom_pos_flat, sizes=sizes_flat)

    print(" -> Redukcja UMAP (50D -> 3D)...")
    reducer = umap.UMAP(n_components=3, random_state=42, n_neighbors=25, min_dist=0.2)
    vectors_3d = reducer.fit_transform(all_vectors_50d)
    flat_x, flat_y, flat_z = vectors_3d[:, 0], vectors_3d[:, 1], vectors_3d[:, 2]

    print(" -> Budowanie Splajnu 3D i obliczanie dystansu...")
    sort_idx = np.argsort(flat_x)
    x_s, y_s, z_s = flat_x[sort_idx], flat_y[sort_idx], flat_z[sort_idx]

    try:
        internal_knots = np.unique(np.percentile(x_s, np.arange(10, 100, 10)))
        internal_knots = internal_knots[(internal_knots > x_s.min()) & (internal_knots < x_s.max())]

        spline_y = LSQUnivariateSpline(x_s, y_s, t=internal_knots)
        spline_z = LSQUnivariateSpline(x_s, z_s, t=internal_knots)

        x_curve_dense = np.linspace(x_s.min(), x_s.max(), 5000)
        y_curve_dense = spline_y(x_curve_dense)
        z_curve_dense = spline_z(x_curve_dense)

        curve_points_3d = np.column_stack((x_curve_dense, y_curve_dense, z_curve_dense))
        tree_3d = KDTree(curve_points_3d)

        data_points_3d = np.column_stack((flat_x, flat_y, flat_z))
        distances, _ = tree_3d.query(data_points_3d)
    except Exception as e:
        print(f" [!] Problem ze splajnem ({e}). Odległości ustalone na 0.")
        distances = np.zeros_like(flat_x)
        x_curve_dense, y_curve_dense, z_curve_dense = None, None, None

    q25, q50, q75, q90 = np.percentile(all_znorms, [25, 50, 75, 90])
    quantile_groups = [
        (all_znorms <= q25, "Q1 (0-25%)", "#2b83ba"),
        ((all_znorms > q25) & (all_znorms <= q50), "Q2 (25-50%)", "#abdda4"),
        ((all_znorms > q50) & (all_znorms <= q75), "Q3 (50-75%)", "#ffffbf"),
        ((all_znorms > q75) & (all_znorms <= q90), "Q4 (75-90%)", "#fdae61"),
        (all_znorms > q90, "Top 10% (>90%)", "#d7191c")
    ]

    print(f" -> Generowanie obrazów PNG (Plotly)...")

    def create_scatter_2d(x_data, y_data, color_data, x_title, y_title, title, is_quantile=False, curve_x=None, curve_y=None):
        fig = go.Figure()
        if is_quantile:
            for mask, label, color in color_data:
                fig.add_trace(go.Scatter(x=x_data[mask], y=y_data[mask], mode='markers',
                    marker=dict(color=color, size=6, opacity=0.8, line=dict(width=0.5, color='darkgray')), name=label))
        else:
            fig.add_trace(go.Scatter(x=x_data, y=y_data, mode='markers',
                marker=dict(color=color_data, colorscale='Turbo', size=6, opacity=0.8, colorbar=dict(title="Z_norm")), showlegend=False))

        if curve_x is not None and curve_y is not None:
            fig.add_trace(go.Scatter(x=curve_x, y=curve_y, mode='lines', line=dict(color='black', width=4), name='Splajn 2D'))

        fig.update_layout(title=title, template='plotly_white', xaxis_title=x_title, yaxis_title=y_title, width=1000, height=800)
        return fig

    def create_scatter_3d(x_data, y_data, z_data, color_data, title, is_quantile=False):
        fig = go.Figure()
        if is_quantile:
            for mask, label, color in color_data:
                fig.add_trace(go.Scatter3d(x=x_data[mask], y=y_data[mask], z=z_data[mask], mode='markers',
                    marker=dict(color=color, size=4, opacity=0.8), name=label))
        else:
            fig.add_trace(go.Scatter3d(x=x_data, y=y_data, z=z_data, mode='markers',
                marker=dict(color=color_data, colorscale='Turbo', size=4, opacity=0.8, colorbar=dict(title="Z_norm", x=0.85)), showlegend=False))

        if x_curve_dense is not None:
            fig.add_trace(go.Scatter3d(x=x_curve_dense, y=y_curve_dense, z=z_curve_dense, mode='lines',
                line=dict(color='black', width=5), name='Splajn 3D'))

        fig.update_layout(title=title, scene=dict(xaxis_title='UMAP 1', yaxis_title='UMAP 2', zaxis_title='UMAP 3'), width=1200, height=900)
        return fig

    fig_pos_grad = create_scatter_2d(chrom_pos_flat, distances, all_znorms, "Pozycja Chromosomowa (bp)", "Dystans Euklidesowy do Splajnu", "Dystans do Splajnu vs Pozycja Chromosomowa ")
    fig_pos_grad.write_image(os.path.join(CURRENT_OUTPUT_DIR, "01_Dystans_vs_Pozycja_Gradient.png"), scale=3)

    fig_pos_quant = create_scatter_2d(chrom_pos_flat, distances, quantile_groups, "Pozycja Chromosomowa (bp)", "Dystans Euklidesowy do Splajnu", "Dystans do Splajnu vs Pozycja Chromosomowa ", is_quantile=True)
    fig_pos_quant.write_image(os.path.join(CURRENT_OUTPUT_DIR, "02_Dystans_vs_Pozycja_Kwantyle.png"), scale=3)

    fig_umap1_grad = create_scatter_2d(flat_x, distances, all_znorms, "UMAP 1", "Dystans Euklidesowy do Splajnu", "Profil Odległości od Splajnu ")
    fig_umap1_grad.write_image(os.path.join(CURRENT_OUTPUT_DIR, "03_Dystans_vs_UMAP1_Gradient.png"), scale=3)

    fig_umap1_quant = create_scatter_2d(flat_x, distances, quantile_groups, "UMAP 1", "Dystans Euklidesowy do Splajnu", "Profil Odległości od Splajnu ", is_quantile=True)
    fig_umap1_quant.write_image(os.path.join(CURRENT_OUTPUT_DIR, "04_Dystans_vs_UMAP1_Kwantyle.png"), scale=3)

    fig_2d_grad = create_scatter_2d(flat_x, flat_y, all_znorms, "UMAP 1", "UMAP 2", "Przestrzeń Latentna 2D ", curve_x=x_curve_dense, curve_y=y_curve_dense)
    fig_2d_grad.write_image(os.path.join(CURRENT_OUTPUT_DIR, "05_UMAP_2D_Gradient.png"), scale=3)

    fig_2d_quant = create_scatter_2d(flat_x, flat_y, quantile_groups, "UMAP 1", "UMAP 2", "Przestrzeń Latentna 2D ", is_quantile=True, curve_x=x_curve_dense, curve_y=y_curve_dense)
    fig_2d_quant.write_image(os.path.join(CURRENT_OUTPUT_DIR, "06_UMAP_2D_Kwantyle.png"), scale=3)

    fig_3d_grad = create_scatter_3d(flat_x, flat_y, flat_z, all_znorms, "Przestrzeń Latentna 3D")
    fig_3d_grad.write_image(os.path.join(CURRENT_OUTPUT_DIR, "07_UMAP_3D_Gradient.png"), scale=3)

    fig_3d_quant = create_scatter_3d(flat_x, flat_y, flat_z, quantile_groups, "Przestrzeń Latentna 3D", is_quantile=True)
    fig_3d_quant.write_image(os.path.join(CURRENT_OUTPUT_DIR, "08_UMAP_3D_Kwantyle.png"), scale=3)


    print("\n -> Rozpoczęto część Machine Learning (RF oraz GB)...")
    bins = [q25, q50, q75, q90]
    y_labels = np.digitize(all_znorms, bins)

    X = np.column_stack((flat_x, flat_y, flat_z, distances))
    X_train, X_test, y_train, y_test = train_test_split(X, y_labels, test_size=0.2, random_state=42)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    X_scaled = scaler.transform(X)

    rf_clf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    rf_clf.fit(X_train_scaled, y_train)
    rf_y_pred_all = rf_clf.predict(X_scaled)
    rf_y_pred_test = rf_clf.predict(X_test_scaled)

    gb_clf = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
    gb_clf.fit(X_train_scaled, y_train)
    gb_y_pred_all = gb_clf.predict(X_scaled)
    gb_y_pred_test = gb_clf.predict(X_test_scaled)

    class_names_str = [f'Klasa {i}' for i in range(len(bins)+1)]
    print("\n" + "-"*50)
    print(f"RAPORT RANDOM FOREST: {base_name}")
    print(f"Globalne Accuracy: {accuracy_score(y_test, rf_y_pred_test):.4f}")
    print(classification_report(y_test, rf_y_pred_test, target_names=class_names_str, zero_division=0))

    print("\n" + "-"*50)
    print(f"RAPORT GRADIENT BOOSTING: {base_name}")
    print(f"Globalne Accuracy: {accuracy_score(y_test, gb_y_pred_test):.4f}")
    print(classification_report(y_test, gb_y_pred_test, target_names=class_names_str, zero_division=0))

    print(" -> Generowanie obrazów ML PNG dla obu modeli...")
    cmap_classes = plt.get_cmap('Set1', len(bins) + 1)
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor=cmap_classes(i), markersize=8, label=f'Klasa {i} (Kwantyl {i+1})')
        for i in range(len(bins)+1)
    ]
    feature_names = ['UMAP 1', 'UMAP 2', 'UMAP 3', 'Dystans 3D']

    def generate_ml_plots(model, y_pred_all, y_pred_test, prefix, title_prefix):
        fig_2d, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
        ax1.scatter(flat_x, flat_y, c=y_labels, cmap=cmap_classes, s=15, alpha=0.7, edgecolors='none')
        ax1.set_title("PRAWDZIWA Struktura Latentna (Rzut 2D)", fontsize=14, fontweight='bold')
        ax1.set_xlabel("UMAP 1"); ax1.set_ylabel("UMAP 2"); ax1.legend(handles=legend_elements, loc='best')

        ax2.scatter(flat_x, flat_y, c=y_pred_all, cmap=cmap_classes, s=15, alpha=0.7, edgecolors='none')
        ax2.set_title(f"{title_prefix}: PREDYKCJA (Rzut 2D)", fontsize=14, fontweight='bold')
        ax2.set_xlabel("UMAP 1"); ax2.set_ylabel("UMAP 2"); ax2.legend(handles=legend_elements, loc='best')
        plt.tight_layout()
        fig_2d.savefig(os.path.join(CURRENT_OUTPUT_DIR, f"{prefix}_UMAP_2D_Porownanie.png"), dpi=300)

        fig_3d = plt.figure(figsize=(18, 8))
        ax3 = fig_3d.add_subplot(1, 2, 1, projection='3d')
        ax3.scatter(flat_x, flat_y, flat_z, c=y_labels, cmap=cmap_classes, s=10, alpha=0.7)
        ax3.set_title("PRAWDZIWA Struktura Latentna 3D", fontsize=14, fontweight='bold')
        ax3.set_xlabel("UMAP 1"); ax3.set_ylabel("UMAP 2"); ax3.set_zlabel("UMAP 3")

        ax4 = fig_3d.add_subplot(1, 2, 2, projection='3d')
        ax4.scatter(flat_x, flat_y, flat_z, c=y_pred_all, cmap=cmap_classes, s=10, alpha=0.7)
        ax4.set_title(f"{title_prefix}: PREDYKCJA 3D", fontsize=14, fontweight='bold')
        ax4.set_xlabel("UMAP 1"); ax4.set_ylabel("UMAP 2"); ax4.set_zlabel("UMAP 3")
        plt.tight_layout()
        fig_3d.savefig(os.path.join(CURRENT_OUTPUT_DIR, f"{prefix}_UMAP_3D_Porownanie.png"), dpi=300)

        fig_dist, (ax5, ax6) = plt.subplots(1, 2, figsize=(16, 7))
        ax5.scatter(flat_x, distances, c=y_labels, cmap=cmap_classes, s=15, alpha=0.7, edgecolors='none')
        ax5.axhline(0, color='red', linestyle='--', linewidth=1.5)
        ax5.set_title("PRAWDZIWY Profil Odległości 3D", fontsize=14, fontweight='bold')
        ax5.set_xlabel("UMAP 1"); ax5.set_ylabel("Dystans Euklidesowy do Splajnu")
        ax5.legend(handles=legend_elements, loc='upper right')

        ax6.scatter(flat_x, distances, c=y_pred_all, cmap=cmap_classes, s=15, alpha=0.7, edgecolors='none')
        ax6.axhline(0, color='red', linestyle='--', linewidth=1.5)
        ax6.set_title(f"{title_prefix}: PREDYKCJA - Profil Odległości 3D", fontsize=14, fontweight='bold')
        ax6.set_xlabel("UMAP 1"); ax6.set_ylabel("Dystans Euklidesowy do Splajnu")
        ax6.legend(handles=legend_elements, loc='upper right')
        plt.tight_layout()
        fig_dist.savefig(os.path.join(CURRENT_OUTPUT_DIR, f"{prefix}_Dystans_Porownanie.png"), dpi=300)

        fig_cm, ax_cm = plt.subplots(figsize=(8, 6))
        cm = confusion_matrix(y_test, y_pred_test)
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names_str)
        disp.plot(ax=ax_cm, cmap='Blues', colorbar=True)
        ax_cm.set_title(f"Macierz Błędu ({title_prefix})", fontsize=14, fontweight='bold')
        plt.tight_layout()
        fig_cm.savefig(os.path.join(CURRENT_OUTPUT_DIR, f"{prefix}_Macierz_Bledu.png"), dpi=300)

        fig_fi, ax_fi = plt.subplots(figsize=(10, 6))
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]
        sorted_features = [feature_names[i] for i in indices]
        sorted_importances = importances[indices]

        bars = ax_fi.bar(sorted_features, sorted_importances, color='steelblue', edgecolor='black')
        ax_fi.set_title(f"Ważność Cech ({title_prefix})", fontsize=14, fontweight='bold')
        ax_fi.set_ylabel("Waga cechy")
        for bar, v in zip(bars, sorted_importances):
            ax_fi.text(bar.get_x() + bar.get_width()/2, v + 0.005, f"{v:.3f}", ha='center', fontweight='bold')
        plt.tight_layout()
        fig_fi.savefig(os.path.join(CURRENT_OUTPUT_DIR, f"{prefix}_Waznosc_Cech.png"), dpi=300)

        fig_tree = plt.figure(figsize=(24, 12))
        ax_tree = fig_tree.add_subplot(111)

        if isinstance(model, RandomForestClassifier):
            tree_to_plot = model.estimators_[0]
        else: 
            tree_to_plot = model.estimators_[0, 0]

        plot_tree(tree_to_plot, feature_names=feature_names, class_names=class_names_str, filled=True, rounded=True, max_depth=3, fontsize=10, ax=ax_tree)
        ax_tree.set_title(f"Przykładowe Drzewo Decyzyjne z modelu {title_prefix} (głębokość 3)", fontsize=16, fontweight='bold')
        plt.tight_layout()
        fig_tree.savefig(os.path.join(CURRENT_OUTPUT_DIR, f"{prefix}_Drzewo_Decyzyjne.png"), dpi=300)

        plt.close('all')

    generate_ml_plots(rf_clf, rf_y_pred_all, rf_y_pred_test, "09_RF", "Random Forest")
    generate_ml_plots(gb_clf, gb_y_pred_all, gb_y_pred_test, "10_GB", "Gradient Boosting")

    del M_matrix, df, idx_a, idx_b, r2_values, valid_pairs
    gc.collect()

print("\n[ZAKOŃCZONO SUKCESEM] .")

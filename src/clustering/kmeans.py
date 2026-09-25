"""Кластеризация: подбор k, KMeans, PCA, характерные треки.

Общая тема, не привязана к Sound.
Использование:
    from clustering.kmeans import (
        find_optimal_k, fit_clustering, fit_pca, mark_characteristic,
    )
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA


RANDOM_STATE = 42
K_RANGE = range(2, 7)


def find_optimal_k(X_scaled, k_range=K_RANGE, metric='silhouette'):
    """
    Перебирает k, считает метрику качества, возвращает лучший.

    Returns
    -------
    best_k : int
    best_score : float
    all_scores : dict {k: score}
    """
    if metric != 'silhouette':
        raise ValueError(f"Неподдерживаемая метрика: {metric}. Сейчас только 'silhouette'.")

    scores = {}
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = km.fit_predict(X_scaled)
        scores[k] = silhouette_score(X_scaled, labels)

    best_k = max(scores, key=scores.get)
    return best_k, scores[best_k], scores


def fit_clustering(X_scaled, k):
    """Обучает KMeans с заданным k. Возвращает KMeans."""
    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
    km.fit(X_scaled)
    return km


def fit_pca(X_scaled, n_components=2):
    """Обучает PCA для визуализации. Возвращает PCA."""
    pca = PCA(n_components=n_components, random_state=RANDOM_STATE)
    pca.fit(X_scaled)
    return pca


def mark_characteristic(df, distance_col='distance_to_center',
                        cluster_col='cluster', top_n=5):
    """
    Помечает топ-N ближайших к центрам своих кластеров.

    Требует: df с колонками distance_col и cluster_col.
    Возвращает df с добавленной колонкой is_characteristic (bool).
    """
    df = df.copy()
    df['is_characteristic'] = False

    for cluster_id in df[cluster_col].unique():
        mask = df[cluster_col] == cluster_id
        idx_top = df.loc[mask].nsmallest(top_n, distance_col).index
        df.loc[idx_top, 'is_characteristic'] = True

    return df
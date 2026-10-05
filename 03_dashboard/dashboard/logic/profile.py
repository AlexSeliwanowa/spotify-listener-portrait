LEVEL_NUM = {'Low': 0, 'Medium': 1, 'High': 2}
CODE_LETTER_TO_LEVEL = {'L': 'Low', 'M': 'Medium', 'H': 'High'}


def nearest_profile(user_levels, profiles):
    """Ближайший архетип по евклидову расстоянию уровней 4 осей.

    user_levels: список уровней ['Low', 'Medium', 'High', ...] по осям
                 Discovery, Retention, Burnout, Variability.
    profiles:    список профилей из profile_labels.json.

    Возвращает (profile_dict, distance).
    """
    nums = [LEVEL_NUM[l] for l in user_levels]
    best_p, best_d = None, None
    for p in profiles:
        code = [LEVEL_NUM[CODE_LETTER_TO_LEVEL[c]] for c in p['code']]
        d = sum((a - b) ** 2 for a, b in zip(nums, code)) ** 0.5
        if best_d is None or d < best_d:
            best_d, best_p = d, p
    return best_p, best_d


PORTRAIT_AXIS_TO_INDEX = {
    'Discovery': 'Novelty Seeking Index',
    'Retention': 'Loyalty / Retention Index',
    'Burnout': 'Burnout Index',
    'Variability': 'Variability',
}


def get_cluster_name(row):
    """Название кластера по медианам 5 звуковых признаков.

    Ожидает Series/dict с ключами: energy, acousticness, instrumentalness,
    valence, danceability.

    Порядок правил — от узкого к широкому (decision list, most specific wins).
    Узкие правила проверяются первыми, чтобы широкое не перехватывало их зону.
    """
    energy = row['energy']
    acousticness = row['acousticness']
    instrumentalness = row['instrumentalness']
    valence = row['valence']
    danceability = row['danceability']

    # 1. Melancholic Acoustic — 3 тугих условия
    if energy < 0.4 and acousticness >= 0.6 and instrumentalness >= 0.5:
        return 'Melancholic Acoustic'

    # 2. Heavy / Dark Drive — 3 тугих условия (новое)
    elif energy >= 0.7 and valence < 0.3 and danceability < 0.5:
        return 'Heavy / Dark Drive'

    # 3. Bright Chill — 2 тугих условия (новое)
    elif energy < 0.5 and valence >= 0.5 and danceability < 0.6:
        return 'Bright Chill'

    # 4. Lo-Fi — 3 условия (новое)
    elif energy < 0.45 and danceability >= 0.5 and acousticness < 0.3:
        return 'Lo-Fi'

    # 5. Vocal Melancholy
    elif instrumentalness < 0.3 and energy < 0.4 and valence < 0.3:
        return 'Vocal Melancholy'

    # 6. Synthetic Ambient
    elif acousticness < 0.3 and energy < 0.4 and instrumentalness >= 0.5:
        return 'Synthetic Ambient'

    # 7. Atmospheric Ambient
    elif instrumentalness >= 0.7 and energy < 0.4:
        return 'Atmospheric Ambient'

    # 8. Organic Rock / Folk
    elif acousticness >= 0.5 and energy >= 0.5:
        return 'Organic Rock / Folk'

    # 9. Bright Dance
    elif danceability >= 0.6 and valence >= 0.4:
        return 'Bright Dance'

    # 10. Dark Groove — теперь ниже Bright Dance, но выше широких
    elif danceability >= 0.6 and valence < 0.4:
        return 'Dark Groove'

    # 11. Pop Groove
    elif danceability >= 0.5 and acousticness < 0.3 and instrumentalness < 0.3:
        return 'Pop Groove'

    # 12. Vocal Drive
    elif instrumentalness < 0.3 and energy >= 0.5:
        return 'Vocal Drive'

    # 13. Energetic Electronic — самое широкое, проверяется последним
    elif energy >= 0.6 and acousticness < 0.3:
        return 'Energetic Electronic'

    else:
        return 'Mixed Style'
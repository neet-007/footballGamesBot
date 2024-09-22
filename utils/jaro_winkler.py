def jaro_winkler_similarity(s1: str, s2: str) -> float:
    def jaro(s1: str, s2: str) -> float:
        if s1 == s2:
            return 1.0
        len_s1, len_s2 = len(s1), len(s2)
        if len_s1 == 0 or len_s2 == 0:
            return 0.0

        match_distance = int(max(len_s1, len_s2) / 2) - 1
        matches = 0
        transpositions = 0
        s1_matches = [False] * len_s1
        s2_matches = [False] * len_s2

        for i in range(len_s1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len_s2)
            for j in range(start, end):
                if s2_matches[j]:
                    continue
                if s1[i] != s2[j]:
                    continue
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        k = 0
        for i in range(len_s1):
            if s1_matches[i]:
                while not s2_matches[k]:
                    k += 1
                if s1[i] != s2[k]:
                    transpositions += 1
                k += 1
        transpositions //= 2

        jaro_score = (matches / len_s1 + matches / len_s2 + (matches - transpositions) / matches) / 3.0
        return jaro_score

    jaro_score = jaro(s1, s2)
    prefix_length = 0
    max_prefix_length = 4

    for i in range(min(len(s1), len(s2), max_prefix_length)):
        if s1[i] != s2[i]:
            break
        prefix_length += 1

    return jaro_score + (prefix_length * 0.1 * (1 - jaro_score))
games = {}

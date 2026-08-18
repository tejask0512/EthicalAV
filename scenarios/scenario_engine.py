"""
scenario_engine.py
-------------------
Generates AV trolley-style dilemmas, localized to South Korean street life
instead of the generic Moral Machine cast. Each scenario has two groups
("Group A" stays on the AV's current path, "Group B" is the swerve path);
the user picks which group the car should save.

Characters were chosen to surface *Korea-specific* ethical tension points
that the original Moral Machine (built around a US/global sample) doesn't
probe well:
  - 배달 라이더 (delivery riders) - huge, visible occupational risk group
  - 학원 버스 하차 학생 (hagwon shuttle kids) - after-dark school-adjacent risk
  - 경로당 어르신 (senior center elderly) - aging society stakes
  - 교대근무자 (shift workers) - late-night pedestrian exposure
  - 다문화가정 자녀 / 외국인 노동자 (multicultural family child / migrant worker)
    - Korea's real immigration/social-inclusion fault lines
  - 반려동물 동반자 (person with pet)
  - 임산부 (pregnant person)
  - 무단횡단 여부 (jaywalking / legality) - Korea has strong legalism norms
"""

import random
import uuid
from collections import Counter

CHARACTERS = [
    {"id": "delivery_rider", "ko": "배달 라이더", "en": "Delivery rider", "weight_tag": "occupational_risk"},
    {"id": "hagwon_student", "ko": "학원 버스 하차 학생", "en": "Student leaving hagwon shuttle", "weight_tag": "youth"},
    {"id": "elderly", "ko": "경로당 어르신", "en": "Elderly person", "weight_tag": "age_elderly"},
    {"id": "shift_worker", "ko": "교대 근무자", "en": "Night-shift worker", "weight_tag": "occupational_risk"},
    {"id": "child_with_parent", "ko": "부모와 함께 있는 아이", "en": "Child with parent", "weight_tag": "youth"},
    {"id": "pregnant", "ko": "임산부", "en": "Pregnant person", "weight_tag": "vulnerability"},
    {"id": "migrant_worker", "ko": "외국인 노동자", "en": "Migrant worker", "weight_tag": "social_inclusion"},
    {"id": "multicultural_child", "ko": "다문화가정 자녀", "en": "Child of multicultural family", "weight_tag": "social_inclusion"},
    {"id": "pet_owner", "ko": "반려동물과 있는 사람", "en": "Person with a pet", "weight_tag": "companion_animal"},
    {"id": "doctor", "ko": "의사", "en": "Doctor", "weight_tag": "social_value"},
    {"id": "office_worker", "ko": "직장인", "en": "Office worker", "weight_tag": "neutral"},
    {"id": "homeless", "ko": "노숙인", "en": "Homeless person", "weight_tag": "vulnerability"},
    {"id": "disabled_person", "ko": "장애인", "en": "Person with a disability", "weight_tag": "vulnerability"},
    {"id": "athlete", "ko": "운동선수", "en": "Athlete", "weight_tag": "social_value"},
    {"id": "criminal", "ko": "범죄 이력자(무단횡단 중)", "en": "Person with criminal record (jaywalking)", "weight_tag": "legal_status"},
]

CONTEXTS = [
    {"id": "crosswalk_green", "ko": "횡단보도, 보행자 신호 초록불", "legal": "pedestrians_legal"},
    {"id": "jaywalking", "ko": "무단횡단 중", "legal": "pedestrians_illegal"},
    {"id": "school_zone", "ko": "스쿨존, 오후 하교 시간", "legal": "pedestrians_legal"},
    {"id": "late_night_alley", "ko": "심야 골목길", "legal": "ambiguous"},
    {"id": "highway_shoulder", "ko": "고속도로 갓길", "legal": "pedestrians_illegal"},
    {"id": "market_street", "ko": "전통시장 골목", "legal": "ambiguous"},
]

WEATHER = ["맑음", "비", "안개", "야간·가로등 없음"]

PASSENGER_VS_PEDESTRIAN = [
    # Occasionally frame it as passengers-in-the-AV vs pedestrians, the other
    # classic Moral Machine axis.
    True, False, False,
]


def _pick_group(n_min=1, n_max=3):
    n = random.randint(n_min, n_max)
    return random.sample(CHARACTERS, k=min(n, len(CHARACTERS)))


def generate_scenario():
    context = random.choice(CONTEXTS)
    weather = random.choice(WEATHER)

    group_a = _pick_group()
    # ensure group B isn't identical
    group_b = _pick_group()
    tries = 0
    while {c["id"] for c in group_b} == {c["id"] for c in group_a} and tries < 5:
        group_b = _pick_group()
        tries += 1

    passengers_mode = random.choice(PASSENGER_VS_PEDESTRIAN)

    scenario = {
        "scenario_id": str(uuid.uuid4()),
        "context": context,
        "weather": weather,
        "mode": "passengers_vs_pedestrians" if passengers_mode else "pedestrians_vs_pedestrians",
        "group_a": {
            "label": "차량 승객 유지 (Stay in lane)" if passengers_mode else "직진 경로 (Path A)",
            "members": group_a,
        },
        "group_b": {
            "label": "보행자 쪽으로 회피 (Swerve)" if passengers_mode else "회피 경로 (Path B)",
            "members": group_b,
        },
    }
    return scenario


def compute_preference_weights(judgment_rows):
    """
    Given [(scenario_json_str, choice), ...] compute a rough per-tag 'saved
    more often' weighting, analogous to Moral Machine's results page
    (e.g. 'You saved the young over the elderly 80% of the time').
    """
    import json as _json

    saved_tag_counts = Counter()
    seen_tag_counts = Counter()

    for scenario_json, choice in judgment_rows:
        try:
            scenario = _json.loads(scenario_json)
        except Exception:
            continue
        group_a = scenario.get("group_a", {}).get("members", [])
        group_b = scenario.get("group_b", {}).get("members", [])
        saved = group_a if choice == "A" else group_b
        not_saved = group_b if choice == "A" else group_a

        for m in saved:
            saved_tag_counts[m["weight_tag"]] += 1
        for m in saved + not_saved:
            seen_tag_counts[m["weight_tag"]] += 1

    weights = {}
    for tag, seen in seen_tag_counts.items():
        saved = saved_tag_counts.get(tag, 0)
        weights[tag] = round(saved / seen, 3) if seen else None

    return weights


class ScenarioEngine:
    def generate_scenario(self):
        return generate_scenario()

"""Frozen Cox coefficients; baseline survival refers to mean-centered predictors."""
import json
import math
from pathlib import Path

MODEL = json.loads(Path(__file__).with_name('model.json').read_text(encoding='utf-8'))

def predict(values):
    clean = {}
    for name in MODEL['coefficients']:
        value = values.get(name)
        if isinstance(value, bool) or value is None:
            raise ValueError('Please enter age, sex, and all three scores.')
        try:
            v = float(value)
        except (ValueError, TypeError):
            raise ValueError('Inputs must be valid numbers.')
        if not math.isfinite(v):
            raise ValueError('Inputs must be finite numbers.')
        if name == 'age':
            if not 20 <= v <= 100:
                raise ValueError('Age must be between 20 and 100 years.')
        elif name == 'sex_num':
            if v not in (0, 1):
                raise ValueError('Invalid sex encoding.')
        elif v not in (0, 1, 2, 3):
            raise ValueError('MRI scores must be integers 0, 1, 2, or 3.')
        clean[name] = v
    lp = sum(MODEL['coefficients'][k] * clean[k] for k in clean)
    centered = sum(MODEL['coefficients'][k] * (clean[k] - MODEL['means'][k]) for k in clean)
    relative = math.exp(centered)
    risk = {year: -math.expm1(math.log(s) * relative) for year, s in MODEL['baseline_survival'].items()}
    t = MODEL['thresholds']
    return {'inputs': clean, 'linear_score': lp, 'centered_score': centered,
            'relative_hazard': relative, 'risk': risk,
            'group': 'High risk' if lp >= t['median'] else 'Low risk',
            'tertile': 'High' if lp >= t['tertile_2'] else 'Intermediate' if lp >= t['tertile_1'] else 'Low',
            'outside_training_age': not 45 <= clean['age'] <= 79,
            'threshold': t['median']}

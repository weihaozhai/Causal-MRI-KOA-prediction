"""Optional comparison with an explicitly supplied authorized training dataset."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from predictor import MODEL, predict

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training-data', type=Path, required=True,
                        help='Authorized OAI development Parquet file; not distributed.')
    args = parser.parse_args()
    data = pd.read_parquet(args.training_data)
    features = list(MODEL['coefficients'])
    required = features + ['event', 'time_months']
    missing = set(required) - set(data.columns)
    if missing:
        parser.error('Missing required columns: ' + ', '.join(sorted(missing)))
    cph = CoxPHFitter(penalizer=0.01).fit(data[required], duration_col='time_months', event_col='event')
    for f in features:
        assert abs(cph.params_[f] - MODEL['coefficients'][f]) < 1e-12
        assert abs(cph._norm_mean[f] - MODEL['means'][f]) < 1e-12
    expected = 1 - cph.predict_survival_function(data[features], times=[60,120]).values.T
    actual = np.array([[predict(row)['risk'][y] for y in ('5','10')]
                       for row in data[features].to_dict('records')])
    error = float(np.max(np.abs(actual-expected)))
    assert error < 1e-12
    lp = data[features].dot(pd.Series(MODEL['coefficients']))
    assert abs(lp.median() - MODEL['thresholds']['median']) < 1e-12
    assert np.allclose(lp.quantile([1/3,2/3]),
                       [MODEL['thresholds']['tertile_1'], MODEL['thresholds']['tertile_2']], rtol=0, atol=1e-12)
    print(json.dumps({'checked_training_knees':len(data), 'max_probability_error':error,
                      'coefficients_match':True,'centering_match':True,'thresholds_match':True}, indent=2))

if __name__ == '__main__':
    main()

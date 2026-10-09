"""Start one fresh RSI experiment (framework v2). Real model calls; requires an authorized config.

    python src/rsi_run.py --config config/chem-sonnet-v2.json [--check]

--check validates the config, roles and initial bundle without any model call.
"""
import argparse
from pathlib import Path

from rsi import bundle as portable
from rsi.controller import ROOT, Experiment, authorized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    experiment = Experiment(args.config)
    if args.check:
        initial = ROOT/experiment.config.get('initial_bundle', 'harness/working')
        errors = portable.validate(initial, experiment.capabilities)
        print('config ok; authorized:', authorized(experiment.config), '; initial bundle errors:', errors or 'none',
              '; output exists:', experiment.root.exists())
        return
    experiment.run()


if __name__ == '__main__':
    main()

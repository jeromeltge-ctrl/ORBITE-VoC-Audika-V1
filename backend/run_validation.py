"""Persist truthful unittest results, including skips, for local/CI review."""
import argparse
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    suite=unittest.defaultTestLoader.discover(str(Path(__file__).parent),pattern='test_*.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'at':datetime.now(timezone.utc).isoformat(),'python':sys.version,
            'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'skipped':[{'test':str(test),'reason':reason} for test,reason in result.skipped],
            'successful':result.wasSuccessful(),
            'failure_details':[{'test':str(test),'traceback':trace} for test,trace in result.failures+result.errors]}
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':sys.exit(main())

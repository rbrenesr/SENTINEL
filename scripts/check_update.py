"""Decide whether a scheduled check needs a new collection. No network calls."""
import argparse
import datetime as dt
import json
import os
import pathlib

UTC = dt.timezone.utc
MIN_INTERVAL_MINUTES = 25


def collection_due(snapshot, event, now=None):
    if event != 'schedule':
        return True, 'manual_or_code_change'
    now = now or dt.datetime.now(UTC)
    try:
        last = dt.datetime.fromisoformat(snapshot['updatedAt'].replace('Z', '+00:00'))
        if last.tzinfo is None or not isinstance(snapshot['items'], list) or not isinstance(snapshot['sources'], list):
            raise ValueError('Invalid snapshot')
        age = (now - last).total_seconds() / 60
        if age < -5:
            return True, 'invalid_future_timestamp'
        return (True, 'collection_due') if age >= MIN_INTERVAL_MINUTES else (False, 'recent_success')
    except (ValueError, TypeError, KeyError, AttributeError):
        return True, 'missing_or_invalid_snapshot'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', default=os.environ.get('GITHUB_EVENT_NAME', 'workflow_dispatch'))
    parser.add_argument('--snapshot', type=pathlib.Path, default=pathlib.Path('data/news.json'))
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding='utf8'))
    except (OSError, ValueError):
        snapshot = {}
    due, reason = collection_due(snapshot, args.event)
    print(f'collection_due={str(due).lower()} reason={reason}')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf8') as output:
            output.write(f'due={str(due).lower()}\nreason={reason}\n')


if __name__ == '__main__':
    main()

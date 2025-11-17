"""Challenge state management with cross-process file locking"""
import os
import json
from datetime import datetime, timezone
from .file_utils import lock_file, unlock_file


class ChallengeTracker:
    """Manages challenge tracking and completion status with cross-process file locking"""

    def __init__(self, challenges_file="challenges.json"):
        self.challenges_file = challenges_file
        if not os.path.exists(self.challenges_file):
            with open(self.challenges_file, 'w') as f:
                json.dump({}, f)

    def _locked_operation(self, modify_func):
        with open(self.challenges_file, 'r+') as f:
            lock_file(f)
            try:
                f.seek(0)
                content = f.read()
                challenges = json.loads(content) if content else {}

                modified_challenges, result = modify_func(challenges)

                f.seek(0)
                f.truncate()
                json.dump(modified_challenges, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

                return result
            finally:
                unlock_file(f)

    def register_challenge(self, challenge):
        def modify(challenges):
            challenge_id = challenge['challenge_id']
            if challenge_id not in challenges:
                challenges[challenge_id] = {
                    'challenge_id': challenge['challenge_id'],
                    'day': challenge.get('day'),
                    'challenge_number': challenge.get('challenge_number'),
                    'difficulty': challenge['difficulty'],
                    'no_pre_mine': challenge['no_pre_mine'],
                    'no_pre_mine_hour': challenge['no_pre_mine_hour'],
                    'latest_submission': challenge['latest_submission'],
                    'discovered_at': datetime.now(timezone.utc).isoformat(),
                    'solved_by': [],
                    'dev_solved_by': []
                }
                return (challenges, True)
            return (challenges, False)

        return self._locked_operation(modify)

    def mark_solved(self, challenge_id, wallet_address):
        def modify(challenges):
            if challenge_id in challenges:
                if wallet_address not in challenges[challenge_id]['solved_by']:
                    challenges[challenge_id]['solved_by'].append(wallet_address)
                    return (challenges, True)
            return (challenges, False)

        return self._locked_operation(modify)

    def get_unsolved_challenge(self, wallet_address):
        """
        Select the best challenge for this wallet:

        - Must not be already solved by this wallet.
        - Must have > 120s remaining until latest_submission.
        - Prefer the EASIEST challenge first:
            * Easiest = lowest numeric difficulty value.
        - Tie-breaker: earlier deadline first.
        """
        def find_challenge(challenges):
            now = datetime.now(timezone.utc)

            best = None
            best_diff = None
            best_deadline = None

            for data in challenges.values():
                # Skip if this wallet already solved it
                solved_by = data.get('solved_by', [])
                if wallet_address in solved_by:
                    continue

                # Parse and validate deadline
                latest = data.get('latest_submission')
                if not latest:
                    continue
                try:
                    deadline = datetime.fromisoformat(
                        latest.replace('Z', '+00:00')
                    )
                except Exception:
                    # Malformed timestamp: ignore this challenge
                    continue

                time_left = (deadline - now).total_seconds()
                if time_left <= 120:
                    # Too close to expiry or expired; skip
                    continue

                # Parse difficulty; must match mining logic prefix
                diff_hex = data.get('difficulty')
                if not diff_hex:
                    continue
                try:
                    difficulty_val = int(diff_hex[:8], 16)
                except Exception:
                    # Invalid difficulty: skip
                    continue

                if best is None:
                    best = data
                    best_diff = difficulty_val
                    best_deadline = deadline
                else:
                    # Prefer EASIER (numerically LOWER) difficulty value
                    if difficulty_val < best_diff:
                        best = data
                        best_diff = difficulty_val
                        best_deadline = deadline
                    # If difficulty equal, prefer the one expiring sooner
                    elif difficulty_val == best_diff and deadline < best_deadline:
                        best = data
                        best_deadline = deadline

            return challenges, dict(best) if best is not None else None

        return self._locked_operation(find_challenge)

    def count_wallet_completions(self, wallet_addresses):
        """Count total challenges completed by given wallet addresses"""
        def count_completions(challenges):
            total = 0
            for challenge_data in challenges.values():
                solved_by = challenge_data.get('solved_by', [])
                for addr in solved_by:
                    if addr in wallet_addresses:
                        total += 1
            return (challenges, total)

        return self._locked_operation(count_completions)

    def mark_dev_solved(self, challenge_id, dev_address):
        """Mark a challenge as solved by a dev address"""
        def modify(challenges):
            if challenge_id in challenges:
                if 'dev_solved_by' not in challenges[challenge_id]:
                    challenges[challenge_id]['dev_solved_by'] = []
                if dev_address not in challenges[challenge_id]['dev_solved_by']:
                    challenges[challenge_id]['dev_solved_by'].append(dev_address)
                    return (challenges, True)
            return (challenges, False)

        return self._locked_operation(modify)

    def is_dev_solved(self, challenge_id, dev_address):
        """Check if a dev address has already solved this challenge"""
        def check(challenges):
            if challenge_id in challenges:
                dev_solved = challenges[challenge_id].get('dev_solved_by', [])
                return (challenges, dev_address in dev_solved)
            return (challenges, False)

        return self._locked_operation(check)

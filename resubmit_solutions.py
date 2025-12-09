import requests
import sys
import os
import json
import shutil
from datetime import datetime

from proxy_config import create_proxy_session

API_BASE = "https://scavenger.prod.gd.midnighttge.io"
SOLUTIONS_FILE = "solutions.csv"
DEFAULT_WALLETS_FILE = "wallets.json"

SESSION, _ = create_proxy_session()


def load_wallets(wallets_file):
    """Load wallets from file and index by address."""
    if not os.path.exists(wallets_file):
        print(f"⚠️  Wallet file {wallets_file} not found. Registration will be skipped.")
        return {}

    try:
        with open(wallets_file, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  Failed to load wallets from {wallets_file}: {e}. Registration will be skipped.")
        return {}

    wallets_by_address = {}
    if isinstance(data, list):
        for wallet in data:
            address = wallet.get("address")
            if address:
                wallets_by_address[address] = wallet
    elif isinstance(data, dict):
        # Allow dictionary storage (address -> wallet)
        for address, wallet in data.items():
            wallets_by_address[address] = wallet

    print(f"✓ Loaded {len(wallets_by_address)} wallet(s) from {wallets_file} for registration support.")
    return wallets_by_address


def register_wallet_with_api(address, wallet_map):
    """Attempt to register a wallet by address using cached wallet data."""
    wallet = wallet_map.get(address)
    if not wallet:
        return (False, f"No wallet data found for address {address}")

    signature = wallet.get("signature")
    pubkey = wallet.get("pubkey")

    if not signature or not pubkey:
        return (False, f"Wallet data for {address} missing signature or pubkey")

    url = f"{API_BASE}/register/{address}/{signature}/{pubkey}"
    try:
        response = SESSION.post(url, json={}, timeout=15)
        response.raise_for_status()
        return (True, "Registered successfully")
    except requests.exceptions.HTTPError as e:
        message = e.response.text
        try:
            data = e.response.json()
            message = data.get("message", message)
        except ValueError:
            pass

        if e.response.status_code == 400 and message and "already" in message.lower():
            return (True, message)

        return (False, f"HTTP {e.response.status_code}: {message}")
    except requests.exceptions.Timeout:
        return (False, "Registration request timed out")
    except Exception as e:
        return (False, str(e))


def submit_solution(address, challenge_id, nonce):
    """Submit a solution to the API."""
    url = f"{API_BASE}/solution/{address}/{challenge_id}/{nonce}"

    try:
        response = SESSION.post(url, json={}, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("crypto_receipt") is not None:
            return ("success", "Solution accepted")
        else:
            return ("rejected", "No crypto receipt in response")

    except requests.exceptions.HTTPError as e:
        error_detail = e.response.text
        lower_detail = error_detail.lower()
        try:
            error_json = e.response.json()
            error_message = error_json.get("message", error_detail)
        except ValueError:
            error_message = error_detail
        lower_message = error_message.lower() if isinstance(error_message, str) else ""

        if "solution already exists" in lower_detail or "solution already exists" in lower_message:
            return ("already_exists", "Solution already exists")
        if lower_message and "address" in lower_message and "not registered" in lower_message:
            return ("needs_registration", error_message)
        return ("error", f"HTTP {e.response.status_code}: {error_message}")

    except requests.exceptions.Timeout:
        return ("error", "Request timed out")

    except Exception as e:
        return ("error", str(e))


def create_backup(file_path):
    """Create a timestamped backup of the given file."""
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{file_path}.{timestamp}.bak"
    try:
        shutil.copyfile(file_path, backup_path)
        print(f"✓ Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"⚠️  Failed to create backup for {file_path}: {e}")
        return None


def parse_args():
    """Parse simple command-line arguments."""
    wallets_file = DEFAULT_WALLETS_FILE
    use_defensio = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--wallets", "--wallets-file") and i + 1 < len(args):
            wallets_file = args[i + 1]
            i += 2
        elif arg == "--defensio":
            use_defensio = True
            i += 1
        else:
            i += 1
    return wallets_file, use_defensio


def main():
    global API_BASE
    wallets_file, use_defensio = parse_args()

    # Update API_BASE if using Defensio
    if use_defensio:
        API_BASE = "https://mine.defensio.io/api"

    if not os.path.exists(SOLUTIONS_FILE):
        print(f"Error: {SOLUTIONS_FILE} not found")
        return 1

    create_backup(SOLUTIONS_FILE)

    # Read all solutions
    with open(SOLUTIONS_FILE, 'r') as f:
        lines = f.readlines()

    if not lines:
        print(f"{SOLUTIONS_FILE} is empty")
        return 0

    wallet_map = load_wallets(wallets_file)

    print(f"Found {len(lines)} solution(s) to resubmit")
    print("="*70)

    results = {
        "success": 0,
        "already_exists": 0,
        "rejected": 0,
        "error": 0,
        "registered": 0,
        "window_closed": 0
    }

    failed_solutions = []

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        try:
            parts = line.split(',')
            if len(parts) != 3:
                print(f"[{i}] SKIP: Invalid format: {line}")
                failed_solutions.append(line)
                continue

            address, challenge_id, nonce = parts

            print(f"[{i}/{len(lines)}] Submitting: {address[:20]}... / {challenge_id[:20]}...", end=" ")
            status, message = submit_solution(address, challenge_id, nonce)

            if status == "needs_registration":
                print("⚠️  ADDRESS NOT REGISTERED")
                success, reg_message = register_wallet_with_api(address, wallet_map)
                if success:
                    results["registered"] += 1
                    print(f"    → Registered address ({reg_message}). Retrying submission...", end=" ")
                    status, message = submit_solution(address, challenge_id, nonce)
                else:
                    print(f"    → Failed to register address: {reg_message}")
                    results["error"] += 1
                    failed_solutions.append(line)
                    continue

            message_lower = message.lower() if isinstance(message, str) else ""

            if status == "success":
                print("✓ SUCCESS")
                results["success"] += 1
            elif status == "already_exists":
                print("✓ ALREADY EXISTS")
                results["already_exists"] += 1
            elif "window" in message_lower and "closed" in message_lower:
                print(f"⚠️  WINDOW CLOSED: {message}")
                results["window_closed"] += 1
            elif status == "rejected":
                print(f"✗ REJECTED: {message}")
                results["rejected"] += 1
                failed_solutions.append(line)
            else:
                print(f"✗ ERROR: {message}")
                results["error"] += 1
                failed_solutions.append(line)

        except Exception as e:
            print(f"[{i}] ERROR: {e}")
            failed_solutions.append(line)
            results["error"] += 1

    print()
    print("="*70)
    print("SUMMARY:")
    print(f"  Successful submissions:  {results['success']}")
    print(f"  Already existed:         {results['already_exists']}")
    print(f"  Rejected:                {results['rejected']}")
    print(f"  Errors:                  {results['error']}")
    print(f"  Window closed:           {results['window_closed']}")
    print(f"  Registered addresses:    {results['registered']}")
    print(f"  Total:                   {len(lines)}")
    print("="*70)

    # Automatically rewrite solutions.csv with only failed submissions
    if failed_solutions:
        with open(SOLUTIONS_FILE, 'w') as f:
            for solution in failed_solutions:
                f.write(solution + '\n')
        print(f"\n✓ Updated {SOLUTIONS_FILE} - kept {len(failed_solutions)} failed solution(s)")
        print(f"  Removed {results['success'] + results['already_exists']} successful/existing solution(s)")
    else:
        with open(SOLUTIONS_FILE, 'w') as f:
            f.truncate()
        print(f"\n✓ All solutions submitted successfully or already existed - wiped {SOLUTIONS_FILE}")
        print(f"  Removed {results['success'] + results['already_exists']} successful/existing solution(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

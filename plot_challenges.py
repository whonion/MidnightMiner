
import json
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# This script requires matplotlib. Please install it using:
# pip install matplotlib

def plot_solved_challenges_over_time():
    """
    Reads challenges.json and wallets.json, and uses matplotlib to display a graph
    of the cumulative number of solutions from the user's wallets over time.
    """
    try:
        with open('wallets.json', 'r') as f:
            wallets_data = json.load(f)
        user_addresses = {wallet['address'] for wallet in wallets_data}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        print("Warning: Could not load user wallets from wallets.json. The plot will show all solutions.")
        user_addresses = set()

    try:
        with open('challenges.json', 'r') as f:
            challenges_data = json.load(f)
    except FileNotFoundError:
        print("Error: challenges.json not found.")
        return
    except json.JSONDecodeError:
        print("Error: Could not decode challenges.json.")
        return

    solutions_by_time = []
    for challenge in challenges_data.values():
        time_str = challenge.get("discovered_at")
        if not time_str:
            continue

        solution_count = 0
        if user_addresses:
            # Count solutions from user's wallets
            user_solutions = [addr for addr in challenge.get('solved_by', []) if addr in user_addresses]
            solution_count = len(user_solutions)
        else:
            # Fallback to counting all solutions if user wallets aren't loaded
            solution_count = len(challenge.get('solved_by', []))

        if solution_count > 0:
            try:
                dt_object = datetime.fromisoformat(time_str)
                solutions_by_time.append((dt_object, solution_count))
            except (ValueError, TypeError):
                print(f"Warning: Could not parse timestamp '{time_str}' for a challenge.")

    if not solutions_by_time:
        print("No solutions found to plot.")
        return

    # Sort by timestamp
    solutions_by_time.sort(key=lambda x: x[0])

    # Create cumulative data for plotting
    plot_times = [item[0] for item in solutions_by_time]
    solution_counts = [item[1] for item in solutions_by_time]

    cumulative_solutions = []
    current_total = 0
    for count in solution_counts:
        current_total += count
        cumulative_solutions.append(current_total)

    # Plotting
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(plot_times, cumulative_solutions, marker='o', linestyle='-', color='cyan')

    # Formatting the plot
    ax.set_title('Cumulative Solutions by Your Wallets Over Time', color='white')
    ax.set_xlabel('Date (of Challenge Discovery)', color='white')
    ax.set_ylabel('Cumulative Number of Solutions', color='white')
    ax.grid(True, which='both', linestyle='--', linewidth=0.5, color='gray')

    # Improve date formatting on the x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    plt.xticks(rotation=45, ha='right', color='white')
    plt.yticks(color='white')
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')


    plt.tight_layout()

    # Save the figure
    output_filename = 'solved_challenges_over_time.png'
    plt.savefig(output_filename, facecolor='#222222')
    # Only show the plot if a display is available (e.g., not on a headless server)
    if os.environ.get('DISPLAY'):
        plt.show()
    else:
        print("No display found. Skipping plot window.")
    print(f"Graph saved to {output_filename}")


def plot_balances_over_time():
    """
    Reads balances.json and plots NIGHT balance over time.
    """
    balances_file = 'balances.json'

    if not os.path.exists(balances_file):
        print(f"Warning: {balances_file} not found. No balance data to plot.")
        print("Balance tracking will start when the miner runs and fetches balances.")
        return

    try:
        with open(balances_file, 'r') as f:
            balances_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Error: Could not read {balances_file}.")
        return

    if not balances_data or 'snapshots' not in balances_data:
        print(f"Warning: No balance snapshots found in {balances_file}.")
        return

    snapshots = balances_data['snapshots']
    if not snapshots:
        print("No balance data to plot.")
        return

    # Parse timestamps and balances
    balance_times = []
    balance_values = []

    for snapshot in snapshots:
        timestamp_str = snapshot.get('timestamp')
        balance = snapshot.get('balance', 0)

        if timestamp_str:
            try:
                dt_object = datetime.fromisoformat(timestamp_str)
                balance_times.append(dt_object)
                balance_values.append(balance)
            except (ValueError, TypeError):
                print(f"Warning: Could not parse timestamp '{timestamp_str}'.")

    if not balance_times:
        print("No valid balance data to plot.")
        return

    # Sort by timestamp
    sorted_data = sorted(zip(balance_times, balance_values), key=lambda x: x[0])
    balance_times, balance_values = zip(*sorted_data)
    balance_times = list(balance_times)
    balance_values = list(balance_values)

    # Plotting
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(balance_times, balance_values, marker='o', linestyle='-', color='green', linewidth=2, markersize=4)

    # Formatting the plot
    ax.set_title('NIGHT Balance Over Time', color='white', fontsize=14)
    ax.set_xlabel('Date', color='white')
    ax.set_ylabel('NIGHT Balance', color='white')
    ax.grid(True, which='both', linestyle='--', linewidth=0.5, color='gray')

    # Improve date formatting on the x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    plt.xticks(rotation=45, ha='right', color='white')
    plt.yticks(color='white')
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')

    # Add value annotations for first, last, and significant changes
    if len(balance_values) > 0:
        # Annotate first point
        ax.annotate(f'{balance_values[0]:.2f}',
                   xy=(balance_times[0], balance_values[0]),
                   xytext=(10, 10), textcoords='offset points',
                   color='white', fontsize=9,
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))

        # Annotate last point
        ax.annotate(f'{balance_values[-1]:.2f}',
                   xy=(balance_times[-1], balance_values[-1]),
                   xytext=(10, -20), textcoords='offset points',
                   color='green', fontsize=10, weight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))

    plt.tight_layout()

    # Save the figure
    output_filename = 'balances_over_time.png'
    plt.savefig(output_filename, facecolor='#222222')
    if os.environ.get('DISPLAY'):
        plt.show()
    else:
        print("No display found. Skipping plot window.")
    print(f"Balance graph saved to {output_filename}")


def plot_combined():
    """
    Plot both solutions and balances on separate subplots.
    """
    # Load wallets
    try:
        with open('wallets.json', 'r') as f:
            wallets_data = json.load(f)
        user_addresses = {wallet['address'] for wallet in wallets_data}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        print("Warning: Could not load user wallets from wallets.json.")
        user_addresses = set()

    # Load challenges
    try:
        with open('challenges.json', 'r') as f:
            challenges_data = json.load(f)
    except FileNotFoundError:
        print("Error: challenges.json not found.")
        return
    except json.JSONDecodeError:
        print("Error: Could not decode challenges.json.")
        return

    # Process solutions data
    solutions_by_time = []
    for challenge in challenges_data.values():
        time_str = challenge.get("discovered_at")
        if not time_str:
            continue

        solution_count = 0
        if user_addresses:
            user_solutions = [addr for addr in challenge.get('solved_by', []) if addr in user_addresses]
            solution_count = len(user_solutions)
        else:
            solution_count = len(challenge.get('solved_by', []))

        if solution_count > 0:
            try:
                dt_object = datetime.fromisoformat(time_str)
                solutions_by_time.append((dt_object, solution_count))
            except (ValueError, TypeError):
                pass

    # Process balance data
    balances_file = 'balances.json'
    balance_times = []
    balance_values = []

    if os.path.exists(balances_file):
        try:
            with open(balances_file, 'r') as f:
                balances_data = json.load(f)

            if balances_data and 'snapshots' in balances_data:
                for snapshot in balances_data['snapshots']:
                    timestamp_str = snapshot.get('timestamp')
                    balance = snapshot.get('balance', 0)
                    if timestamp_str:
                        try:
                            dt_object = datetime.fromisoformat(timestamp_str)
                            balance_times.append(dt_object)
                            balance_values.append(balance)
                        except (ValueError, TypeError):
                            pass
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # Sort balance data
    if balance_times:
        sorted_balance = sorted(zip(balance_times, balance_values), key=lambda x: x[0])
        balance_times, balance_values = zip(*sorted_balance)
        balance_times = list(balance_times)
        balance_values = list(balance_values)

    # Create plot with two subplots
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # Plot solutions
    if solutions_by_time:
        solutions_by_time.sort(key=lambda x: x[0])
        plot_times = [item[0] for item in solutions_by_time]
        solution_counts = [item[1] for item in solutions_by_time]

        cumulative_solutions = []
        current_total = 0
        for count in solution_counts:
            current_total += count
            cumulative_solutions.append(current_total)

        ax1.plot(plot_times, cumulative_solutions, marker='o', linestyle='-', color='cyan', linewidth=2, markersize=4)
        ax1.set_title('Cumulative Solutions Over Time', color='white', fontsize=14)
        ax1.set_ylabel('Cumulative Number of Solutions', color='white')
        ax1.grid(True, which='both', linestyle='--', linewidth=0.5, color='gray')
        ax1.tick_params(colors='white')
    else:
        ax1.text(0.5, 0.5, 'No solution data available',
                transform=ax1.transAxes, ha='center', va='center', color='white')
        ax1.set_title('Cumulative Solutions Over Time', color='white', fontsize=14)
        ax1.set_ylabel('Cumulative Number of Solutions', color='white')

    # Plot balances
    if balance_times:
        ax2.plot(balance_times, balance_values, marker='o', linestyle='-', color='green', linewidth=2, markersize=4)
        ax2.set_title('NIGHT Balance Over Time', color='white', fontsize=14)
        ax2.set_ylabel('NIGHT Balance', color='white')
        ax2.set_xlabel('Date', color='white')
        ax2.grid(True, which='both', linestyle='--', linewidth=0.5, color='gray')
        ax2.tick_params(colors='white')

        # Annotate last balance
        if len(balance_values) > 0:
            ax2.annotate(f'{balance_values[-1]:.2f}',
                        xy=(balance_times[-1], balance_values[-1]),
                        xytext=(10, -20), textcoords='offset points',
                        color='green', fontsize=10, weight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
    else:
        ax2.text(0.5, 0.5, 'No balance data available',
                transform=ax2.transAxes, ha='center', va='center', color='white')
        ax2.set_title('NIGHT Balance Over Time', color='white', fontsize=14)
        ax2.set_ylabel('NIGHT Balance', color='white')
        ax2.set_xlabel('Date', color='white')

    # Format x-axis
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right', color='white')

    plt.tight_layout()

    # Save the figure
    output_filename = 'mining_statistics.png'
    plt.savefig(output_filename, facecolor='#222222')
    if os.environ.get('DISPLAY'):
        plt.show()
    else:
        print("No display found. Skipping plot window.")
    print(f"Combined graph saved to {output_filename}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--balances-only':
        plot_balances_over_time()
    elif len(sys.argv) > 1 and sys.argv[1] == '--combined':
        plot_combined()
    else:
        plot_solved_challenges_over_time()
        plot_balances_over_time()

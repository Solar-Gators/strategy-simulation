import os
import platform
import subprocess
import sys

from mystic.monitors import VerboseMonitor
from mystic.solvers import *
from mystic.strategy import Best1Bin
from mystic.termination import VTR

CALLS_BETWEEN_IMAGE = 20
MAX_VELOCITY_ALLOWED = 40.0
MAX_ACCELERATION_ALLOWED = 3.0  # m/s^2
MAX_DECCELERATION_ALLOWED = 3.0
MAX_ENERGY_CONS = 1300
MAX_CENTRIPETAL_ALLOWED = 3.0  # m/s^2

try:
    subprocess.run(["go", "build", "."])
except:
    print("Ensure Go is installed! Using binaries...\n")

if platform.system() == "Windows":
    cli_program = "./strategy-simulation.exe"
else:
    cli_program = "./strategy-simulation"


def call_cli_program(x, endArg):
    return subprocess.run(
        [cli_program] + list(map(str, x)) + [str(endArg)],
        capture_output=True,
        text=True,
    ).stdout


def get_expected_argument_count():
    output = subprocess.run([cli_program], capture_output=True, text=True).stdout
    try:
        return int(output.split("Expected argument count:")[1].split("\n")[0])
    except (IndexError, ValueError):
        print("Could not determine the expected argument count from the CLI program.")
        sys.exit(1)


output_cache = {}
i = 0


def get_output(x):
    global i
    autoEndArg = "" if i % CALLS_BETWEEN_IMAGE == 0 else "none"
    i += 1
    x_tuple = tuple(x)
    if x_tuple not in output_cache:
        output_cache[x_tuple] = call_cli_program(x, autoEndArg)
    return output_cache[x_tuple]


def parse_value(value, output):
    return float(output.split(value)[1].split("\n")[0])


def objective(strategy_to_test):
    output = get_output(strategy_to_test)
    try:
        time_elapsed = parse_value("Time Elapsed (s):", output)
        energy_consumption = parse_value("Energy Consumption (W):", output)
        initial_velocity = parse_value("Initial Velocity (m/s):", output)
        final_velocity = parse_value("Final Velocity (m/s):", output)
        max_velocity = parse_value("Max Velocity (m/s):", output)
        min_velocity = parse_value("Min Velocity (m/s):", output)
        max_acceleration = parse_value("Max Acceleration (m/s^2):", output)
        min_acceleration = parse_value("Min Acceleration (m/s^2):", output)
        max_centripetal_force = parse_value("Max Centripetal Force (N):", output)

        objective_value = time_elapsed

        # Check energy consumption constraint
        if energy_consumption > MAX_ENERGY_CONS or energy_consumption < 0:
            objective_value += abs(energy_consumption - MAX_ENERGY_CONS) * 100

        # Check velocity constraints
        if max_velocity > MAX_VELOCITY_ALLOWED:
            objective_value += (max_velocity - MAX_VELOCITY_ALLOWED) * 100

        if min_velocity < 0:
            objective_value += abs(min_velocity) * 100

        if max_acceleration > MAX_ACCELERATION_ALLOWED:
            objective_value += (max_acceleration - MAX_ACCELERATION_ALLOWED) * 100

        if min_acceleration < -MAX_DECCELERATION_ALLOWED:
            objective_value += (abs(min_acceleration) - MAX_DECCELERATION_ALLOWED) * 100

        if max_centripetal_force > MAX_CENTRIPETAL_ALLOWED:
            objective_value += (MAX_CENTRIPETAL_ALLOWED-max_centripetal_force) * 100

        # Check the percentage difference constraint
        velocity_difference = abs(final_velocity - initial_velocity)

        objective_value += abs(velocity_difference) * 100

        # If all constraints are satisfied, return the time elapsed
        return (
            objective_value
            if objective_value != float("inf") and objective_value >= 0
            else sys.float_info.max
        )
    except (ValueError, IndexError, OverflowError):
        # If parsing fails, return max float value as penalty
        return sys.float_info.max


# Initialization
expected_args = get_expected_argument_count()
npts = 20  # Number of points in the lattice (adjust based on problem size)
bounds = [(0, MAX_VELOCITY_ALLOWED)] * expected_args  # Assuming bounds are known
mon = VerboseMonitor(10)

# Configure and solve using LatticeSolver
cube_root_npts = int(round(npts ** (1 / expected_args)))  # For 3D: npts ** (1/3)
nbins = (cube_root_npts,) * expected_args  # Adjust this based on your problem

# Initialization for target value
target_value = 0.01  # Set this to your desired target for the objective function

# Configure and solve using LatticeSolver
solver = SparsitySolver(expected_args, npts=npts)
solver.SetEvaluationMonitor(mon)
# Use VTR with the target value directly
solver.Solve(objective, termination=VTR(target_value), strategy=Best1Bin, disp=True)

res = solver.Solution()
print("Optimized Result:", res)
print("Objective Value:", objective(res))
output_cache.clear()
print(call_cli_program(res, ""))

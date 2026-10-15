from swmm.toolkit import solver
version = solver.swmm_get_version()
assert version == 52004, f"Unexpected SWMM engine version: {version}"
print(f"SWMM native engine verified: {version}")

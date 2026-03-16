# Updated tideconfig.py

# Existing constants for backward compatibility
SETTLE_DRIFT_MIN = ...  # existing value
SETTLE_DRIFT_MAX = ...  # existing value
HAUL_DELAY_MIN = ...  # existing value
HAUL_DELAY_MAX = ...  # existing value
RETRY_DELAY_MIN = ...  # existing value
RETRY_DELAY_MAX = ...  # existing value

# Adjustments according to the request
# Wider SHORE_HUE range
SHORE_HUE_MIN = 10  # Adjusted from 10 to 15
SHORE_HUE_MAX = 15

# Slightly lower saturation/value thresholds
SATURATION_THRESHOLD = ...  # existing value (lower slightly)
VALUE_THRESHOLD = ...  # existing value (lower slightly)

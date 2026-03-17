class TideConfig:
    # Existing attributes restored
    # ... [other attributes and methods] ...

    # New optional timing ranges
    SETTLE_DRIFT_MIN = 1.2
    SETTLE_DRIFT_MAX = 1.9
    HAUL_DELAY_MIN = 0.35
    HAUL_DELAY_MAX = 0.8
    RETRY_DELAY_MIN = 0.6
    RETRY_DELAY_MAX = 1.4

    # Adjusted Hue and Saturation/Value
    SHORE_HUE_HIGH_1 = (10, 255, 255)
    SHORE_HUE_HIGH_2 = (15, 255, 255)
    SHORE_HUE_LOW_1 = (0, 90, 60)
    SHORE_HUE_LOW_2 = (165, 90, 60)

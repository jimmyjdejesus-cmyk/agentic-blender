"""
Langmuir Systems Machine Configuration Profiles for FireControl.
Supports:
- CrossFire (Standard, PRO, XR) Plasma CNC
- MR-1 CNC Gantry Mill
"""

MACHINE_PROFILES = {
    "crossfire_pro": {
        "name": "Langmuir CrossFire PRO Plasma",
        "type": "plasma",
        "units": "G20",  # G20 = Inches, G21 = Millimeters
        "unit_name": "inch",
        "work_area": {"x": 33.3, "y": 48.0, "z": 3.0},  # inches
        "max_feed_rate": 300.0,  # IPM
        "rapid_feed_rate": 300.0,
        "safe_z": 1.0,  # Safe clearance height above material
        "ihs_enabled": True,  # Initial Height Sensing (Ohmic / switch probe)
        "ihs_springback": 0.02,  # Switch springback compensation (in)
        "ihs_feed_rate": 60.0,  # Probe feed rate (IPM)
        "thc_enabled": True,  # Torch Height Control (H1 to enable, H0 to disable)
        "default_material": "14_gauge_mild_steel",
        "material_presets": {
            "16_gauge_mild_steel": {
                "pierce_height": 0.15,
                "pierce_delay": 0.5,  # seconds
                "cut_height": 0.06,
                "cut_feed_rate": 180.0,
                "amperage": 45,
            },
            "14_gauge_mild_steel": {
                "pierce_height": 0.15,
                "pierce_delay": 0.6,
                "cut_height": 0.06,
                "cut_feed_rate": 150.0,
                "amperage": 45,
            },
            "11_gauge_mild_steel": {
                "pierce_height": 0.15,
                "pierce_delay": 0.7,
                "cut_height": 0.06,
                "cut_feed_rate": 110.0,
                "amperage": 45,
            },
            "3_16_inch_mild_steel": {
                "pierce_height": 0.16,
                "pierce_delay": 0.9,
                "cut_height": 0.06,
                "cut_feed_rate": 75.0,
                "amperage": 45,
            },
            "1_4_inch_mild_steel": {
                "pierce_height": 0.18,
                "pierce_delay": 1.2,
                "cut_height": 0.06,
                "cut_feed_rate": 48.0,
                "amperage": 45,
            },
        },
    },
    "crossfire_xr": {
        "name": "Langmuir CrossFire XR Plasma",
        "type": "plasma",
        "units": "G20",
        "unit_name": "inch",
        "work_area": {"x": 48.0, "y": 96.0, "z": 3.0},
        "max_feed_rate": 400.0,
        "rapid_feed_rate": 400.0,
        "safe_z": 1.0,
        "ihs_enabled": True,
        "ihs_springback": 0.02,
        "ihs_feed_rate": 60.0,
        "thc_enabled": True,
        "default_material": "14_gauge_mild_steel",
        "material_presets": {},
    },
    "mr1_mill": {
        "name": "Langmuir MR-1 CNC Gantry Mill",
        "type": "milling",
        "units": "G20",
        "unit_name": "inch",
        "work_area": {"x": 20.8, "y": 21.8, "z": 6.5},
        "max_feed_rate": 100.0,
        "rapid_feed_rate": 100.0,
        "safe_z": 0.5,
        "spindle_control": True,
        "coolant_control": True,  # M8 / M9
    },
}

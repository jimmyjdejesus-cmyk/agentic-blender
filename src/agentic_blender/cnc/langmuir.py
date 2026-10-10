"""
Langmuir Systems CNC Machine Specs, Controllers, and Cut Charts.
Supports:
- Langmuir CrossFire (Standard, PRO, XR) Plasma CNC
- Langmuir MR-1 CNC Gantry Mill
"""

MACHINE_PROFILES = {
    "crossfire_pro": {
        "name": "Langmuir CrossFire PRO Plasma",
        "controller": "FireControl",
        "type": "plasma",
        "units": "G20",  # Inches
        "unit_name": "inch",
        "work_area": {"x": 33.3, "y": 48.0, "z": 3.0},  # Inches
        "max_feed_rate": 300.0,
        "rapid_feed_rate": 300.0,
        "safe_z": 1.0,
        "ihs_enabled": True,  # Initial Height Sensing (probe contact)
        "ihs_springback": 0.02,
        "ihs_feed_rate": 60.0,
        "thc_enabled": True,  # Torch Height Control
        "materials": {
            "18_gauge_mild_steel": {
                "amperage": 45,
                "pierce_height": 0.15,
                "pierce_delay": 0.4,
                "cut_height": 0.06,
                "cut_feed_rate": 200.0,
                "kerf_width": 0.040,
            },
            "16_gauge_mild_steel": {
                "amperage": 45,
                "pierce_height": 0.15,
                "pierce_delay": 0.5,
                "cut_height": 0.06,
                "cut_feed_rate": 180.0,
                "kerf_width": 0.045,
            },
            "14_gauge_mild_steel": {
                "amperage": 45,
                "pierce_height": 0.15,
                "pierce_delay": 0.6,
                "cut_height": 0.06,
                "cut_feed_rate": 150.0,
                "kerf_width": 0.050,
            },
            "11_gauge_mild_steel": {
                "amperage": 45,
                "pierce_height": 0.15,
                "pierce_delay": 0.7,
                "cut_height": 0.06,
                "cut_feed_rate": 110.0,
                "kerf_width": 0.055,
            },
            "10_gauge_mild_steel": {
                "amperage": 45,
                "pierce_height": 0.15,
                "pierce_delay": 0.8,
                "cut_height": 0.06,
                "cut_feed_rate": 95.0,
                "kerf_width": 0.058,
            },
            "3_16_inch_mild_steel": {
                "amperage": 45,
                "pierce_height": 0.16,
                "pierce_delay": 0.9,
                "cut_height": 0.06,
                "cut_feed_rate": 75.0,
                "kerf_width": 0.060,
            },
            "1_4_inch_mild_steel": {
                "amperage": 45,
                "pierce_height": 0.18,
                "pierce_delay": 1.2,
                "cut_height": 0.06,
                "cut_feed_rate": 48.0,
                "kerf_width": 0.065,
            },
            "3_8_inch_mild_steel": {
                "amperage": 45,
                "pierce_height": 0.20,
                "pierce_delay": 1.6,
                "cut_height": 0.06,
                "cut_feed_rate": 32.0,
                "kerf_width": 0.075,
            },
            "1_8_inch_aluminum": {
                "amperage": 45,
                "pierce_height": 0.15,
                "pierce_delay": 0.7,
                "cut_height": 0.06,
                "cut_feed_rate": 130.0,
                "kerf_width": 0.055,
            },
            "3_16_inch_aluminum": {
                "amperage": 45,
                "pierce_height": 0.16,
                "pierce_delay": 0.9,
                "cut_height": 0.06,
                "cut_feed_rate": 90.0,
                "kerf_width": 0.060,
            },
            "1_4_inch_aluminum": {
                "amperage": 45,
                "pierce_height": 0.18,
                "pierce_delay": 1.2,
                "cut_height": 0.06,
                "cut_feed_rate": 55.0,
                "kerf_width": 0.065,
            },
            "16_gauge_stainless": {
                "amperage": 45,
                "pierce_height": 0.15,
                "pierce_delay": 0.5,
                "cut_height": 0.06,
                "cut_feed_rate": 160.0,
                "kerf_width": 0.045,
            },
            "14_gauge_stainless": {
                "amperage": 45,
                "pierce_height": 0.15,
                "pierce_delay": 0.6,
                "cut_height": 0.06,
                "cut_feed_rate": 140.0,
                "kerf_width": 0.050,
            },
            "11_gauge_stainless": {
                "amperage": 45,
                "pierce_height": 0.15,
                "pierce_delay": 0.7,
                "cut_height": 0.06,
                "cut_feed_rate": 100.0,
                "kerf_width": 0.055,
            },
        },
    },
    "crossfire_xr": {
        "name": "Langmuir CrossFire XR Plasma",
        "controller": "FireControl",
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
        "materials": {},
    },
    "mr1_mill": {
        "name": "Langmuir MR-1 CNC Gantry Mill",
        "controller": "FireControl",
        "type": "milling",
        "units": "G20",
        "unit_name": "inch",
        "work_area": {"x": 20.8, "y": 21.8, "z": 6.5},
        "max_feed_rate": 100.0,
        "rapid_feed_rate": 100.0,
        "safe_z": 0.5,
        "spindle_control": True,
        "coolant_control": True,
        "materials": {
            "aluminum_6061": {
                "roughing_feed": 45.0,
                "finishing_feed": 30.0,
                "spindle_rpm": 6500,
                "plunge_rate": 15.0,
            },
            "mild_steel_1018": {
                "roughing_feed": 22.0,
                "finishing_feed": 16.0,
                "spindle_rpm": 3500,
                "plunge_rate": 8.0,
            },
        },
    },
}

def get_machine_profile(name="crossfire_pro"):
    """Fetch machine configuration with fallback to CrossFire PRO."""
    return MACHINE_PROFILES.get(name, MACHINE_PROFILES["crossfire_pro"])

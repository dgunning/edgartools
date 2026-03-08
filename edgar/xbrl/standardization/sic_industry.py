"""
SIC code to Fama-French 48 industry classification.

Maps 4-digit SIC codes to the 48 industry codes used by the
Fama-French industry classification system. These codes match the
industry_overrides keys in gaap_mappings.json.

Source: Kenneth French's Data Library
https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_48_ind_port.html
"""

from functools import lru_cache
from typing import Optional


# Each entry: (start_sic, end_sic, ff48_code)
# Sorted by SIC range for binary search
_FF48_SIC_RANGES = [
    # 1 Agric - Agriculture
    (100, 299, "Agric"), (700, 799, "Agric"), (910, 919, "Agric"),
    (2048, 2048, "Agric"),
    # 2 Food - Food Products
    (2000, 2046, "Food"), (2050, 2063, "Food"), (2070, 2079, "Food"),
    (2090, 2092, "Food"), (2095, 2095, "Food"), (2098, 2099, "Food"),
    # 3 Soda - Candy & Soda
    (2064, 2068, "Soda"), (2086, 2086, "Soda"), (2087, 2087, "Soda"),
    (2096, 2097, "Soda"),
    # 4 Beer - Beer & Liquor
    (2080, 2085, "Beer"),
    # 5 Smoke - Tobacco Products
    (2100, 2199, "Smoke"),
    # 6 Toys - Recreation
    (920, 999, "Toys"), (3650, 3651, "Toys"), (3732, 3732, "Toys"),
    (3930, 3931, "Toys"), (3940, 3949, "Toys"),
    # 7 Fun - Entertainment
    (7800, 7833, "Fun"), (7840, 7841, "Fun"), (7900, 7999, "Fun"),
    # 8 Books - Printing and Publishing
    (2700, 2749, "Books"), (2770, 2771, "Books"), (2780, 2799, "Books"),
    # 9 Hshld - Consumer Goods
    (2047, 2047, "Hshld"), (2391, 2392, "Hshld"), (2510, 2519, "Hshld"),
    (2590, 2599, "Hshld"), (2840, 2844, "Hshld"), (3160, 3161, "Hshld"),
    (3170, 3172, "Hshld"), (3190, 3199, "Hshld"), (3229, 3231, "Hshld"),
    (3260, 3260, "Hshld"), (3262, 3263, "Hshld"), (3269, 3269, "Hshld"),
    (3630, 3639, "Hshld"), (3750, 3751, "Hshld"), (3800, 3800, "Hshld"),
    (3860, 3861, "Hshld"), (3870, 3873, "Hshld"), (3910, 3911, "Hshld"),
    (3914, 3914, "Hshld"), (3915, 3915, "Hshld"), (3960, 3962, "Hshld"),
    (3991, 3991, "Hshld"), (3995, 3995, "Hshld"),
    # 10 Clths - Apparel
    (2300, 2390, "Clths"), (3020, 3021, "Clths"), (3100, 3111, "Clths"),
    (3130, 3131, "Clths"), (3140, 3151, "Clths"), (3963, 3965, "Clths"),
    # 11 Hlth - Healthcare
    (8000, 8099, "Hlth"),
    # 12 MedEq - Medical Equipment
    (3693, 3693, "MedEq"), (3840, 3851, "MedEq"),
    # 13 Drugs - Pharmaceutical Products
    (2830, 2836, "Drugs"),
    # 14 Chems - Chemicals
    (2800, 2829, "Chems"), (2850, 2899, "Chems"),
    # 15 Rubbr - Rubber and Plastic Products
    (3031, 3031, "Rubbr"), (3041, 3041, "Rubbr"), (3050, 3053, "Rubbr"),
    (3060, 3099, "Rubbr"),
    # 16 Txtls - Textiles
    (2200, 2284, "Txtls"), (2290, 2295, "Txtls"), (2297, 2299, "Txtls"),
    (2393, 2395, "Txtls"), (2397, 2399, "Txtls"),
    # 17 BldMt - Construction Materials
    (800, 899, "BldMt"), (2400, 2439, "BldMt"), (2450, 2459, "BldMt"),
    (2490, 2499, "BldMt"), (2660, 2661, "BldMt"), (2950, 2952, "BldMt"),
    (3200, 3200, "BldMt"), (3210, 3211, "BldMt"), (3240, 3241, "BldMt"),
    (3250, 3259, "BldMt"), (3261, 3261, "BldMt"), (3264, 3264, "BldMt"),
    (3270, 3275, "BldMt"), (3280, 3281, "BldMt"), (3290, 3293, "BldMt"),
    (3295, 3299, "BldMt"), (3420, 3433, "BldMt"), (3440, 3442, "BldMt"),
    (3446, 3452, "BldMt"), (3490, 3499, "BldMt"), (3996, 3996, "BldMt"),
    # 18 Cnstr - Construction
    (1500, 1511, "Cnstr"), (1520, 1549, "Cnstr"), (1600, 1699, "Cnstr"),
    (1700, 1799, "Cnstr"),
    # 19 Steel - Steel Works Etc
    (3300, 3317, "Steel"), (3320, 3325, "Steel"), (3330, 3341, "Steel"),
    (3350, 3357, "Steel"), (3360, 3379, "Steel"), (3380, 3399, "Steel"),
    # 20 FabPr - Fabricated Products
    (3400, 3400, "FabPr"), (3443, 3444, "FabPr"), (3460, 3479, "FabPr"),
    # 21 Mach - Machinery
    (3510, 3536, "Mach"), (3538, 3599, "Mach"),
    # 22 ElcEq - Electrical Equipment
    (3600, 3600, "ElcEq"), (3610, 3613, "ElcEq"), (3620, 3629, "ElcEq"),
    (3640, 3644, "ElcEq"), (3645, 3645, "ElcEq"), (3646, 3649, "ElcEq"),
    (3660, 3660, "ElcEq"), (3690, 3692, "ElcEq"), (3699, 3699, "ElcEq"),
    # 23 Autos - Automobiles and Trucks
    (2296, 2296, "Autos"), (2396, 2396, "Autos"), (3010, 3011, "Autos"),
    (3537, 3537, "Autos"), (3647, 3647, "Autos"), (3694, 3694, "Autos"),
    (3700, 3700, "Autos"), (3710, 3711, "Autos"), (3713, 3713, "Autos"),
    (3714, 3714, "Autos"), (3715, 3715, "Autos"), (3716, 3716, "Autos"),
    (3792, 3792, "Autos"), (3790, 3791, "Autos"), (3799, 3799, "Autos"),
    # 24 Aero - Aircraft
    (3720, 3729, "Aero"),
    # 25 Ships - Shipbuilding, Railroad Equipment
    (3730, 3731, "Ships"), (3740, 3743, "Ships"),
    # 26 Guns - Defense
    (3760, 3769, "Guns"), (3795, 3795, "Guns"), (3480, 3489, "Guns"),
    # 27 Gold - Precious Metals
    (1040, 1049, "Gold"),
    # 28 Mines - Non-Metallic and Industrial Metal Mining
    (1000, 1039, "Mines"), (1050, 1099, "Mines"), (1200, 1299, "Mines"),
    (1400, 1499, "Mines"),
    # 29 Coal - Coal
    (1200, 1299, "Coal"),
    # 30 Oil - Petroleum and Natural Gas
    (1300, 1300, "Oil"), (1310, 1339, "Oil"), (1370, 1382, "Oil"),
    (1389, 1389, "Oil"), (2900, 2912, "Oil"), (2990, 2999, "Oil"),
    # 31 Util - Utilities
    (4900, 4900, "Util"), (4910, 4911, "Util"), (4920, 4925, "Util"),
    (4930, 4932, "Util"), (4939, 4942, "Util"),
    # 32 Telcm - Communication
    (4800, 4800, "Telcm"), (4810, 4813, "Telcm"), (4820, 4822, "Telcm"),
    (4830, 4841, "Telcm"), (4890, 4899, "Telcm"),
    # 33 PerSv - Personal Services
    (7020, 7021, "PerSv"), (7030, 7033, "PerSv"), (7200, 7212, "PerSv"),
    (7214, 7214, "PerSv"), (7215, 7216, "PerSv"), (7217, 7217, "PerSv"),
    (7219, 7219, "PerSv"), (7220, 7221, "PerSv"), (7230, 7231, "PerSv"),
    (7240, 7241, "PerSv"), (7250, 7251, "PerSv"), (7260, 7269, "PerSv"),
    (7270, 7290, "PerSv"), (7291, 7291, "PerSv"), (7292, 7299, "PerSv"),
    (7395, 7395, "PerSv"), (7500, 7500, "PerSv"), (7520, 7549, "PerSv"),
    (7600, 7600, "PerSv"), (7620, 7620, "PerSv"), (7622, 7622, "PerSv"),
    (7623, 7623, "PerSv"), (7629, 7631, "PerSv"), (7640, 7641, "PerSv"),
    (7690, 7699, "PerSv"), (8100, 8199, "PerSv"), (8200, 8299, "PerSv"),
    (8300, 8399, "PerSv"), (8400, 8499, "PerSv"), (8600, 8699, "PerSv"),
    (8800, 8899, "PerSv"),
    # 34 BusSv - Business Services
    (2750, 2759, "BusSv"), (3993, 3993, "BusSv"), (7300, 7300, "BusSv"),
    (7310, 7342, "BusSv"), (7349, 7353, "BusSv"), (7359, 7372, "BusSv"),
    (7374, 7374, "BusSv"), (7376, 7376, "BusSv"), (7377, 7377, "BusSv"),
    (7378, 7378, "BusSv"), (7379, 7379, "BusSv"), (7380, 7380, "BusSv"),
    (7381, 7382, "BusSv"), (7383, 7383, "BusSv"), (7384, 7384, "BusSv"),
    (7385, 7385, "BusSv"), (7389, 7390, "BusSv"), (7391, 7391, "BusSv"),
    (7392, 7392, "BusSv"), (7393, 7393, "BusSv"), (7394, 7394, "BusSv"),
    (7396, 7397, "BusSv"), (7399, 7399, "BusSv"), (7519, 7519, "BusSv"),
    (8700, 8700, "BusSv"), (8710, 8713, "BusSv"), (8720, 8721, "BusSv"),
    (8730, 8734, "BusSv"), (8740, 8748, "BusSv"), (8900, 8910, "BusSv"),
    (8911, 8911, "BusSv"), (8920, 8999, "BusSv"),
    # 35 Comps - Computers
    (3570, 3579, "Comps"), (3680, 3689, "Comps"), (3695, 3695, "Comps"),
    # 36 Chips - Electronic Equipment
    (3622, 3622, "Chips"), (3661, 3666, "Chips"), (3669, 3679, "Chips"),
    (3810, 3810, "Chips"), (3812, 3812, "Chips"),
    # 37 LabEq - Measuring and Control Equipment
    (3811, 3811, "LabEq"), (3820, 3827, "LabEq"), (3829, 3839, "LabEq"),
    # 38 Paper - Business Supplies
    (2520, 2549, "Paper"), (2600, 2639, "Paper"), (2670, 2699, "Paper"),
    (2760, 2761, "Paper"), (3950, 3955, "Paper"),
    # 39 Boxes - Shipping Containers
    (2440, 2449, "Boxes"), (2640, 2659, "Boxes"), (3220, 3221, "Boxes"),
    (3410, 3412, "Boxes"),
    # 40 Trans - Transportation
    (4000, 4013, "Trans"), (4040, 4049, "Trans"), (4100, 4100, "Trans"),
    (4110, 4121, "Trans"), (4130, 4131, "Trans"), (4140, 4142, "Trans"),
    (4150, 4151, "Trans"), (4170, 4173, "Trans"), (4190, 4200, "Trans"),
    (4210, 4231, "Trans"), (4240, 4249, "Trans"), (4400, 4700, "Trans"),
    (4710, 4712, "Trans"), (4720, 4749, "Trans"), (4780, 4780, "Trans"),
    (4782, 4785, "Trans"), (4789, 4789, "Trans"),
    # 41 Whlsl - Wholesale
    (5000, 5000, "Whlsl"), (5010, 5015, "Whlsl"), (5020, 5023, "Whlsl"),
    (5030, 5060, "Whlsl"), (5063, 5065, "Whlsl"), (5070, 5078, "Whlsl"),
    (5080, 5088, "Whlsl"), (5090, 5094, "Whlsl"), (5099, 5100, "Whlsl"),
    (5110, 5113, "Whlsl"), (5120, 5122, "Whlsl"), (5130, 5172, "Whlsl"),
    (5180, 5182, "Whlsl"), (5190, 5199, "Whlsl"),
    # 42 Rtail - Retail
    (5200, 5200, "Rtail"), (5210, 5231, "Rtail"), (5250, 5251, "Rtail"),
    (5260, 5261, "Rtail"), (5270, 5271, "Rtail"), (5300, 5300, "Rtail"),
    (5310, 5311, "Rtail"), (5320, 5320, "Rtail"), (5330, 5331, "Rtail"),
    (5334, 5334, "Rtail"), (5340, 5349, "Rtail"), (5390, 5400, "Rtail"),
    (5410, 5412, "Rtail"), (5420, 5469, "Rtail"), (5490, 5500, "Rtail"),
    (5510, 5579, "Rtail"), (5590, 5700, "Rtail"), (5710, 5722, "Rtail"),
    (5730, 5736, "Rtail"), (5750, 5799, "Rtail"), (5900, 5900, "Rtail"),
    (5910, 5912, "Rtail"), (5920, 5932, "Rtail"), (5940, 5990, "Rtail"),
    (5992, 5995, "Rtail"), (5999, 5999, "Rtail"),
    # 43 Meals - Restaurants, Hotels, Motels
    (5800, 5813, "Meals"), (5890, 5890, "Meals"), (7000, 7000, "Meals"),
    (7010, 7019, "Meals"), (7040, 7049, "Meals"), (7213, 7213, "Meals"),
    # 44 Banks - Banking
    (6000, 6000, "Banks"), (6010, 6022, "Banks"), (6025, 6025, "Banks"),
    (6026, 6026, "Banks"), (6028, 6029, "Banks"), (6030, 6036, "Banks"),
    (6040, 6062, "Banks"), (6080, 6082, "Banks"), (6090, 6099, "Banks"),
    (6100, 6100, "Banks"), (6110, 6113, "Banks"), (6120, 6129, "Banks"),
    (6130, 6139, "Banks"), (6140, 6163, "Banks"), (6170, 6199, "Banks"),
    # 45 Insur - Insurance
    (6300, 6300, "Insur"), (6310, 6331, "Insur"), (6350, 6351, "Insur"),
    (6360, 6361, "Insur"), (6370, 6379, "Insur"), (6390, 6399, "Insur"),
    (6400, 6411, "Insur"),
    # 46 RlEst - Real Estate
    (6500, 6500, "RlEst"), (6510, 6510, "RlEst"), (6512, 6515, "RlEst"),
    (6517, 6519, "RlEst"), (6520, 6532, "RlEst"), (6550, 6553, "RlEst"),
    (6590, 6599, "RlEst"), (6610, 6611, "RlEst"),
    # 47 Fin - Trading
    (6200, 6200, "Fin"), (6210, 6211, "Fin"), (6220, 6221, "Fin"),
    (6230, 6231, "Fin"), (6240, 6241, "Fin"), (6250, 6252, "Fin"),
    (6260, 6261, "Fin"), (6280, 6282, "Fin"), (6290, 6299, "Fin"),
    (6700, 6700, "Fin"), (6710, 6726, "Fin"), (6730, 6733, "Fin"),
    (6740, 6779, "Fin"), (6790, 6795, "Fin"), (6798, 6798, "Fin"),
    (6799, 6799, "Fin"),
    # 48 Other - Almost Nothing
    (4950, 4959, "Other"), (4960, 4961, "Other"), (4970, 4971, "Other"),
    (4990, 4991, "Other"),
]


@lru_cache(maxsize=256)
def sic_to_fama_french(sic_code: int) -> Optional[str]:
    """
    Map a 4-digit SIC code to its Fama-French 48 industry code.

    Args:
        sic_code: Numeric SIC code (e.g., 3711 for Motor Vehicles)

    Returns:
        FF48 industry code (e.g., "Autos") or None if not classified
    """
    for start, end, code in _FF48_SIC_RANGES:
        if start <= sic_code <= end:
            return code
    return None


def sic_str_to_fama_french(sic_code: str) -> Optional[str]:
    """
    Map a SIC code string to its Fama-French 48 industry code.

    Args:
        sic_code: SIC code as string (e.g., "3711")

    Returns:
        FF48 industry code (e.g., "Autos") or None if not classified
    """
    if not sic_code:
        return None
    try:
        return sic_to_fama_french(int(sic_code))
    except (ValueError, TypeError):
        return None

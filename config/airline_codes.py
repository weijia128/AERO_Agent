"""
航空公司代码映射配置

IATA (2字母) -> ICAO (3字母) 代码映射
用于将前端输入的航班号（如"南航1234"、"CZ1234"）转换为ICAO格式（如"CSN1234"）
"""

# 标准库
import re

# IATA到ICAO代码映射
IATA_TO_ICAO = {
    # 三大航
    "CZ": "CSN",  # 中国南方航空
    "MU": "CES",  # 中国东方航空
    "CA": "CCA",  # 中国国际航空

    # 其他主要航空公司
    "HU": "CHH",  # 海南航空
    "MF": "CXA",  # 厦门航空
    "3U": "CSC",  # 四川航空
    "ZH": "CSZ",  # 深圳航空
    "9C": "CQH",  # 春秋航空
    "SC": "CDG",  # 山东航空
    "HO": "DKH",  # 吉祥航空
    "GS": "GCR",  # 天津航空
    "GJ": "CDC",  # 长龙航空
    "DR": "RLH",  # 瑞丽航空
    "GX": "CBJ",  # 北部湾航空
    "KN": "CUA",  # 中国联合航空
    "EU": "UEA",  # 成都航空
    "JD": "CBJ",  # 首都航空
    "NS": "HBH",  # 河北航空
    "GY": "CGZ",  # 多彩贵州航空
    "AQ": "JYH",  # 九元航空
    "TV": "TBA",  # 西藏航空
    "FU": "FZA",  # 福州航空
    "KY": "KNA",  # 昆明航空
    "QW": "QDA",  # 青岛航空
    "UQ": "CUH",  # 乌鲁木齐航空
    "9H": "CGN",  # 长安航空
    "G5": "CHA",  # 华夏航空
    "Y8": "YZR",  # 扬子江快运

    # 货运航空
    "CK": "CKK",  # 中国货运航空
}

# 航空公司中文名称映射（用于解析"南航1234"这类输入）
AIRLINE_CHINESE_TO_IATA = {
    "南航": "CZ",
    "东航": "MU",
    "国航": "CA",
    "海航": "HU",
    "厦航": "MF",
    "川航": "3U",
    "深航": "ZH",
    "春秋": "9C",
    "山航": "SC",
    "吉祥": "HO",
    "天津航": "GS",
    "天航": "GS",
    "长龙": "GJ",
    "瑞丽": "DR",
    "北部湾": "GX",
    "联航": "KN",
    "成都航": "EU",
    "首都航": "JD",
    "河北航": "NS",
    "贵州航": "GY",
    "九元": "AQ",
    "西藏航": "TV",
    "福州航": "FU",
    "昆明航": "KY",
    "青岛航": "QW",
    "乌鲁木齐航": "UQ",
    "长安": "9H",
    "华夏": "G5",
}

# IATA到中文简称（用于对话显示）
IATA_TO_CHINESE_SHORT = {}
for _cn_name, _iata_code in AIRLINE_CHINESE_TO_IATA.items():
    # 避免同一IATA代码被多次覆盖，保留首个映射
    if _iata_code not in IATA_TO_CHINESE_SHORT:
        IATA_TO_CHINESE_SHORT[_iata_code] = _cn_name

# 反向映射：ICAO到IATA（用于显示）
ICAO_TO_IATA = {v: k for k, v in IATA_TO_ICAO.items()}

# 航空公司全称（用于显示）
AIRLINE_FULL_NAMES = {
    "CSN": "中国南方航空",
    "CES": "中国东方航空",
    "CCA": "中国国际航空",
    "CHH": "海南航空",
    "CXA": "厦门航空",
    "CSC": "四川航空",
    "CSZ": "深圳航空",
    "CQH": "春秋航空",
    "CDG": "山东航空",
    "DKH": "吉祥航空",
    "GCR": "天津航空",
    "CDC": "长龙航空",
    "RLH": "瑞丽航空",
    "CBJ": "北部湾航空/首都航空",
    "CUA": "中国联合航空",
    "UEA": "成都航空",
    "HBH": "河北航空",
    "CGZ": "多彩贵州航空",
    "JYH": "九元航空",
    "TBA": "西藏航空",
    "FZA": "福州航空",
    "KNA": "昆明航空",
    "QDA": "青岛航空",
    "CUH": "乌鲁木齐航空",
    "CGN": "长安航空",
    "CHA": "华夏航空",
    "YZR": "扬子江快运",
    "CKK": "中国货运航空",
}


def normalize_flight_number(flight_input: str) -> str:
    """
    将各种格式的航班号转换为ICAO格式

    支持格式：
    - "南航1234" -> "CSN1234"
    - "CZ1234" -> "CSN1234"
    - "CSN1234" -> "CSN1234" (已经是ICAO格式)

    Args:
        flight_input: 航班号输入（可能包含中文、IATA或ICAO代码）

    Returns:
        ICAO格式的航班号，如果无法识别则返回原输入的大写形式
    """
    if not flight_input:
        return ""

    flight_input = flight_input.strip().upper()

    # 1. 提取中文航空公司名称和数字部分（如"南航1234"）
    for chinese_name, iata_code in AIRLINE_CHINESE_TO_IATA.items():
        if flight_input.startswith(chinese_name):
            # 提取数字部分
            number_part = flight_input[len(chinese_name):].strip()
            if number_part.isdigit():
                icao_code = IATA_TO_ICAO.get(iata_code, iata_code)
                return f"{icao_code}{number_part}"

    # 2. 优先尝试2字母IATA代码（如 3U3349 -> CSC3349）
    if len(flight_input) >= 3:
        match_2char = re.match(r"^([A-Z0-9]{2})(\d{3,4})$", flight_input)
        if match_2char:
            prefix, number_part = match_2char.group(1), match_2char.group(2)
            if prefix in IATA_TO_ICAO:
                icao_code = IATA_TO_ICAO[prefix]
                return f"{icao_code}{number_part}"

    # 3. 尝试3字母ICAO代码（如 CSC3349）
    if len(flight_input) >= 4:
        match_3char = re.match(r"^([A-Z]{3})(\d{3,4})$", flight_input)
        if match_3char:
            prefix, number_part = match_3char.group(1), match_3char.group(2)
            # 已经是ICAO代码，直接返回
            if prefix in ICAO_TO_IATA or prefix in AIRLINE_FULL_NAMES:
                return flight_input

    # 3. 无法识别，返回原输入的大写形式
    return flight_input


def get_airline_name(icao_code: str) -> str:
    """
    获取航空公司全称

    Args:
        icao_code: ICAO代码（3字母）

    Returns:
        航空公司全称，如果未找到则返回代码本身
    """
    # 提取航班号中的航空公司代码（前3个字母）
    airline_code = icao_code[:3].upper()
    return AIRLINE_FULL_NAMES.get(airline_code, airline_code)


def format_callsign_display(flight_no: str) -> str:
    """
    将航班号格式化为中文简称呼号（用于对话显示）

    支持格式：
    - "南航1234" -> "南航1234"
    - "CZ1234" -> "南航1234"
    - "CSN1234" -> "南航1234"
    - "3U1234" -> "川航1234"
    """
    if not flight_no:
        return ""

    raw = flight_no.strip()
    # 已包含中文时，直接返回原始格式
    if any('\u4e00' <= ch <= '\u9fff' for ch in raw):
        return raw

    upper = raw.upper()
    match = re.match(r"^([A-Z0-9]{2})(\d+)$", upper)
    if not match:
        match = re.match(r"^([A-Z0-9]{3})(\d+)$", upper)
    if not match:
        return raw

    prefix, number = match.group(1), match.group(2)
    if len(prefix) == 3 and prefix in ICAO_TO_IATA:
        iata_code = ICAO_TO_IATA[prefix]
    else:
        iata_code = prefix

    short_name = IATA_TO_CHINESE_SHORT.get(iata_code)
    if not short_name:
        return raw

    return f"{short_name}{number}"

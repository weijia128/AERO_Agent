"""
测试航班信息查询功能
"""
from tools.information.get_aircraft_info import GetAircraftInfoTool
from config.airline_codes import normalize_flight_number


def test_flight_number_normalization():
    """测试航班号格式转换"""
    print("=" * 60)
    print("测试航班号格式转换")
    print("=" * 60)

    test_cases = [
        "南航1234",
        "CZ1234",
        "CSN1234",
        "东航2367",
        "MU2367",
        "CES2367",
        "国航8523",
        "CA8523",
        "CCA8523",
    ]

    for test_input in test_cases:
        result = normalize_flight_number(test_input)
        print(f"{test_input:15s} -> {result}")

    print()


def test_flight_info_query():
    """测试航班信息查询"""
    print("=" * 60)
    print("测试航班信息查询（使用真实数据）")
    print("=" * 60)

    tool = GetAircraftInfoTool()

    # 测试用例：使用data/Log_1.txt中实际存在的航班
    test_cases = [
        {"flight_no": "CES2367"},  # ICAO格式
        {"flight_no": "MU2367"},   # IATA格式（假设MU是东航）
        {"flight_no": "东航2367"},  # 中文格式
        {"flight_no": "CCA8523"},  # 国航
        {"flight_no": "CA8523"},   # 国航IATA
        {"flight_no": "CSN6938"},  # 南航
        {"flight_no": "CZ6938"},   # 南航IATA
    ]

    for i, inputs in enumerate(test_cases, 1):
        print(f"\n测试 {i}: 查询航班 '{inputs['flight_no']}'")
        print("-" * 60)
        result = tool.execute({}, inputs)
        print(result.get("observation", "无结果"))

        # 如果有incident信息，也打印出来
        if "incident" in result:
            print("\n结构化数据:")
            for key, value in result["incident"].items():
                print(f"  {key}: {value}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_flight_number_normalization()
    print("\n")
    test_flight_info_query()

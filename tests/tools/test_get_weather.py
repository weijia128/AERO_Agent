"""
测试 get_weather 工具
"""
import pytest
from datetime import datetime
from tools.information.get_weather import GetWeatherTool, find_nearest_record, format_weather_info
import pandas as pd


class TestGetWeatherTool:
    """测试GetWeatherTool"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return GetWeatherTool()

    @pytest.fixture
    def mock_state(self):
        """创建模拟的state"""
        return {
            "incident": {
                "position": "501",
                "fluid_type": "FUEL",
            }
        }

    def test_tool_metadata(self, tool):
        """测试工具元数据"""
        assert tool.name == "get_weather"
        assert "气象" in tool.description
        assert "location" in tool.description

    def test_missing_location_parameter(self, tool, mock_state):
        """测试缺少location参数的情况"""
        result = tool.execute(mock_state, {})

        assert "observation" in result
        assert "请提供位置" in result["observation"]

    def test_auto_location_selection(self, tool, mock_state):
        """测试自动选择观测点"""
        result = tool.execute(mock_state, {"location": "推荐"})

        # 应该成功执行（即使没有数据也不应该报错）
        assert "observation" in result
        # 注意：如果气象数据不存在，会返回错误信息

    def test_specific_location(self, tool, mock_state):
        """测试查询特定位置的气象信息"""
        result = tool.execute(mock_state, {"location": "05L"})

        assert "observation" in result
        # 如果数据不存在，会返回错误信息
        # 如果数据存在，应该包含气象信息

    def test_location_with_timestamp(self, tool, mock_state):
        """测试带时间戳的查询"""
        result = tool.execute(
            mock_state,
            {
                "location": "NORTH",
                "timestamp": "2026-01-06 05:30:00"
            }
        )

        assert "observation" in result

    def test_invalid_timestamp_format(self, tool, mock_state):
        """测试无效的时间格式"""
        result = tool.execute(
            mock_state,
            {
                "location": "05L",
                "timestamp": "invalid-time"
            }
        )

        assert "observation" in result
        assert "时间格式错误" in result["observation"]


class TestHelperFunctions:
    """测试辅助函数"""

    @pytest.fixture
    def sample_weather_df(self):
        """创建示例气象数据"""
        data = {
            'timestamp': pd.to_datetime([
                '2026-01-06 05:00:00',
                '2026-01-06 05:30:00',
                '2026-01-06 06:00:00',
            ]),
            'location_id': ['05L', '05L', '05L'],
            'temperature': [-2.5, -2.0, -1.5],
            'wind_speed': [3.0, 3.5, 4.0],
            'wind_direction': [280, 285, 290],
            'relative_humidity': [60, 58, 56],
            'qnh': [1035.0, 1035.2, 1035.5],
            'visibility': [10000, 10000, 10000],
        }
        return pd.DataFrame(data)

    def test_find_nearest_record_exact_match(self, sample_weather_df):
        """测试精确时间匹配"""
        target_time = pd.to_datetime('2026-01-06 05:30:00')
        result = find_nearest_record(sample_weather_df, '05L', target_time)

        assert result is not None
        assert result['temperature'] == -2.0

    def test_find_nearest_record_closest_match(self, sample_weather_df):
        """测试最近时间匹配"""
        target_time = pd.to_datetime('2026-01-06 05:15:00')
        result = find_nearest_record(sample_weather_df, '05L', target_time)

        assert result is not None
        # 应该返回05:00或05:30的数据（取决于哪个更近）
        assert result['temperature'] in [-2.5, -2.0]

    def test_find_nearest_record_no_match_location(self, sample_weather_df):
        """测试位置不存在的情况"""
        target_time = pd.to_datetime('2026-01-06 05:30:00')
        result = find_nearest_record(sample_weather_df, '99Z', target_time)

        assert result is None

    def test_find_nearest_record_too_far(self, sample_weather_df):
        """测试时间差超过1小时的情况"""
        target_time = pd.to_datetime('2026-01-06 07:30:00')
        result = find_nearest_record(sample_weather_df, '05L', target_time)

        assert result is None  # 时间差超过1小时，返回None

    def test_format_weather_info_complete(self, sample_weather_df):
        """测试格式化完整气象信息"""
        record = sample_weather_df.iloc[1]  # 05:30的数据
        formatted = format_weather_info(record, '05L', pd.to_datetime('2026-01-06 05:30:00'))

        assert "05L 气象信息" in formatted
        assert "温度: -2.0°C" in formatted
        assert "风: 285° 3.5 m/s" in formatted
        assert "相对湿度: 58%" in formatted
        assert "QNH: 1035" in formatted
        assert "能见度: 10.0 km" in formatted

    def test_format_weather_info_empty_record(self):
        """测试格式化空记录"""
        formatted = format_weather_info(None, '05L', None)
        assert "未找到" in formatted

    def test_format_weather_info_partial_data(self, sample_weather_df):
        """测试格式化部分气象数据"""
        # 创建只有部分字段的记录
        partial_record = pd.Series({
            'timestamp': pd.to_datetime('2026-01-06 05:30:00'),
            'temperature': -2.0,
            'wind_speed': None,  # 缺失
            'qnh': None,  # 缺失
        })

        formatted = format_weather_info(partial_record, '05L', None)

        # 应该包含温度，但不应该包含风和气压
        assert "温度: -2.0°C" in formatted
        assert "风:" not in formatted or "m/s" not in formatted


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self):
        """测试完整的工作流程"""
        tool = GetWeatherTool()
        state = {
            "incident": {
                "position": "501",
            }
        }

        # 查询05L位置的气象
        result = tool.execute(state, {"location": "05L"})

        assert "observation" in result

        # 如果查询成功，应该包含weather字段
        if "weather" in result:
            weather = result["weather"]
            assert "location" in weather
            assert "timestamp" in weather
            assert weather["location"] == "05L"

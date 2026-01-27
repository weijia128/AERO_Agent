#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request


def http_get(url: str, headers: dict, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def http_post(url: str, payload: dict, headers: dict, timeout: float) -> tuple[int, bytes]:
    data = json.dumps(payload).encode("utf-8")
    merged_headers = dict(headers)
    merged_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=merged_headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def parse_json(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8"))


def print_fsm_states(fsm_states: list[dict]) -> None:
    if not fsm_states:
        print("  fsm_states: <empty>")
        return
    print("  fsm_states:")
    for item in fsm_states:
        state_id = item.get("id", "")
        name = item.get("name", "")
        order = item.get("order")
        order_part = f"(order {order})" if order is not None else ""
        line = f"  - {state_id} {name} {order_part}".strip()
        print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Test scenario detection and FSM list output.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--api-key", default="", help="Optional API key for X-API-Key header")
    parser.add_argument("--timeout", type=float, default=15.0, help="Request timeout (seconds)")
    parser.add_argument("--show-json", action="store_true", help="Print full JSON response")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    headers = {}
    if args.api_key:
        headers["X-API-Key"] = args.api_key

    # Health check
    try:
        status, body = http_get(f"{base_url}/health", headers, args.timeout)
        if status != 200:
            print(f"Health check failed: status={status} body={body!r}")
            return 1
    except urllib.error.URLError as exc:
        print(f"Health check failed: {exc}")
        return 1

    tests = [
        ("oil_spill", "CES2876在501机位漏油，燃油，发动机还在转，持续滴漏"),
        ("bird_strike", "MU5208 起飞后报告疑似鸟击，发动机受损"),
        ("fod", "跑道发现FOD，疑似金属碎片，仍在道面"),
    ]

    for label, message in tests:
        print(f"\n=== Test: {label}")
        payload = {
            "message": message,
            "scenario_type": "",
        }
        try:
            status, body = http_post(f"{base_url}/event/start", payload, headers, args.timeout)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            detail = raw.decode("utf-8", errors="ignore")
            print(f"Request failed: status={exc.code} body={detail}")
            continue
        except urllib.error.URLError as exc:
            print(f"Request failed: {exc}")
            continue

        data = parse_json(body)
        if args.show_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))

        scenario_type = data.get("scenario_type")
        incident = data.get("incident") or {}
        incident_scenario = incident.get("scenario_type")
        print(f"  detected scenario_type: {scenario_type or incident_scenario or '<empty>'}")
        print(f"  fsm_state: {data.get('fsm_state')}")
        print_fsm_states(data.get("fsm_states") or [])

    return 0


if __name__ == "__main__":
    sys.exit(main())

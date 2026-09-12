#!/usr/bin/env python3

import argparse
import json
import time
import yaml
import sys

from datetime import datetime
from typing import Dict, Any, Optional, List
from pysolarmanv5 import PySolarmanV5
from umodbus.exceptions import IllegalDataAddressError


class DeyeReader:
    def __init__(self, host: str, serial: int, port: int = 8899, registers_map_path: str = "none.yaml"):
        self.host = host
        self.serial = serial
        self.port = port
        self.registers_map_path = registers_map_path
        self.client: Optional[PySolarmanV5] = None
        self.registers: Dict[str, Dict[str, Any]] = {}
        self._load_registers_map()

    def _load_registers_map(self) -> None:
        try:
            with open("maps/" + self.registers_map_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.registers = config.get('registers', {})

            if not self.registers:
                raise ValueError("No registers found in map file")
        except FileNotFoundError:
            print(f"file not found: {self.registers_map_path}")
            exit(1)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {e}")

    def connect(self) -> bool:
        try:
            self.client = PySolarmanV5(
                address=self.host,
                serial=self.serial,
                port=self.port,
                mb_slave_id=1,
                verbose=False
            )

            return True

        except Exception as e:
            print(f"error connecting to inverter: {e}")
            return False

    def disconnect(self) -> None:
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass

    def _to_signed(self, value: int) -> int:
        if value > 32767:
            return value - 65536
        return value

    def _read_register(self, address: int, quantity: int = 1) -> Optional[List[int]]:
        if not self.client:
            return None

        try:
            result = self.client.read_holding_registers(
                register_addr=address,
                quantity=quantity
            )
            return result
        except (IllegalDataAddressError, Exception) as e:
            return None

    def _read_single_register(self, reg_config: Dict[str, Any]) -> Optional[float]:
        address = reg_config['address']
        scale = reg_config.get('scale', 1)
        offset = reg_config.get('offset', 0)
        reg_type = reg_config.get('type', 'U_WORD')

        result = self._read_register(address, 1)
        if result is None or len(result) == 0:
            return None

        value = result[0]

        if reg_type == 'S_WORD':
            value = self._to_signed(value)

        if offset != 0:
            value = value - offset

        if scale != 1:
            if scale < 1:
                return round(float(value * scale), 1)
            else:
                return value * scale

        return value

    def _read_dword_register(self, low_addr: int, high_addr: int, scale: float = 1.0) -> Optional[float]:
        low_result = self._read_register(low_addr, 1)
        high_result = self._read_register(high_addr, 1)

        if low_result is None or high_result is None:
            return None

        if len(low_result) == 0 or len(high_result) == 0:
            return None

        low = low_result[0]
        high = high_result[0]
        value = (high << 16) | low

        return round(float(value * scale), 1)

    def _read_serial_register(self, address: int) -> Optional[str]:
        data = self._read_register(address, 5)
        sn_bytes = bytearray()
        for reg in data:
            low_byte = reg & 0xFF
            high_byte = reg >> 8 & 0xFF

            sn_bytes.append(low_byte)
            sn_bytes.append(high_byte)

        return sn_bytes.decode('ascii', errors='ignore').strip()

    def read_all(self) -> Dict[str, Any]:
        if not self.client:
            print("not connected to inverter")
            return {}

        results = {
            'timestamp': datetime.now().isoformat(),
            'host': self.host,
            'data': {},
            'errors': []
        }

        for reg_key, reg_config in self.registers.items():
            address = reg_config['address']
            address_type = reg_config.get('type', '')
            name = reg_config['name']
            unit = reg_config.get('unit', '')
            low_addr = reg_config.get('address').get('low', 0) if type(address) is dict else 0
            high_addr = reg_config.get('address').get('high', 0) if type(address) is dict else 0

            if address_type == 'SERIAL':
                value = self._read_serial_register(address)
            elif address_type == 'U_DWORD':
                value = self._read_dword_register(low_addr, high_addr, reg_config['scale'])
            elif address_type == 'U_WORD':
                value = self._read_single_register(reg_config)
            elif address_type == 'S_WORD':
                value = self._read_single_register(reg_config)
            else:
                raise ValueError(f"unknown address type: {address_type}")

            if value is not None:
                results['data'][reg_key] = {
                    'name': name,
                    'value': value,
                    'unit': unit,
                    'address': f"{low_addr}" if type == 'U_DWORD' else address,
                    'type': address_type
                }
            else:
                results['errors'].append(f"error reading {reg_key}, address = {low_addr}-{high_addr}")

            time.sleep(0.05)

        return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="read registers from deye via modbus/solarman")
    parser.add_argument('--ip', required=True, help='ip address of wifi stick (например 192.168.1.100)')
    parser.add_argument('--port', type=int, default=8899, help='wifi stick port, default 8899')
    parser.add_argument('--serial', type=int, required=True, help='serial number of wifi stick')
    parser.add_argument('--map', required=True, dest='registers_map', help='map name')
    return parser.parse_args()


def main():
    args = parse_args()
    reader = DeyeReader(args.ip, args.serial, args.port, args.registers_map)
    if not reader.connect():
        sys.exit(1)

    try:
        results = reader.read_all()
        print(json.dumps(results, indent=2, ensure_ascii=False))
    finally:
        reader.disconnect()


if __name__ == "__main__":
    main()

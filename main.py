#!/usr/bin/env python3

import argparse
import json
import time
import yaml
import sys
import os

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
        self.registers_groups: list[Dict] = []
        self.registers_values: Dict[str, int] = {}
        self._load_registers_map()
        self._group_registers()

    def _load_registers_map(self) -> None:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            with open(script_dir + "/maps/" + self.registers_map_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.registers = config.get('registers', {})

            if not self.registers:
                raise ValueError("No registers found in map file")
        except FileNotFoundError:
            exit(f"file not found: {self.registers_map_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {e}")

    def _group_registers(self) -> None:
        max_span = 8
        max_registers = 8
        ids = []

        for config in self.registers.values():
            if type(config['address']) == int:
                ids.append(int(config['address']))
            if config['type'] == 'SERIAL':
                for reg in config['address']['list']:
                    ids.append(reg)
            if config['type'] == 'U_DWORD':
                ids.append(config['address']['low'])
                ids.append(config['address']['high'])

        groups = []
        current = []

        for reg in sorted(ids):
            if current:
                fits_span = reg - current[0] <= max_span
                fits_count = len(current) < max_registers
                if fits_span and fits_count:
                    current.append(reg)
                    continue

            if current:
                groups.append(current)
            current = [reg]

        if current:
            groups.append(current)

        for g in groups:
            self.registers_groups.append({
                "start": g[0],
                "count": len(g),
                "length": g[-1] - g[0] + 1,
                "registers": g
            })

    def connect(self) -> bool:
        try:
            self.client = PySolarmanV5(
                address=self.host,
                serial=self.serial,
                port=self.port,
                mb_slave_id=1,
                verbose=False,
                socket_timeout=5,
                auto_reconnect=True
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
        """
        reads single or pack of registers
        :param address:
        :param quantity:
        :return:
        """
        if not self.client:
            return None

        if quantity == 1:
            if self.registers_values.get(address) is not None:
                return [self.registers_values.get(address)]

        try:
            result = self.client.read_holding_registers(
                register_addr=address,
                quantity=quantity
            )
            return result
        except (IllegalDataAddressError, Exception) as e:
            return None

    def _read_register_groups(self) -> None:
        """
        reads pack of registers, to avoid deye hangs
        :return:
        """
        for group in self.registers_groups:
            try:
                result = self.client.read_holding_registers(
                    register_addr=group['start'],
                    quantity=group['length'],

                )
                for idx, r in enumerate(result):
                    address = int(group['start'] + idx)
                    self.registers_values[address] = r
                time.sleep(0.05)
            except (IllegalDataAddressError, Exception) as e:
                print(f"error reading register group: {e}")
                continue

    def _read_single_register(self, reg_config: Dict[str, Any]) -> Optional[float]:
        """
        read single register
        :param reg_config:
        :return:
        """
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
        """
        reads dword register, 2 registers high/low value
        :param low_addr:
        :param high_addr:
        :param scale:
        :return:
        """
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

    def _read_serial_register(self, addresses: list) -> Optional[str]:
        """
        reads serial registers and transfer data to ascii
        :param addresses:
        :return:
        """
        data = []
        for address in addresses:
            d = self._read_register(address, 1)
            if d is None:
                return None
            else:
                data.append(d[0])

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

        self._read_register_groups()

        for reg_key, reg_config in self.registers.items():
            address = reg_config['address']
            address_type = reg_config.get('type', '')
            name = reg_config['name']
            unit = reg_config.get('unit', '')
            low_addr = reg_config.get('address').get('low', 0) if type(address) is dict else 0
            high_addr = reg_config.get('address').get('high', 0) if type(address) is dict else 0

            if address_type == 'SERIAL':
                value = self._read_serial_register(address['list'])
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
                results['errors'].append(
                    f"error reading {reg_key}, address = {address}, low={low_addr} high={high_addr}"
                )

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

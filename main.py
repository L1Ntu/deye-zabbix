from sys import argv
from pysolarmanv5 import PySolarmanV5
from deye_controller.utils import group_registers, map_response
from deye_controller.modbus.protocol import HoldingRegisters
from json import dumps

params = dict(enumerate(argv))
INVERTER_IP = params.get(1)
INVERTER_PORT = int(params.get(2)) if params.get(2) else None
LOGGER_SN = int(params.get(3)) if params.get(3) else None


def main():
    if INVERTER_IP is None or INVERTER_PORT is None or LOGGER_SN is None:
        print("Usage:")
        print("python3 main.py inverter_ip inverter_port logger_sn")
        print("python3 main.py 192.168.9.6 8899 2919905242")
        exit(1)

    inv = PySolarmanV5(
        INVERTER_IP,
        LOGGER_SN,
        port=INVERTER_PORT,
        auto_close=True
    )

    registers = [
        # Basic info
        'DeviceType',
        'SerialNumber',
        'InverterWorkMode',
        'RunState',
        'ACRelays',
        'TodayFromGenerator',
        'TodayFromPV',
        'TodayBuyGrid',
        'TodaySoldGrid',
        'PowerToday',
        'TotalFromPV',
        'TotalFromGenerator',
        'TodayGeneratorWorkTime',
        'GeneratorWorkingTime',

        # Solar panels
        'PV1Voltage',
        'PV2Voltage',
        'PV3Voltage',
        'PV1Current',
        'PV2Current',
        'PV3Current',

        # GRID - city input
        'GRIDPhaseAVolt',
        'GRIDPhaseBVolt',
        'GRIDPhaseCVolt',
        'GRIDPhaseAPowerIn',
        'GRIDPhaseBPowerIn',
        'GRIDPhaseCPowerIn',
        'GRIDPhaseACurrentIn',
        'GRIDPhaseBCurrentIn',
        'GRIDPhaseCCurrentIn',
        'GRIDTotalPower',

        # Battery
        'BatterySOC',
        'BattFloat',
        'BattCapacity',
        'BattEmptyVoltage',
        'BatteryTemp',
        'BatteryChargeToday',
        'BatteryDischargeToday',
        'BatteryChargeTotal',
        'BatteryDischargeTotal',
        'BatteryOutPower',
        'BatteryOutCurrent',

        # BMS
        'BMSBatteryCurrent',
        'BMSBatteryTemp',

        # Load
        'UPSPhaseAPower',
        'UPSPhaseBPower',
        'UPSPhaseCPower',
        'UPSTotalPower',
        'LoadPhaseAVolt',
        'LoadPhaseBVolt',
        'LoadPhaseCVolt',
        'LoadTotalPower'
    ]

    regs = [getattr(HoldingRegisters, attr) for attr in registers]
    groups = group_registers(regs)
    result = {}

    try:
        for group in groups:
            res = inv.read_holding_registers(group.start_address, group.len)
            map_response(res, group)
            for reg in group:
                if hasattr(reg, 'suffix'):
                    suffix = reg.suffix
                else:
                    suffix = ''

                result[reg.address] = {
                    'address': reg.address,
                    'description': reg.description,
                    'value': reg.format(),
                    'suffix': suffix
                }

        print(dumps(result))
    except Exception as e:
        print(f"Error sending request: {e}")


if __name__ == '__main__':
    main()

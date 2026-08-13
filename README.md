# deye-zabbix

A small Python script for collecting data from an external source and providing it to **Zabbix** in JSON format.
The project contains the Python script, a Zabbix template, and an example of the data returned by the script.

### Files

| File            | Description |
|-----------------|---|
| `main.py`       | Main Python script |
| `template.yaml` | Zabbix template |
| `example.json`  | Example JSON output |
| `README.md`     | Project documentation |

## Requirements

- Python 3.x
- Zabbix 7.0+
- `pip` / `venv` if additional Python dependencies are required

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd <repository-directory>
```

Create a Python virtual environment:

```bash
python3 -m venv venv
```

Activate the virtual environment:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If the script does not require any external Python packages, this step can be skipped.

## Usage

Run the script:

```bash
python3 main.py
```

Or explicitly use the Python interpreter from the virtual environment:

```bash
./venv/bin/python main.py
```

The script returns data in JSON format.
See `example.json` for a complete example of the returned data.

## Zabbix Integration

The repository contains a ready-to-import Zabbix template:

```text
template.yaml
```

The template can be imported from the Zabbix web interface:

**Data collection → Templates → Import**

After importing the template, link it to the required host.
Also you need to create a UserParameter in zabbix server or proxy


## JSON Output

The expected JSON structure is documented in `example.json`.

If the JSON structure changes, the corresponding Zabbix items and preprocessing rules in `template.yml` may also need to be updated.

## License

Use this project at your own discretion.

# SAP Registry Server

A simple server that serves a static file called `saps.txt` at the `/saps` endpoint. The `saps.txt` file contains a series of `ip:port` entries of various SAPs that are running for clients to connect to.

## Features

- Serves `saps.txt` file content at `/saps` endpoint
- Health check endpoint at `/health`
- Service information at root `/` endpoint
- Background and foreground running modes

## Usage

### Basic Usage

```bash
# Run with default settings (port 8081)
python registry_server.py

# Run with custom port
python registry_server.py --port 8082

# Run with custom saps.txt file
python registry_server.py --saps-file /path/to/custom/saps.txt
```

### Programmatic Usage

```python
from registry_server import SAPRegistryServer

# Create server instance
server = SAPRegistryServer("saps.txt")

# Run in foreground
server.run(host="0.0.0.0", port=8081)

# Or run in background
host, port = server.start_background(host="0.0.0.0", port=8081)
# ... do other work ...
server.stop()
```

## API Endpoints

- `GET /saps` - Returns the content of `saps.txt` as plain text
- `GET /health` - Health check endpoint
- `GET /` - Service information and available endpoints

## saps.txt Format

The `saps.txt` file should contain one `ip:port` entry per line:

```
# Comments start with #
localhost:8080
192.168.1.100:8080
10.0.0.50:8081
```

Lines starting with `#` are treated as comments and ignored.

## Installation

```bash
pip install -r requirements.txt
```

## Example

1. Start the registry server:
   ```bash
   python registry_server.py --port 8081
   ```

2. The server will be available at `http://localhost:8081`

3. Access the SAP endpoints:
   ```bash
   curl http://localhost:8081/saps
   ```

4. Check health:
   ```bash
   curl http://localhost:8081/health
   ```

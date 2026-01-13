# Dynamic Port Management

## Overview

JobiAI now automatically detects and uses available ports to prevent "port already in use" errors. The system will intelligently find free ports and configure all services accordingly.

## How It Works

1. **Port Detection**: On startup, the system scans for available ports
2. **Configuration File**: Creates `.ports.json` with the detected ports
3. **Service Configuration**: Backend and frontend automatically use these ports
4. **CORS Update**: Backend CORS is dynamically configured for the frontend URL

## Port Ranges

- **Backend**: Tries ports 9000-9099 (default: 9000)
- **Frontend**: Tries ports 5173-5272 (default: 5173)

If the default port is taken, the system automatically finds the next available port in the range.

## Files Involved

### Backend
- `backend/app/utils/port_finder.py` - Python port detection utility
- `backend/app/main.py` - Updated to use dynamic CORS origins

### Frontend
- `frontend/port-finder.js` - Node.js port detection utility
- `frontend/vite.config.dynamic.ts` - Dynamic Vite configuration
- `frontend/vite.config.ts` - Gets replaced at startup with dynamic config

### Configuration
- `.ports.json` - Shared configuration file (auto-generated, git-ignored)

## Usage

### Normal Startup
Just run as usual:
```bash
start-dev.bat
```

The script will:
1. Detect available ports
2. Create `.ports.json`
3. Start services on the detected ports
4. Show you the URLs in the terminal

### Manual Port Detection
If you want to check available ports without starting services:
```bash
detect-ports.bat
```

This will show you which ports are available and create the `.ports.json` file.

### Port Configuration File Format
```json
{
  "backend_port": 9000,
  "frontend_port": 5173,
  "backend_url": "http://localhost:9000",
  "frontend_url": "http://localhost:5173"
}
```

## Troubleshooting

### Port Still Blocked?
If you still get port errors:

1. **Check what's using the port**:
   ```bash
   netstat -ano | findstr ":9000"
   ```

2. **Kill the process** (if safe):
   ```bash
   taskkill /PID <pid> /F
   ```

3. **Re-run port detection**:
   ```bash
   detect-ports.bat
   ```

### Services Not Communicating?
If frontend can't reach backend:

1. **Check `.ports.json` exists** in project root
2. **Verify backend is running** on the port shown in terminal
3. **Check browser console** for CORS errors
4. **Restart both services**:
   ```bash
   restart-dev.bat
   ```

### Want to Force Specific Ports?
You can manually create `.ports.json` before starting:

```json
{
  "backend_port": 8080,
  "frontend_port": 3000,
  "backend_url": "http://localhost:8080",
  "frontend_url": "http://localhost:3000"
}
```

**Note**: If those ports are unavailable, Vite will still try to find an alternative for the frontend (thanks to `strictPort: false`).

## Benefits

✅ **No More Port Conflicts**: Automatically finds available ports
✅ **Multiple Instances**: Run multiple dev environments simultaneously
✅ **Zero Configuration**: Works out of the box
✅ **Cross-Service Coordination**: Backend and frontend always configured correctly
✅ **Future-Proof**: Easy to add more services with their own port ranges

## Advanced: Adding New Services

If you add a new service (e.g., a Redis server):

1. **Add port range** to `port_finder.py`:
   ```python
   REDIS_PORT_RANGE = range(6379, 6479)

   def get_redis_port() -> int:
       port = find_available_port(6379, REDIS_PORT_RANGE)
       if port is None:
           raise RuntimeError("No Redis port available")
       return port
   ```

2. **Update config saver**:
   ```python
   def save_port_config(backend_port, frontend_port, redis_port):
       config = {
           # ... existing ports ...
           "redis_port": redis_port,
           "redis_url": f"redis://localhost:{redis_port}"
       }
   ```

3. **Use in startup script**:
   ```batch
   set REDIS_PORT=%%i
   redis-server --port %REDIS_PORT%
   ```

## Technical Details

### Port Availability Check
Uses socket binding to verify port availability:
- Python: `socket.bind()`
- Node.js: `net.createServer()` with error handling

### Race Conditions
The system checks ports sequentially and immediately starts services, minimizing the window for another process to grab the port.

### Fallback Behavior
- If preferred port is taken, scans 100 ports in range
- Vite's `strictPort: false` allows it to increment port if needed
- Backend will error if all ports in range are taken (requires manual intervention)

### CORS Security
Dynamic CORS includes:
- Detected frontend URL
- Default ports (5173, 3000) for backward compatibility
- Only localhost origins (no wildcards)

## Future Enhancements

Potential improvements:
- [ ] Port reservation system to prevent race conditions
- [ ] Health check URLs at detected ports
- [ ] Browser extension to detect running instances
- [ ] Automatic service discovery (mDNS/Bonjour)
- [ ] Port preferences in user settings

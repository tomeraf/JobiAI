/**
 * Port detection and allocation utility for frontend (Node.js)
 */
import net from 'net';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configuration file shared between backend and frontend
const CONFIG_FILE = path.join(__dirname, '..', '.ports.json');

// Default ports to try
const DEFAULT_BACKEND_PORT = 9000;
const DEFAULT_FRONTEND_PORT = 5173;
const BACKEND_PORT_RANGE = { start: 9000, end: 9100 };
// Expand frontend range to cover more ports (5173-5999)
const FRONTEND_PORT_RANGE = { start: 5173, end: 6000 };

/**
 * Check if a port is available for binding
 * @param {number} port - Port number to check
 * @param {string} host - Host address to check on
 * @returns {Promise<boolean>} True if port is available
 */
function isPortAvailable(port, host = '0.0.0.0') {
  return new Promise((resolve) => {
    const server = net.createServer();

    server.once('error', (err) => {
      if (err.code === 'EADDRINUSE') {
        resolve(false);
      } else {
        resolve(false);
      }
    });

    server.once('listening', () => {
      server.close();
      resolve(true);
    });

    server.listen(port, host);
  });
}

/**
 * Find an available port in the given range
 * @param {number} startPort - Preferred port to try first
 * @param {object} portRange - Range object with start and end
 * @returns {Promise<number|null>} Available port number or null
 */
async function findAvailablePort(startPort, portRange) {
  // Try the preferred port first
  if (startPort >= portRange.start && startPort < portRange.end) {
    if (await isPortAvailable(startPort)) {
      return startPort;
    }
  }

  // Try other ports in the range
  for (let port = portRange.start; port < portRange.end; port++) {
    if (port === startPort) continue;
    if (await isPortAvailable(port)) {
      return port;
    }
  }

  return null;
}

/**
 * Get an available port for the backend server
 * @returns {Promise<number>} Available port number
 */
async function getBackendPort() {
  const port = await findAvailablePort(DEFAULT_BACKEND_PORT, BACKEND_PORT_RANGE);
  if (port === null) {
    throw new Error(
      `No available port found in range ${BACKEND_PORT_RANGE.start}-${BACKEND_PORT_RANGE.end - 1}`
    );
  }

  console.log(`Backend port detected: ${port}`);
  return port;
}

/**
 * Get an available port for the frontend server
 * @returns {Promise<number>} Available port number
 */
async function getFrontendPort() {
  const port = await findAvailablePort(DEFAULT_FRONTEND_PORT, FRONTEND_PORT_RANGE);
  if (port === null) {
    throw new Error(
      `No available port found in range ${FRONTEND_PORT_RANGE.start}-${FRONTEND_PORT_RANGE.end - 1}`
    );
  }

  console.log(`Frontend port detected: ${port}`);
  return port;
}

/**
 * Save port configuration to shared file
 * @param {number} backendPort - Backend server port
 * @param {number} frontendPort - Frontend server port
 */
function savePortConfig(backendPort, frontendPort) {
  const config = {
    backend_port: backendPort,
    frontend_port: frontendPort,
    backend_url: `http://localhost:${backendPort}`,
    frontend_url: `http://localhost:${frontendPort}`,
  };

  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
  console.log(`Port configuration saved to ${CONFIG_FILE}`);
}

/**
 * Load port configuration from shared file
 * @returns {object} Configuration object with port information
 */
function loadPortConfig() {
  if (!fs.existsSync(CONFIG_FILE)) {
    // Return defaults if config doesn't exist
    return {
      backend_port: DEFAULT_BACKEND_PORT,
      frontend_port: DEFAULT_FRONTEND_PORT,
      backend_url: `http://localhost:${DEFAULT_BACKEND_PORT}`,
      frontend_url: `http://localhost:${DEFAULT_FRONTEND_PORT}`,
    };
  }

  try {
    const content = fs.readFileSync(CONFIG_FILE, 'utf8');
    return JSON.parse(content);
  } catch (error) {
    console.error(`Failed to load port config: ${error.message}`);
    // Return defaults on error
    return {
      backend_port: DEFAULT_BACKEND_PORT,
      frontend_port: DEFAULT_FRONTEND_PORT,
      backend_url: `http://localhost:${DEFAULT_BACKEND_PORT}`,
      frontend_url: `http://localhost:${DEFAULT_FRONTEND_PORT}`,
    };
  }
}

/**
 * Get the backend URL from configuration
 * @returns {string} Backend URL
 */
function getBackendUrl() {
  const config = loadPortConfig();
  return config.backend_url;
}

// CLI tool for port detection
async function main() {
  console.log('JobiAI Port Detection Tool (Frontend)');
  console.log('='.repeat(50));

  const backendPort = await getBackendPort();
  const frontendPort = await getFrontendPort();

  console.log('\nAvailable ports:');
  console.log(`  Backend:  ${backendPort}`);
  console.log(`  Frontend: ${frontendPort}`);

  savePortConfig(backendPort, frontendPort);
  console.log(`\nConfiguration saved to: ${CONFIG_FILE}`);
}

// Run CLI if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(console.error);
}

export {
  isPortAvailable,
  findAvailablePort,
  getBackendPort,
  getFrontendPort,
  savePortConfig,
  loadPortConfig,
  getBackendUrl,
};

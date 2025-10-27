#!/usr/bin/env python3
"""
SAP Registry Server

A simple server that serves a static file called saps.txt at the /saps endpoint.
The saps.txt file contains a series of ip:port entries of various SAPs that are running.
"""

import os
import logging
from flask import Flask, Response, jsonify
from werkzeug.serving import make_server
import threading
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SAPRegistryServer:
    def __init__(self, saps_file_path: str = "saps.txt"):
        """
        Initialize the SAP Registry Server.
        
        Args:
            saps_file_path: Path to the saps.txt file to serve
        """
        self.saps_file_path = saps_file_path
        self.app = Flask("sap-registry")
        self._configure_routes()
        
        self._wsgi_server = None
        self._server_thread: Optional[threading.Thread] = None

    def _configure_routes(self) -> None:
        """Configure Flask routes."""
        app = self.app

        @app.route("/saps")
        def serve_saps():
            """Serve the saps.txt file content."""
            try:
                if not os.path.exists(self.saps_file_path):
                    logger.warning(f"saps.txt file not found at {self.saps_file_path}")
                    return jsonify({"error": "saps.txt file not found"}), 404
                
                with open(self.saps_file_path, 'r') as f:
                    content = f.read()
                
                logger.info("Serving saps.txt content")
                return Response(content, mimetype='text/plain')
                
            except Exception as e:
                logger.error(f"Error reading saps.txt: {str(e)}")
                return jsonify({"error": f"Error reading file: {str(e)}"}), 500

        @app.route("/wtf")
        def wtf():
            """What the fuck is this server? Returns server type."""
            return jsonify({"type": "Registry"})

        @app.route("/health")
        def health():
            """Health check endpoint."""
            return jsonify({"status": "ok", "service": "sap-registry"})

        @app.route("/")
        def root():
            """Root endpoint with service information."""
            return jsonify({
                "service": "SAP Registry",
                "description": "Serves SAP server endpoints from saps.txt",
                "endpoints": {
                    "/wtf": "Server type identification",
                    "/saps": "SAP server endpoints (ip:port format)",
                    "/health": "Health check"
                },
                "status": "running"
            })

    def _create_server(self, host: str, port: int) -> Tuple[str, int]:
        """Create and bind the WSGI server."""
        try:
            server = make_server(host, port, self.app)
            self._wsgi_server = server
            actual_port = server.server_port
            return host, actual_port
        except OSError as e:
            raise e

    def start_background(
        self,
        host: str = "0.0.0.0",
        port: int = 8081
    ) -> Tuple[str, int]:
        """Start the server in background mode."""
        logger.info(f"Starting SAP Registry server on {host}:{port}")
        
        # Create WSGI server
        bound_host, actual_port = self._create_server(host, port)
        logger.info(f"Server bound to {bound_host}:{actual_port}")

        # Start serving in background
        def _serve():
            assert self._wsgi_server is not None
            logger.info("Starting HTTP server thread")
            self._wsgi_server.serve_forever()

        self._server_thread = threading.Thread(target=_serve, name="sap-registry-server", daemon=True)
        self._server_thread.start()
        logger.info("SAP Registry server started successfully")
        return bound_host, actual_port

    def stop(self, timeout: Optional[float] = 5.0) -> None:
        """Stop the server."""
        logger.info(f"Stopping SAP Registry server (timeout: {timeout}s)")
        try:
            if self._wsgi_server is not None:
                logger.info("Shutting down WSGI server")
                self._wsgi_server.shutdown()
        finally:
            if self._server_thread and self._server_thread.is_alive():
                logger.info("Waiting for server thread to finish")
                self._server_thread.join(timeout=timeout)
        logger.info("SAP Registry server stopped")

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8081
    ) -> None:
        """Run the server in foreground mode."""
        logger.info("Starting SAP Registry server run mode")
        try:
            bound_host, actual_port = self.start_background(
                host=host,
                port=port
            )
            print(f"SAP Registry running at http://{bound_host}:{actual_port}")
            logger.info(f"SAP Registry running at http://{bound_host}:{actual_port}")
            
            # Block main thread until interrupted
            import time
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
        finally:
            self.stop()


def run_registry_server(
    saps_file_path: str = "saps.txt",
    host: str = "0.0.0.0",
    port: int = 8081
) -> None:
    """Convenience function to run the registry server."""
    server = SAPRegistryServer(saps_file_path)
    server.run(host=host, port=port)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SAP Registry Server")
    parser.add_argument("--saps-file", default="saps.txt", help="Path to saps.txt file")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8081, help="Port to bind to")
    
    args = parser.parse_args()
    
    run_registry_server(
        saps_file_path=args.saps_file,
        host=args.host,
        port=args.port
    )

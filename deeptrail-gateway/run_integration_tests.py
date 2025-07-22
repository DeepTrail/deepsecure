#!/usr/bin/env python3
"""
Integration test runner for DeepTrail Gateway.

This script sets up the necessary environment and runs integration tests
between the deeptrail-gateway and deeptrail-control services.
"""

import os
import sys
import time
import subprocess
import signal
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

import httpx
import pytest


class IntegrationTestRunner:
    """Manages the integration test lifecycle."""
    
    def __init__(self):
        self.control_plane_url = "http://localhost:8000"
        self.gateway_url = "http://localhost:8002"
        self.test_timeout = 60  # seconds
        self.services_ready = False
        
    async def check_service_health(self, url: str, service_name: str) -> bool:
        """Check if a service is healthy and responding."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{url}/health")
                if response.status_code == 200:
                    print(f"✅ {service_name} is healthy at {url}")
                    return True
                else:
                    print(f"❌ {service_name} returned status {response.status_code}")
                    return False
        except Exception as e:
            print(f"❌ {service_name} health check failed: {e}")
            return False
    
    async def wait_for_services(self, max_wait: int = 60) -> bool:
        """Wait for both services to be ready."""
        print("🔄 Waiting for services to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            control_healthy = await self.check_service_health(
                self.control_plane_url, "DeepTrail Control"
            )
            gateway_healthy = await self.check_service_health(
                self.gateway_url, "DeepTrail Gateway"
            )
            
            if control_healthy and gateway_healthy:
                print("✅ All services are ready!")
                self.services_ready = True
                return True
            
            print(f"⏳ Services not ready yet, waiting... ({int(time.time() - start_time)}s)")
            await asyncio.sleep(5)
        
        print("❌ Services did not become ready within the timeout period")
        return False
    
    def setup_environment(self):
        """Set up environment variables for testing."""
        os.environ["DEEPTRAIL_CONTROL_URL"] = self.control_plane_url
        os.environ["DEEPTRAIL_GATEWAY_URL"] = self.gateway_url
        os.environ["PYTHONPATH"] = str(Path(__file__).parent)
        
        # Add the parent directory to Python path for deepsecure imports
        parent_dir = Path(__file__).parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
    
    def run_tests(self, test_pattern: Optional[str] = None) -> int:
        """Run the integration tests."""
        if not self.services_ready:
            print("❌ Services are not ready. Cannot run tests.")
            return 1
        
        # Set up pytest arguments
        pytest_args = [
            "-v",  # verbose output
            "--tb=short",  # shorter traceback format
            "-x",  # stop on first failure
            "--durations=10",  # show slowest 10 tests
            "-m", "integration",  # run only integration tests
            "tests/test_integration.py"
        ]
        
        if test_pattern:
            pytest_args.extend(["-k", test_pattern])
        
        print(f"🧪 Running integration tests with: pytest {' '.join(pytest_args)}")
        
        # Run pytest
        return pytest.main(pytest_args)
    
    def run_docker_compose_tests(self) -> int:
        """Run integration tests using docker-compose services."""
        print("🐳 Starting services with docker-compose...")
        
        # Change to the parent directory where docker-compose.yml is located
        parent_dir = Path(__file__).parent.parent
        os.chdir(parent_dir)
        
        try:
            # Start services
            subprocess.run(
                ["docker-compose", "up", "-d", "--build"],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Wait for services to be ready
            if not asyncio.run(self.wait_for_services()):
                return 1
            
            # Run tests
            return self.run_tests()
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start services: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            return 1
        
        finally:
            # Clean up
            print("🧹 Cleaning up services...")
            subprocess.run(
                ["docker-compose", "down"],
                capture_output=True,
                text=True
            )
    
    def run_local_tests(self) -> int:
        """Run integration tests assuming services are already running locally."""
        print("🏠 Running tests against local services...")
        
        # Check if services are ready
        if not asyncio.run(self.wait_for_services()):
            return 1
        
        # Run tests
        return self.run_tests()


def main():
    """Main entry point for the integration test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run DeepTrail Gateway integration tests")
    parser.add_argument(
        "--mode",
        choices=["local", "docker"],
        default="local",
        help="Test mode: 'local' for existing services, 'docker' for docker-compose"
    )
    parser.add_argument(
        "--pattern",
        help="Test pattern to filter tests (pytest -k pattern)"
    )
    parser.add_argument(
        "--control-url",
        default="http://localhost:8000",
        help="DeepTrail Control URL"
    )
    parser.add_argument(
        "--gateway-url",
        default="http://localhost:8002",
        help="DeepTrail Gateway URL"
    )
    
    args = parser.parse_args()
    
    # Create test runner
    runner = IntegrationTestRunner()
    runner.control_plane_url = args.control_url
    runner.gateway_url = args.gateway_url
    
    # Set up environment
    runner.setup_environment()
    
    # Run tests based on mode
    if args.mode == "docker":
        exit_code = runner.run_docker_compose_tests()
    else:
        exit_code = runner.run_local_tests()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main() 
"""Gateway management commands for DeepSecure CLI."""

import typer
import requests
import json
import sys
import time
from typing import Optional, Annotated
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .._core.config import get_deeptrail_gateway_url, get_deeptrail_control_url
from .. import utils

app = typer.Typer(
    name="gateway",
    help="Manage and monitor the DeepSecure gateway service.",
    rich_markup_mode="markdown",
    no_args_is_help=True,
)

console = Console()


@app.command("health")
def health_check(
    gateway_url: Annotated[
        Optional[str],
        typer.Option(
            "--gateway-url",
            "-g",
            help="Gateway URL to check (overrides configuration)",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed health information",
        ),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            "-t",
            help="Request timeout in seconds",
        ),
    ] = 10,
) -> None:
    """Check the health and status of the DeepSecure gateway service."""
    
    # Get gateway URL from config if not provided
    if not gateway_url:
        gateway_url = get_deeptrail_gateway_url()
    
    if not gateway_url:
        console.print(
            Panel(
                "[red]❌ Gateway URL not configured[/red]\n\n"
                "Please configure the gateway URL:\n"
                "  [cyan]deepsecure configure set-gateway-url http://localhost:8002[/cyan]\n\n"
                "Or set the environment variable:\n"
                "  [cyan]export DEEPSECURE_GATEWAY_URL=http://localhost:8002[/cyan]",
                title="Gateway Configuration Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)
    
    console.print(f"🌐 Checking gateway health at: [cyan]{gateway_url}[/cyan]")
    
    # Test gateway health endpoint
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Checking gateway health...", total=None)
        
        try:
            response = requests.get(
                f"{gateway_url}/health",
                timeout=timeout,
                headers={"User-Agent": "DeepSecure-CLI/health-check"}
            )
            
            progress.update(task, description="Gateway responded")
            
            if response.status_code == 200:
                console.print("✅ [green]Gateway is healthy![/green]")
                
                if verbose:
                    # Show detailed health information
                    try:
                        health_data = response.json()
                        table = Table(title="Gateway Health Details")
                        table.add_column("Property", style="cyan")
                        table.add_column("Value", style="green")
                        
                        for key, value in health_data.items():
                            table.add_row(str(key), str(value))
                        
                        console.print(table)
                    except Exception:
                        console.print(f"📋 Status Code: {response.status_code}")
                        console.print(f"📄 Response: {response.text[:200]}...")
                
            else:
                console.print(f"⚠️  [yellow]Gateway responded with status {response.status_code}[/yellow]")
                if verbose:
                    console.print(f"📄 Response: {response.text}")
                raise typer.Exit(code=1)
                
        except requests.exceptions.ConnectionError:
            console.print(f"❌ [red]Could not connect to gateway at {gateway_url}[/red]")
            console.print("\n🔧 Troubleshooting steps:")
            console.print("  1. Check if gateway service is running:")
            console.print("     [cyan]docker compose ps deeptrail-gateway[/cyan]")
            console.print("  2. Start the gateway service:")
            console.print("     [cyan]docker compose up deeptrail-gateway -d[/cyan]")
            console.print("  3. Check gateway logs:")
            console.print("     [cyan]docker compose logs deeptrail-gateway[/cyan]")
            raise typer.Exit(code=1)
            
        except requests.exceptions.Timeout:
            console.print(f"❌ [red]Gateway health check timed out after {timeout} seconds[/red]")
            console.print("💡 Try increasing timeout with --timeout option")
            raise typer.Exit(code=1)
            
        except Exception as e:
            console.print(f"❌ [red]Unexpected error checking gateway health: {e}[/red]")
            raise typer.Exit(code=1)


@app.command("test-proxy")
def test_proxy(
    target: Annotated[
        str,
        typer.Option(
            "--target",
            "-t",
            help="Target URL to test proxy functionality",
        ),
    ] = "https://httpbin.org/get",
    gateway_url: Annotated[
        Optional[str],
        typer.Option(
            "--gateway-url",
            "-g",
            help="Gateway URL to use (overrides configuration)",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed proxy test information",
        ),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            help="Request timeout in seconds",
        ),
    ] = 30,
) -> None:
    """Test the gateway's proxy functionality with external API calls."""
    
    # Get gateway URL from config if not provided
    if not gateway_url:
        gateway_url = get_deeptrail_gateway_url()
    
    if not gateway_url:
        console.print(
            Panel(
                "[red]❌ Gateway URL not configured[/red]\n\n"
                "Please configure the gateway URL:\n"
                "  [cyan]deepsecure configure set-gateway-url http://localhost:8002[/cyan]",
                title="Gateway Configuration Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)
    
    console.print(f"🧪 Testing gateway proxy functionality")
    console.print(f"🌐 Gateway: [cyan]{gateway_url}[/cyan]")
    console.print(f"🎯 Target: [cyan]{target}[/cyan]")
    
    # Parse target URL
    from urllib.parse import urlparse
    parsed = urlparse(target)
    target_base_url = f"{parsed.scheme}://{parsed.netloc}"
    target_path = parsed.path or "/"
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Testing proxy functionality...", total=None)
        
        try:
            # Make proxy request through gateway
            proxy_url = f"{gateway_url}/proxy{target_path}"
            
            headers = {
                "X-Target-Base-URL": target_base_url,
                "User-Agent": "DeepSecure-CLI/proxy-test",
                "X-Test-Request": "true"
            }
            
            response = requests.get(
                proxy_url,
                headers=headers,
                timeout=timeout
            )
            
            progress.update(task, description="Proxy request completed")
            
            if response.status_code == 200:
                console.print("✅ [green]Proxy test successful![/green]")
                
                if verbose:
                    console.print(f"📊 Response Status: {response.status_code}")
                    console.print(f"📏 Response Size: {len(response.text)} bytes")
                    console.print(f"⏱️  Response Time: ~{response.elapsed.total_seconds():.2f}s")
                    
                    # Show response headers
                    console.print("\n📋 Response Headers:")
                    headers_table = Table()
                    headers_table.add_column("Header", style="cyan")
                    headers_table.add_column("Value", style="white")
                    
                    for key, value in response.headers.items():
                        headers_table.add_row(key, str(value)[:100])
                    
                    console.print(headers_table)
                    
                    # Show response body (first 500 chars)
                    console.print("\n📄 Response Body (truncated):")
                    response_text = response.text[:500]
                    try:
                        # Try to pretty-print JSON
                        json_data = json.loads(response_text)
                        console.print_json(json.dumps(json_data, indent=2))
                    except json.JSONDecodeError:
                        console.print(response_text)
                        
            else:
                console.print(f"⚠️  [yellow]Proxy test returned status {response.status_code}[/yellow]")
                if verbose:
                    console.print(f"📄 Response: {response.text}")
                raise typer.Exit(code=1)
                
        except requests.exceptions.ConnectionError:
            console.print(f"❌ [red]Could not connect to gateway at {gateway_url}[/red]")
            console.print("\n🔧 Troubleshooting steps:")
            console.print("  1. Check gateway health:")
            console.print("     [cyan]deepsecure gateway health[/cyan]")
            console.print("  2. Check if gateway service is running:")
            console.print("     [cyan]docker compose ps deeptrail-gateway[/cyan]")
            raise typer.Exit(code=1)
            
        except requests.exceptions.Timeout:
            console.print(f"❌ [red]Proxy test timed out after {timeout} seconds[/red]")
            console.print("💡 Try increasing timeout with --timeout option")
            raise typer.Exit(code=1)
            
        except Exception as e:
            console.print(f"❌ [red]Unexpected error during proxy test: {e}[/red]")
            raise typer.Exit(code=1)


@app.command("status")
def status(
    gateway_url: Annotated[
        Optional[str],
        typer.Option(
            "--gateway-url",
            "-g",
            help="Gateway URL to check (overrides configuration)",
        ),
    ] = None,
    control_url: Annotated[
        Optional[str],
        typer.Option(
            "--control-url",
            "-c",
            help="Control plane URL to check (overrides configuration)",
        ),
    ] = None,
) -> None:
    """Show comprehensive status of both gateway and control plane services."""
    
    # Get URLs from config if not provided
    if not gateway_url:
        gateway_url = get_deeptrail_gateway_url()
    if not control_url:
        control_url = get_deeptrail_control_url()
    
    console.print("[bold]🌐 DeepSecure Services Status[/bold]")
    console.print()
    
    # Create status table
    status_table = Table(title="Service Status")
    status_table.add_column("Service", style="cyan")
    status_table.add_column("URL", style="white")
    status_table.add_column("Status", style="bold")
    status_table.add_column("Response Time", style="yellow")
    
    # Check control plane
    control_status = "❌ Not configured"
    control_time = "N/A"
    if control_url:
        try:
            start_time = time.time()
            response = requests.get(f"{control_url}/health", timeout=5)
            end_time = time.time()
            if response.status_code == 200:
                control_status = "✅ Healthy"
                control_time = f"{(end_time - start_time):.2f}s"
            else:
                control_status = f"⚠️  Status {response.status_code}"
                control_time = f"{(end_time - start_time):.2f}s"
        except requests.exceptions.ConnectionError:
            control_status = "❌ Connection Failed"
        except requests.exceptions.Timeout:
            control_status = "❌ Timeout"
        except Exception as e:
            control_status = f"❌ Error: {str(e)[:20]}"
    
    # Check gateway
    gateway_status = "❌ Not configured"
    gateway_time = "N/A"
    if gateway_url:
        try:
            start_time = time.time()
            response = requests.get(f"{gateway_url}/health", timeout=5)
            end_time = time.time()
            if response.status_code == 200:
                gateway_status = "✅ Healthy"
                gateway_time = f"{(end_time - start_time):.2f}s"
            else:
                gateway_status = f"⚠️  Status {response.status_code}"
                gateway_time = f"{(end_time - start_time):.2f}s"
        except requests.exceptions.ConnectionError:
            gateway_status = "❌ Connection Failed"
        except requests.exceptions.Timeout:
            gateway_status = "❌ Timeout"
        except Exception as e:
            gateway_status = f"❌ Error: {str(e)[:20]}"
    
    # Add rows to table
    status_table.add_row(
        "Control Plane",
        control_url or "Not configured",
        control_status,
        control_time
    )
    status_table.add_row(
        "Gateway",
        gateway_url or "Not configured",
        gateway_status,
        gateway_time
    )
    
    console.print(status_table)
    console.print()
    
    # Show configuration recommendations
    if not gateway_url or not control_url:
        console.print(
            Panel(
                "[yellow]⚠️  Configuration Incomplete[/yellow]\n\n"
                "Set up both services for full functionality:\n"
                "  [cyan]deepsecure configure set-url http://localhost:8000[/cyan]\n"
                "  [cyan]deepsecure configure set-gateway-url http://localhost:8002[/cyan]",
                title="Configuration Recommendations",
                border_style="yellow",
            )
        )
    
    # Show troubleshooting tips if services are down
    if "❌" in control_status or "❌" in gateway_status:
        console.print(
            Panel(
                "[red]🔧 Troubleshooting Tips[/red]\n\n"
                "Start both services:\n"
                "  [cyan]docker compose up deeptrail-control deeptrail-gateway -d[/cyan]\n\n"
                "Check service logs:\n"
                "  [cyan]docker compose logs deeptrail-control[/cyan]\n"
                "  [cyan]docker compose logs deeptrail-gateway[/cyan]",
                title="Service Issues Detected",
                border_style="red",
            )
        )


@app.command("connectivity")
def connectivity_test(
    gateway_url: Annotated[
        Optional[str],
        typer.Option(
            "--gateway-url",
            "-g",
            help="Gateway URL to test (overrides configuration)",
        ),
    ] = None,
) -> None:
    """Test end-to-end connectivity between CLI, gateway, and external services."""
    
    # Get gateway URL from config if not provided
    if not gateway_url:
        gateway_url = get_deeptrail_gateway_url()
    
    if not gateway_url:
        console.print(
            Panel(
                "[red]❌ Gateway URL not configured[/red]\n\n"
                "Please configure the gateway URL:\n"
                "  [cyan]deepsecure configure set-gateway-url http://localhost:8002[/cyan]",
                title="Gateway Configuration Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)
    
    console.print("[bold]🔗 Testing End-to-End Connectivity[/bold]")
    console.print()
    
    tests = [
        ("Gateway Health", f"{gateway_url}/health"),
        ("Gateway Proxy", f"{gateway_url}/proxy/get"),
        ("External Service", "https://httpbin.org/get"),
    ]
    
    results = []
    
    for test_name, test_url in tests:
        console.print(f"🧪 Testing: {test_name}")
        
        try:
            if test_name == "Gateway Proxy":
                # Special handling for proxy test
                headers = {
                    "X-Target-Base-URL": "https://httpbin.org",
                    "User-Agent": "DeepSecure-CLI/connectivity-test"
                }
                response = requests.get(test_url, headers=headers, timeout=10)
            else:
                response = requests.get(test_url, timeout=10)
            
            if response.status_code == 200:
                console.print(f"   ✅ [green]Success[/green] ({response.status_code})")
                results.append((test_name, "✅ Success", response.status_code))
            else:
                console.print(f"   ⚠️  [yellow]Status {response.status_code}[/yellow]")
                results.append((test_name, f"⚠️  Status {response.status_code}", response.status_code))
                
        except requests.exceptions.ConnectionError:
            console.print(f"   ❌ [red]Connection Failed[/red]")
            results.append((test_name, "❌ Connection Failed", "N/A"))
        except requests.exceptions.Timeout:
            console.print(f"   ❌ [red]Timeout[/red]")
            results.append((test_name, "❌ Timeout", "N/A"))
        except Exception as e:
            console.print(f"   ❌ [red]Error: {str(e)[:30]}[/red]")
            results.append((test_name, f"❌ Error", "N/A"))
    
    console.print()
    
    # Summary table
    summary_table = Table(title="Connectivity Test Results")
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Result", style="bold")
    summary_table.add_column("Status Code", style="yellow")
    
    for test_name, result, status_code in results:
        summary_table.add_row(test_name, result, str(status_code))
    
    console.print(summary_table)
    
    # Overall assessment
    success_count = sum(1 for _, result, _ in results if "✅" in result)
    if success_count == len(results):
        console.print("\n🎉 [green]All connectivity tests passed![/green]")
    elif success_count > 0:
        console.print(f"\n⚠️  [yellow]{success_count}/{len(results)} tests passed[/yellow]")
    else:
        console.print("\n❌ [red]All connectivity tests failed[/red]")
        console.print("\n🔧 Check your network connection and service configuration")
        raise typer.Exit(code=1) 